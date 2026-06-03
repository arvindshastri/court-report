import warnings
warnings.filterwarnings("ignore")

from dotenv import dotenv_values
from pathlib import Path
from nba_api.stats.endpoints import ScoreboardV3, BoxScoreTraditionalV3
from datetime import date, timedelta
import time

config = dotenv_values(Path(__file__).parent.parent / ".env")


def get_games(game_date=None):
    """
    Fetch completed NBA games for a given date string (YYYY-MM-DD).
    If no date is provided, search backwards from yesterday up to 14 days
    until at least one Final game is found.
    Returns (parsed_games, date_str) or ([], None) if nothing found.
    """
    if game_date:
        scoreboard = ScoreboardV3(game_date=game_date, league_id="00")
        games = scoreboard.get_dict()["scoreboard"]["games"]
        return parse_games(games), game_date

    for days_back in range(1, 15):
        check_date = date.today() - timedelta(days=days_back)
        date_str = check_date.strftime("%Y-%m-%d")
        print(f"  Checking {date_str}...")
        scoreboard = ScoreboardV3(game_date=date_str, league_id="00")
        games = scoreboard.get_dict()["scoreboard"]["games"]
        final_games = [g for g in games if g["gameStatusText"].strip().lower() == "final"]
        if final_games:
            print(f"  Found {len(final_games)} completed game(s) on {date_str}.\n")
            return parse_games(final_games), date_str

    print("  No completed NBA games found in the last 14 days.")
    return [], None


def parse_games(games):
    parsed = []
    for g in games:
        def team_dict(t):
            quarters = [p["score"] for p in sorted(t.get("periods", []), key=lambda p: p["period"])]
            return {
                "city":     t["teamCity"],
                "name":     t["teamName"],
                "tricode":  t["teamTricode"],
                "score":    t["score"],
                "wins":     t["wins"],
                "losses":   t["losses"],
                "quarters": quarters,
            }

        def leader_dict(side, leader_type):
            key = "homeLeaders" if side == "home" else "awayLeaders"
            block = g.get(leader_type, {}).get(key, {})
            return {
                "name":     block.get("name", "N/A"),
                "tricode":  block.get("teamTricode", "N/A"),
                "points":   block.get("points"),
                "rebounds": block.get("rebounds"),
                "assists":  block.get("assists"),
            }

        parsed.append({
            "game_id": g["gameId"],
            "status":  g["gameStatusText"],
            "label":   g.get("gameLabel", ""),
            "home_team": team_dict(g["homeTeam"]),
            "away_team": team_dict(g["awayTeam"]),
            "game_leaders": {
                "home": leader_dict("home", "gameLeaders"),
                "away": leader_dict("away", "gameLeaders"),
            },
            "season_leaders": {
                "home": leader_dict("home", "teamLeaders"),
                "away": leader_dict("away", "teamLeaders"),
            },
        })
    return parsed


def print_games(parsed_games):
    for g in parsed_games:
        home = g["home_team"]
        away = g["away_team"]
        gl   = g["game_leaders"]
        sl   = g["season_leaders"]

        label = f"  [{g['label']}]" if g["label"] else ""
        print("=" * 60)
        print(f"  {g['status']}{label}  |  Game ID: {g['game_id']}")
        print(f"  {away['city']} {away['name']} ({away['wins']}-{away['losses']})  @  "
              f"{home['city']} {home['name']} ({home['wins']}-{home['losses']})")
        print()

        # Final score
        print(f"  FINAL:  {away['tricode']} {away['score']}  —  {home['tricode']} {home['score']}")

        # Quarter scores
        away_q = "  ".join(str(s) for s in away["quarters"])
        home_q = "  ".join(str(s) for s in home["quarters"])
        labels = "  ".join(f"Q{i+1}" for i in range(len(home["quarters"])))
        print(f"\n  Quarters:   {labels}")
        print(f"  {away['tricode']:>10}:   {away_q}")
        print(f"  {home['tricode']:>10}:   {home_q}")

        # Game leaders
        print(f"\n  GAME LEADERS:")
        for side, team in [("Away", "away"), ("Home", "home")]:
            ldr = gl[team]
            print(f"    {side} ({ldr['tricode']})  {ldr['name']:20s}"
                  f"  PTS {ldr['points']}  REB {ldr['rebounds']}  AST {ldr['assists']}")

        # Season leaders
        print(f"\n  SEASON LEADERS (averages):")
        for side, team in [("Away", "away"), ("Home", "home")]:
            ldr = sl[team]
            print(f"    {side} ({ldr['tricode']})  {ldr['name']:20s}"
                  f"  PTS {ldr['points']}  REB {ldr['rebounds']}  AST {ldr['assists']}")
        print()

    print("=" * 60)
    print(f"  {len(parsed_games)} games on this date.")
    print("=" * 60)


def get_player_stats(game_id):
    """
    Fetch individual player stats for a given game_id from BoxScoreTraditionalV3.
    Returns {'home_players': [...], 'away_players': [...]} sorted by points descending.
    Only includes players who actually played (minutes not None or '0:00').
    """
    time.sleep(0.6)
    box = BoxScoreTraditionalV3(game_id=game_id)
    data = box.get_dict()["boxScoreTraditional"]

    def parse_players(team_data):
        players = []
        for p in team_data.get("players", []):
            s = p.get("statistics", {})
            minutes = s.get("minutes")
            if not minutes or minutes in ("PT00M00.00S", "0:00"):
                continue
            players.append({
                "name":          f"{p.get('firstName', '')} {p.get('familyName', '')}".strip(),
                "team_tricode":  team_data.get("teamTricode"),
                "minutes":       minutes,
                "points":        s.get("points"),
                "rebounds":      s.get("reboundsTotal"),
                "assists":       s.get("assists"),
                "steals":        s.get("steals"),
                "blocks":        s.get("blocks"),
                "fg_made":       s.get("fieldGoalsMade"),
                "fg_attempted":  s.get("fieldGoalsAttempted"),
                "fg_pct":        s.get("fieldGoalsPercentage"),
                "fg3_made":      s.get("threePointersMade"),
                "fg3_attempted": s.get("threePointersAttempted"),
                "turnovers":     s.get("turnovers"),
                "ft_made":       s.get("freeThrowsMade"),
                "ft_attempted":  s.get("freeThrowsAttempted"),
                "ft_pct":        s.get("freeThrowsPercentage"),
                "personal_fouls": s.get("foulsPersonal"),
                "plus_minus":    s.get("plusMinusPoints"),
            })
        return sorted(players, key=lambda p: p["points"] or 0, reverse=True)

    return {
        "home_players": parse_players(data["homeTeam"]),
        "away_players": parse_players(data["awayTeam"]),
    }


if __name__ == "__main__":
    import sys, io

    parsed, found_date = get_games()

    if not parsed:
        sys.exit(0)

    output_path = Path(__file__).parent / "scoreboard_parsed.txt"
    buffer = io.StringIO()
    sys.stdout = buffer
    print_games(parsed)
    sys.stdout = sys.__stdout__
    output_path.write_text(buffer.getvalue(), encoding="utf-8")
    print(f"Parsed output written to {output_path} (games from {found_date})")
