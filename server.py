import warnings
warnings.filterwarnings("ignore")

import sys
import os
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pipeline.pipeline import run_pipeline
from pipeline.chroma_store import get_vectorstore
from pipeline.claude_recap import generate_chat_response

logger = logging.getLogger(__name__)

app = FastAPI(title="Court Report API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CACHE_PATH = Path(__file__).parent / "data" / "digest_cache.json"

vectorstore = get_vectorstore()

chat_sessions: dict[str, list[dict]] = {}

# Module-level cache for last_night_context — rebuilt only when cache file changes
_cached_last_night_context: str = ""
_cached_last_night_mtime: float = 0.0


class ChatRequest(BaseModel):
    question: str
    session_id: str


def _build_last_night_context() -> str:
    """
    Pull player_game documents for last night from Chroma, filtering to players
    who played meaningful minutes (stored as metadata-filtered fetch).
    Returns empty string if cache is missing or no documents found.
    """
    date = ""
    if CACHE_PATH.exists():
        try:
            cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            date = cache.get("date", "")
        except Exception as e:
            logger.warning(f"[last_night_context] Failed to read cache: {e}")

    if not date:
        return ""

    try:
        results = vectorstore.get(where={"$and": [{"type": "player_game"}, {"date": date}]})
        docs = results.get("documents", []) or []

        if not docs:
            return ""

        # Filter to players with > 15 minutes by parsing the doc text
        # Doc format: "Name | TEAM vs OPP | date | X PTS Y REB ..."
        # Minutes aren't in the doc string — include all non-garbage players
        # by filtering out lines with very low stat totals (pts+reb+ast < 5)
        filtered = []
        for doc in docs:
            try:
                parts = doc.split(" | ")
                if len(parts) < 4:
                    filtered.append(doc)
                    continue
                stats_str = parts[3]
                pts = int(stats_str.split(" PTS")[0].split()[-1]) if " PTS" in stats_str else 0
                reb = int(stats_str.split(" REB")[0].split()[-1]) if " REB" in stats_str else 0
                ast = int(stats_str.split(" AST")[0].split()[-1]) if " AST" in stats_str else 0
                if pts + reb + ast >= 5:
                    filtered.append(doc)
            except Exception:
                filtered.append(doc)

        return "\n".join(filtered) if filtered else ""

    except Exception as e:
        logger.warning(f"[last_night_context] Chroma fetch failed: {e}")
        return ""


def _get_last_night_context() -> str:
    """Return cached last_night_context, rebuilding only if digest_cache.json has changed."""
    global _cached_last_night_context, _cached_last_night_mtime

    try:
        current_mtime = os.path.getmtime(CACHE_PATH) if CACHE_PATH.exists() else 0.0
    except OSError:
        current_mtime = 0.0

    if current_mtime != _cached_last_night_mtime:
        _cached_last_night_context = _build_last_night_context()
        _cached_last_night_mtime = current_mtime

    return _cached_last_night_context


def _is_followup_question(question: str) -> bool:
    """Return True if the question is short or contains a pronoun, indicating a follow-up."""
    followup_pronouns = {"he", "his", "him", "they", "their", "them", "she", "her"}
    words = question.lower().split()
    if len(words) < 6:
        return True
    if followup_pronouns.intersection(words):
        return True
    return False


# Name parts that are common words or suffixes, not useful for matching
_NAME_SKIP_PARTS = {"jr", "ii", "iii", "iv", "de", "le", "la", "van", "el"}


def _extract_player_name(text: str) -> str | None:
    """
    Scan text against known player_name values stored in Chroma metadata.
    Returns the first matching full player name, or None if no match found.

    Handles three cases:
    1. Normal multi-word names: any individual part (3+ chars, not a suffix)
       appearing as a substring in the query.
    2. Hyphenated names: the full hyphenated first name (e.g. 'karl-anthony')
       checked as a single substring.
    3. Uppercase abbreviations: any 2-4 char all-uppercase token in the query
       (e.g. 'KAT', 'KD') matched against initials derived from stored names.
    """
    try:
        results = vectorstore.get(where={"type": "player_game"})
        metadatas = results.get("metadatas", []) or []
    except Exception:
        return None

    # Collect unique player names from metadata
    seen_names: set[str] = set()
    known_names: list[str] = []
    for meta in metadatas:
        name = meta.get("player_name", "")
        if name and name not in seen_names:
            seen_names.add(name)
            known_names.append(name)

    if not known_names:
        return None

    lower_text = text.lower()

    # Extract any uppercase abbreviation tokens from the query (2-4 chars, all caps)
    import re
    abbrev_tokens = set(re.findall(r'\b[A-Z]{2,4}\b', text))

    for name in known_names:
        parts = name.split()
        lower_name = name.lower()

        # Case 1: hyphenated first name substring match (e.g. 'karl-anthony')
        if "-" in lower_name and lower_name.split()[0] in lower_text:
            return name
        # Also check full hyphenated segment without spaces
        hyphen_segment = lower_name.replace(" ", "-")
        if "-" in hyphen_segment and hyphen_segment in lower_text:
            return name

        # Case 2: individual name part substring match (skip suffixes and short parts)
        if any(
            part.lower() in lower_text
            for part in parts
            if len(part) >= 3 and part.lower() not in _NAME_SKIP_PARTS
        ):
            return name

        # Case 3: abbreviation match — check if any uppercase token in the query
        # matches the initials of this player's name
        if abbrev_tokens:
            # Split on both spaces and hyphens so 'Karl-Anthony Towns' -> ['Karl','Anthony','Towns']
            all_parts = re.split(r"[\s\-]+", name)
            initials = "".join(p[0] for p in all_parts if p and p[0].isupper())
            if initials in abbrev_tokens:
                return name

    return None


def _retrieve_chroma_context(query: str, last_user_msg: str | None = None) -> str:
    """
    Run two targeted Chroma retrievals by document type and return combined results.
    For season_averages, builds an explicit player-name query if a name can be
    identified in the current question or the last user message.
    """
    # Try to find a player name in the current question first, then fall back to
    # the last user message (covers pronoun follow-ups like "what about his average")
    combined_text = query if not last_user_msg else f"{last_user_msg} {query}"
    player_name = _extract_player_name(combined_text)

    season_query = (
        f"{player_name} season averages 2025-26" if player_name else query
    )

    seen = set()
    combined = []

    queries_by_type = {
        "season_averages": season_query,
        "game_recap":      query,
    }

    for doc_type, type_query in queries_by_type.items():
        try:
            retriever = vectorstore.as_retriever(
                search_kwargs={"k": 2, "filter": {"type": doc_type}}
            )
            docs = retriever.invoke(type_query)
            for doc in docs:
                content = doc.page_content
                if content not in seen:
                    seen.add(content)
                    combined.append(content)
        except Exception as e:
            logger.warning(f"[chroma] Retrieval failed for type={doc_type}: {e}")

    return "\n".join(combined) if combined else "No historical context available."


@app.post("/chat")
def chat(req: ChatRequest):
    history = chat_sessions.setdefault(req.session_id, [])

    last_user_msg = next(
        (m["content"] for m in reversed(history) if m["role"] == "user"), None
    )

    # Only expand retrieval query with prior message if this looks like a follow-up
    if last_user_msg and _is_followup_question(req.question):
        retrieval_query = f"{last_user_msg} {req.question}"
    else:
        retrieval_query = req.question

    last_night_context = _get_last_night_context()
    context = _retrieve_chroma_context(retrieval_query, last_user_msg=last_user_msg)

    try:
        answer = generate_chat_response(
            req.question, context, history, last_night_context=last_night_context
        )
    except Exception as e:
        logger.error(f"[chat] generate_chat_response failed: {e}")
        return {"answer": "Sorry, Court Report is having trouble right now. Please try again in a moment."}

    history.append({"role": "user", "content": req.question})
    history.append({"role": "assistant", "content": answer})
    return {"answer": answer}


@app.get("/health")
def health():
    return {"status": "ok"}


CACHE_TTL_HOURS = 12


@app.get("/digest")
def digest():
    now = datetime.utcnow()

    # Return cache if it exists and is within the TTL window
    if CACHE_PATH.exists():
        try:
            cached = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            cached_at = datetime.fromisoformat(cached["cached_at"])
            age = now - cached_at
            if age < timedelta(hours=CACHE_TTL_HOURS):
                print(f"[cache] Returning cached digest (age: {age}, cached_at: {cached['cached_at']})")
                return {k: v for k, v in cached.items() if k != "cached_at"}
        except Exception as e:
            print(f"[cache] Could not read cache, regenerating: {e}")

    # Run pipeline and write fresh cache with timestamp
    print(f"[cache] Cache missing or expired — running pipeline")
    result = run_pipeline()
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        cache_payload = {**result, "cached_at": now.isoformat()}
        CACHE_PATH.write_text(json.dumps(cache_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[cache] Digest cached to {CACHE_PATH} at {now.isoformat()}")
    except Exception as e:
        print(f"[cache] Could not write cache: {e}")

    return result
