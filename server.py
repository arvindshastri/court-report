import warnings
warnings.filterwarnings("ignore")

import sys
import json
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pipeline.pipeline import run_pipeline
from pipeline.chroma_store import get_vectorstore, retrieve_relevant_history
from pipeline.claude_recap import generate_chat_response, client as claude_client

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


class ChatRequest(BaseModel):
    question: str
    session_id: str


_NICKNAME_EXPANSION_PROMPT = (
    "You are an NBA assistant. If the question contains any player nicknames, abbreviations "
    "(like KAT, AD, KD), or first names only, rewrite the question replacing them with the "
    "player's full name. If no nicknames are present, return the question unchanged. "
    "Return only the rewritten question, nothing else."
)


def _expand_nicknames(question: str) -> str:
    response = claude_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        system=_NICKNAME_EXPANSION_PROMPT,
        messages=[{"role": "user", "content": question}],
    )
    return response.content[0].text.strip()


@app.post("/chat")
def chat(req: ChatRequest):
    history = chat_sessions.setdefault(req.session_id, [])
    last_user_msg = next(
        (m["content"] for m in reversed(history) if m["role"] == "user"), None
    )
    expanded_question = _expand_nicknames(req.question)
    retrieval_query = (
        f"{last_user_msg} {expanded_question}" if last_user_msg else expanded_question
    )
    context_docs = retrieve_relevant_history(retrieval_query, n_results=3, vs=vectorstore)
    context = "\n".join(context_docs) if context_docs else "No recent game data available."
    answer = generate_chat_response(req.question, context, history)
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
