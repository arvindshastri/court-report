import warnings
warnings.filterwarnings("ignore")

import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.fetcher import get_games, get_player_stats
from pipeline.claude_recap import generate_digest, generate_game_card_recap
from pipeline.chroma_store import (
    store_game_recap,
    retrieve_relevant_history,
    store_nightly_recaps,
    init_collection,
)


def build_full_game(game):
    """
    Enrich a parsed game dict with per-player box score stats.
    Returns a new dict containing all original fields plus 'player_stats'.
    """
    time.sleep(0.6)
    player_stats = get_player_stats(game["game_id"])
    return {**game, "player_stats": player_stats}


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
            print(f"  [history] Found {len(history)} past recap(s) for {away} @ {home}")
        else:
            print(f"  [history] No prior history for {away} @ {home}")


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

    # --- Full digest ---
    print("\nGenerating digest...\n")
    digest = generate_digest(enriched_games)

    print("=" * 60)
    print(f"  COURT REPORT  |  {found_date}")
    print("=" * 60)
    print(digest)
    print()

    # --- Per-game card recaps ---
    print("=" * 60)
    print("  GAME CARDS")
    print("=" * 60)

    card_recaps = {}
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

    # --- Store tonight's recaps in Chroma ---
    print("\n")
    print("=" * 60)
    print("  STORING RECAPS TO CHROMA")
    print("=" * 60)
    store_nightly_recaps(enriched_games, card_recaps, game_date=found_date)

    # --- Collection size summary ---
    collection = init_collection()
    total_docs = collection.count()
    print(f"\n  Chroma collection now contains {total_docs} document(s) total.")

    print()
    print("=" * 60)
    print(f"  Pipeline complete. {len(enriched_games)} game(s) from {found_date}.")
    print("=" * 60)


if __name__ == "__main__":
    run_pipeline()
