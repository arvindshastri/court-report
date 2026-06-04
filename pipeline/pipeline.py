import warnings
warnings.filterwarnings("ignore")

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


def attach_historical_context(games):
    """
    For each game, query Chroma for relevant past game recaps and attach
    the results under the 'historical_context' key.
    """
    for game in games:
        home = f"{game['home_team']['city']} {game['home_team']['name']}"
        away = f"{game['away_team']['city']} {game['away_team']['name']}"
        query = f"{home} vs {away} recent performance history"
        history = retrieve_relevant_history(query, n_results=3)
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

    # --- Retrieve historical context from Chroma ---
    print("\nRetrieving historical context from Chroma...\n")
    attach_historical_context(enriched_games)

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
    digest = generate_digest(
        enriched_games, upcoming_games=upcoming, underrated_player=underrated
    )

    print("=" * 60)
    print(f"  COURT REPORT  |  {found_date}")
    print("=" * 60)
    print(digest)
    print()

    # --- Per-game card recaps (skip if only 1 game) ---
    card_recaps = {}
    if len(enriched_games) > 1:
        print("=" * 60)
        print("  GAME CARDS")
        print("=" * 60)

        for game in enriched_games:
            home = game["home_team"]
            away = game["away_team"]
            header = (
                f"{away['city']} {away['name']} {away['score']}  @  "
                f"{home['city']} {home['name']} {home['score']}"
            )
            card_recap = generate_game_card_recap(game)
            game["card_recap"] = card_recap
            card_recaps[game["game_id"]] = card_recap

            print(f"\n{header}")
            print("-" * 60)
            print(card_recap)
        print()
    else:
        # Single game — use digest as the card recap for storage
        g = enriched_games[0]
        card_recaps[g["game_id"]] = digest
        g["card_recap"] = digest

    # --- Store tonight's recaps in Chroma ---
    print("=" * 60)
    print("  STORING RECAPS TO CHROMA")
    print("=" * 60)
    store_nightly_recaps(enriched_games, card_recaps, game_date=found_date)

    # --- Collection size summary ---
    total_docs = get_vectorstore()._collection.count()
    print(f"\n  Chroma collection now contains {total_docs} document(s) total.")

    print()
    print("=" * 60)
    print(f"  Pipeline complete. {len(enriched_games)} game(s) from {found_date}.")
    print("=" * 60)


if __name__ == "__main__":
    run_pipeline()
