import warnings
warnings.filterwarnings("ignore")

import re
import time
import sys
import io
from pathlib import Path

# Ensure stdout handles Unicode (emoji, dashes) on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.fetcher import get_games, get_player_stats, get_upcoming_games
from pipeline.claude_recap import generate_digest, generate_game_card_recap
from pipeline.chroma_store import (
    retrieve_relevant_history,
    store_nightly_recaps,
    store_player_game_stats,
    get_vectorstore,
)


def _parse_minutes(minutes_str):
    """Convert 'MM:SS' string to float minutes."""
    try:
        parts = minutes_str.split(":")
        return int(parts[0]) + int(parts[1]) / 60
    except Exception:
        return 0.0


def calculate_game_score(player):
    """
    Hollinger Game Score formula:
    PTS + 0.4*FGM - 0.7*FGA - 0.4*(FTA-FTM) + 0.7*ORB + 0.3*DRB + STL + 0.7*AST + 0.7*BLK - 0.4*PF - TOV
    Only calculated for players with >15 minutes played.
    Returns None if not eligible.
    """
    mins = _parse_minutes(player.get("minutes") or "0:00")
    if mins <= 15:
        return None

    def g(key, default=0):
        v = player.get(key)
        return v if v is not None else default

    gs = (
        g("points")
        + 0.4 * g("fg_made")
        - 0.7 * g("fg_attempted")
        - 0.4 * (g("ft_attempted") - g("ft_made"))
        + 0.7 * g("offensive_rebounds")
        + 0.3 * g("defensive_rebounds")
        + g("steals")
        + 0.7 * g("assists")
        + 0.7 * g("blocks")
        - 0.4 * g("personal_fouls")
        - g("turnovers")
    )
    return round(gs, 2)


def build_full_game(game):
    """
    Enrich a parsed game dict with per-player box score stats and game scores.
    Returns a new dict with 'player_stats' key added; each player has 'game_score'.
    """
    time.sleep(0.6)
    player_stats = get_player_stats(game["game_id"])

    for side in ("home_players", "away_players"):
        for player in player_stats[side]:
            player["game_score"] = calculate_game_score(player)

    return {**game, "player_stats": player_stats}


def get_underrated_player(games):
    """
    Find the most underrated performer across all enriched games.
    Ranks all eligible players (15+ min) by points and by game_score,
    returns the player with the highest positive (points_rank - game_score_rank),
    meaning they contributed far more than their scoring implied.
    """
    all_players = []
    for game in games:
        ps = game.get("player_stats", {})
        for side in ("home_players", "away_players"):
            for p in ps.get(side, []):
                if p.get("game_score") is not None:
                    all_players.append({**p, "_game_id": game["game_id"]})

    if not all_players:
        return None

    sorted_by_pts = sorted(all_players, key=lambda p: p["points"] or 0, reverse=True)
    sorted_by_gs  = sorted(all_players, key=lambda p: p["game_score"], reverse=True)

    pts_rank = {id(p): i for i, p in enumerate(sorted_by_pts)}
    gs_rank  = {id(p): i for i, p in enumerate(sorted_by_gs)}

    best = max(all_players, key=lambda p: pts_rank[id(p)] - gs_rank[id(p)])
    best["_pts_rank"]   = pts_rank[id(best)]
    best["_gs_rank"]    = gs_rank[id(best)]
    best["_differential"] = pts_rank[id(best)] - gs_rank[id(best)]
    return best


def attach_historical_context(games, vs=None):
    """
    For each game, query Chroma for relevant past game recaps and attach
    the results under the 'historical_context' key.
    """
    for game in games:
        home = f"{game['home_team']['city']} {game['home_team']['name']}"
        away = f"{game['away_team']['city']} {game['away_team']['name']}"
        query = f"{home} vs {away} recent performance history"
        history = retrieve_relevant_history(query, n_results=3, vs=vs)
        game["historical_context"] = history
        if history:
            print(f"  [history] Found {len(history)} relevant historical recap(s) retrieved from Chroma")
        else:
            print(f"  [history] No relevant history found in Chroma")


def run_pipeline():
    print("Fetching most recent NBA games...\n")
    games, found_date = get_games()

    if not games:
        print("No recent games found. Exiting.")
        return

    print(f"Enriching {len(games)} game(s) from {found_date} with player stats...\n")
    enriched_games = [build_full_game(g) for g in games]

    # --- Initialize Chroma once for this pipeline run ---
    vs = get_vectorstore()

    # --- Retrieve historical context from Chroma ---
    print("\nRetrieving historical context from Chroma...\n")
    attach_historical_context(enriched_games, vs=vs)

    # --- Fetch upcoming games ---
    print("Fetching upcoming NBA games...\n")
    upcoming = get_upcoming_games()
    if upcoming:
        print(f"  Found {len(upcoming)} upcoming game(s).\n")
    else:
        print("  No upcoming games found in the next 3 days.\n")

    # --- Underrated player ---
    underrated = get_underrated_player(enriched_games)

    # --- Full digest ---
    print("Generating digest...\n")
    digest_text = generate_digest(
        enriched_games, upcoming_games=upcoming, underrated_player=underrated
    )

    # --- Per-game card recaps (skip if only 1 game) ---
    card_recaps = {}
    game_cards = []
    if len(enriched_games) > 1:
        for game in enriched_games:
            home = game["home_team"]
            away = game["away_team"]
            matchup = (
                f"{away['city']} {away['name']} {away['score']}  @  "
                f"{home['city']} {home['name']} {home['score']}"
            )
            card_recap = generate_game_card_recap(game)
            game["card_recap"] = card_recap
            card_recaps[game["game_id"]] = card_recap
            game_cards.append({"matchup": matchup, "card_recap": card_recap})
    else:
        g = enriched_games[0]
        home, away = g["home_team"], g["away_team"]
        matchup = (
            f"{away['city']} {away['name']} {away['score']}  @  "
            f"{home['city']} {home['name']} {home['score']}"
        )
        card_recaps[g["game_id"]] = ""
        g["card_recap"] = ""
        game_cards.append({"matchup": matchup, "card_recap": ""})

    # --- Store tonight's recaps in Chroma ---
    print("Storing recaps to Chroma...\n")
    store_nightly_recaps(enriched_games, card_recaps, game_date=found_date)
    store_player_game_stats(enriched_games, found_date)
    total_docs = vs._collection.count()
    print(f"  Chroma collection now contains {total_docs} document(s) total.\n")

    # --- Parse digest sections into structured dict ---
    def extract_section(text, header, next_headers):
        """Extract a named section from the digest text.
        Handles Claude markdown decorators: **, ##, # before the header word.
        """
        import re
        md_prefix = r"(?:#{1,3}\s*|\*{1,2})*"
        md_suffix = r"(?:\*{1,2})?"
        pattern = md_prefix + re.escape(header) + md_suffix
        start = re.search(pattern, text, re.IGNORECASE)
        if not start:
            return ""
        content_start = start.end()
        end = len(text)
        for nxt in next_headers:
            nxt_pattern = md_prefix + re.escape(nxt) + md_suffix
            m = re.search(nxt_pattern, text[content_start:], re.IGNORECASE)
            if m:
                end = min(end, content_start + m.start())
        return text[content_start:end].strip()

    ordered_sections = [
        "STORY OF THE NIGHT",
        "PLAYERS OF THE NIGHT",
        "BY THE NUMBERS",
        "WATCH NEXT",
    ]

    story      = extract_section(digest_text, "STORY OF THE NIGHT",   ordered_sections[1:])
    players    = extract_section(digest_text, "PLAYERS OF THE NIGHT", ordered_sections[2:])
    by_numbers = extract_section(digest_text, "BY THE NUMBERS",       ordered_sections[3:])
    watch_next = extract_section(digest_text, "WATCH NEXT",           [])

    # Split BY THE NUMBERS into individual bullets, strip markdown noise
    bullets = [
        line.lstrip("•-– *").strip()
        for line in by_numbers.splitlines()
        if line.strip() and line.strip() not in ("**", "---", "*")
        and not line.strip().lower().startswith("by the numbers")
    ]
    bullets = [b for b in bullets if b]  # drop any empty strings after strip
    bullets = [re.sub(r'\*+', '', b).strip() for b in bullets]
    bullets = [b for b in bullets if b]  # drop any newly empty strings

    # Split PLAYERS OF THE NIGHT into top / underrated
    top_line        = next((l for l in players.splitlines() if "🏆" in l or l.strip().startswith("🏆")), players)
    underrated_line = next((l for l in players.splitlines() if "⭐" in l or l.strip().startswith("⭐")), "")

    def clean(text):
        import re
        # Remove isolated markdown artifacts: lines that are only **, ---, *
        lines = [l for l in text.splitlines() if l.strip() not in ("**", "---", "*", "")]
        text = "\n".join(lines).strip(" *\n-")
        # Strip all remaining bold markers
        text = re.sub(r'\*+', '', text)
        return text.strip()

    result = {
        "date":           found_date,
        "story":          clean(story),
        "players": {
            "top":        clean(top_line),
            "underrated": clean(underrated_line),
        },
        "by_the_numbers": bullets,
        "watch_next":     clean(watch_next),
        "games":          game_cards,
    }

    print(f"Pipeline complete. {len(enriched_games)} game(s) from {found_date}.")
    return result


if __name__ == "__main__":
    import json
    output = run_pipeline()
    print("\n" + "=" * 60)
    print("  STRUCTURED OUTPUT")
    print("=" * 60)
    print(json.dumps(output, indent=2, ensure_ascii=False))
