import warnings
warnings.filterwarnings("ignore")

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from nba_api.stats.endpoints import LeagueDashPlayerStats
from pipeline.chroma_store import store_season_averages, delete_season_averages


def fetch_season_averages(top_n=50):
    """
    Fetch per-game season averages for all NBA players in 2024-25,
    sort by points descending, and return the top N as a list of dicts.
    """
    print("Fetching 2025-26 season averages from NBA API...")
    stats = LeagueDashPlayerStats(
        season="2025-26",
        season_type_all_star="Regular Season",
        per_mode_detailed="PerGame",
        league_id_nullable="00",
        measure_type_detailed_defense="Base",
        last_n_games=0,
        month=0,
        opponent_team_id=0,
        pace_adjust="N",
        period=0,
        plus_minus="N",
        rank="N",
    )

    time.sleep(0.6)

    df = stats.get_data_frames()[0]

    df = df.sort_values("PTS", ascending=False).head(top_n)

    players = []
    for _, row in df.iterrows():
        fg_pct  = row.get("FG_PCT", 0) or 0
        fg3_pct = row.get("FG3_PCT", 0) or 0
        ft_pct  = row.get("FT_PCT", 0) or 0
        players.append({
            "player_name": row["PLAYER_NAME"],
            "team":        row["TEAM_ABBREVIATION"],
            "gp":          int(row.get("GP", 0) or 0),
            "pts":         round(float(row.get("PTS", 0) or 0), 1),
            "reb":         round(float(row.get("REB", 0) or 0), 1),
            "ast":         round(float(row.get("AST", 0) or 0), 1),
            "stl":         round(float(row.get("STL", 0) or 0), 1),
            "blk":         round(float(row.get("BLK", 0) or 0), 1),
            "fg_pct":      round(fg_pct * 100, 1),
            "fg3_pct":     round(fg3_pct * 100, 1),
            "ft_pct":      round(ft_pct * 100, 1),
        })

    print(f"  Fetched {len(players)} players (top {top_n} by PPG).\n")
    return players


if __name__ == "__main__":
    print("Deleting old 2024-25 season averages from Chroma...")
    delete_season_averages("2024-25")

    players = fetch_season_averages(top_n=50)

    print("Storing 2025-26 season averages to Chroma...")
    total_docs = store_season_averages(players, season="2025-26")

    print(f"\nDone. Chroma collection now contains {total_docs} document(s) total.")
