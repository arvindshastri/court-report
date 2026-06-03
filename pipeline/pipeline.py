import warnings
warnings.filterwarnings("ignore")

import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.fetcher import get_games, get_player_stats
from pipeline.claude_recap import generate_digest, generate_game_card_recap


def build_full_game(game):
    """
    Enrich a parsed game dict with per-player box score stats.
    Returns a new dict containing all original fields plus 'player_stats'.
    """
    time.sleep(0.6)
    player_stats = get_player_stats(game["game_id"])
    return {**game, "player_stats": player_stats}


def run_pipeline():
    print("Fetching most recent NBA games...\n")
    games, found_date = get_games()

    if not games:
        print("No recent games found. Exiting.")
        return

    print(f"Enriching {len(games)} game(s) from {found_date} with player stats...\n")
    enriched_games = [build_full_game(g) for g in games]

    # --- Full digest ---
    print("Generating digest...\n")
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

    for game in enriched_games:
        home = game["home_team"]
        away = game["away_team"]
        header = (
            f"{away['city']} {away['name']} {away['score']}  @  "
            f"{home['city']} {home['name']} {home['score']}"
        )
        card_recap = generate_game_card_recap(game)
        game["card_recap"] = card_recap

        print(f"\n{header}")
        print("-" * 60)
        print(card_recap)

    print()
    print("=" * 60)
    print(f"  Pipeline complete. {len(enriched_games)} game(s) from {found_date}.")
    print("=" * 60)


if __name__ == "__main__":
    run_pipeline()
