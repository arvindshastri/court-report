import warnings
warnings.filterwarnings("ignore")

from dotenv import dotenv_values
from pathlib import Path
from nba_api.stats.endpoints import (
    ScoreboardV3,
    BoxScoreTraditionalV3,
    LeagueGameFinder,
    PlayerCareerStats,
)
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
        final_games = [g for g in games if g["gameStatusText"].strip().lower() == "final"]
        return parse_games(final_games), game_date

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
                "team_id":  t.get("teamId"),
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
                "person_id":     p.get("personId"),
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
                "turnovers":           s.get("turnovers"),
                "ft_made":             s.get("freeThrowsMade"),
                "ft_attempted":        s.get("freeThrowsAttempted"),
                "ft_pct":              s.get("freeThrowsPercentage"),
                "personal_fouls":      s.get("foulsPersonal"),
                "plus_minus":          s.get("plusMinusPoints"),
                "offensive_rebounds":  s.get("reboundsOffensive"),
                "defensive_rebounds":  s.get("reboundsDefensive"),
            })
        return sorted(players, key=lambda p: p["points"] or 0, reverse=True)

    return {
        "home_players": parse_players(data["homeTeam"]),
        "away_players": parse_players(data["awayTeam"]),
    }


def get_upcoming_games():
    """
    Return scheduled (not yet played) NBA games for today and the next 3 days.
    gameStatus == 1 means the game has not started yet.
    Returns a list of dicts with home_team, away_team, and scheduled_date.
    """
    upcoming = []
    for days_ahead in range(0, 4):
        check_date = date.today() + timedelta(days=days_ahead)
        date_str = check_date.strftime("%Y-%m-%d")
        try:
            scoreboard = ScoreboardV3(game_date=date_str, league_id="00")
            games = scoreboard.get_dict()["scoreboard"]["games"]
            for g in games:
                if g.get("gameStatus") == 1:
                    game_dict = {
                        "scheduled_date": date_str,
                        "home_team": g["homeTeam"]["teamCity"] + " " + g["homeTeam"]["teamName"],
                        "away_team": g["awayTeam"]["teamCity"] + " " + g["awayTeam"]["teamName"],
                        "home_tricode": g["homeTeam"]["teamTricode"],
                        "away_tricode": g["awayTeam"]["teamTricode"],
                        "game_status_text": g.get("gameStatusText", "").strip(),
                    }
                    series_game_number = g.get("seriesGameNumber")
                    if series_game_number:
                        game_dict["series_game_number"] = series_game_number
                    upcoming.append(game_dict)
        except Exception as e:
            print(f"  [warn] Could not fetch upcoming games for {date_str}: {e}")
    return upcoming


def get_series_games(home_team_id, away_team_id, season="2025-26"):
    """
    Pull all playoff games between two specific teams in a given season
    using LeagueGameFinder. Returns a list of game dicts with date, score,
    and game number.
    """
    time.sleep(0.6)
    finder = LeagueGameFinder(
        team_id_nullable=home_team_id,
        vs_team_id_nullable=away_team_id,
        season_nullable=season,
        season_type_nullable="Playoffs",
        league_id_nullable="00",
    )
    rows = finder.get_dict()["resultSets"][0]
    headers = rows["headers"]
    games = []
    for row in rows["rowSet"]:
        g = dict(zip(headers, row))
        games.append({
            "game_id":   g.get("GAME_ID"),
            "date":      g.get("GAME_DATE"),
            "matchup":   g.get("MATCHUP"),
            "wl":        g.get("WL"),
            "pts":       g.get("PTS"),
            "pts_opp":   g.get("PLUS_MINUS"),  # approximation via available fields
        })
    return games


def get_player_season_averages(player_id, season="2025-26"):
    """
    Pull season averages for a player using PlayerCareerStats.
    Returns a dict with key per-game averages for the requested season.
    """
    time.sleep(0.6)
    career = PlayerCareerStats(player_id=player_id, per_mode36="PerGame")
    data = career.get_dict()
    reg_season = next(
        (rs for rs in data["resultSets"] if rs["name"] == "SeasonTotalsRegularSeason"),
        None,
    )
    if not reg_season:
        return {}
    headers = reg_season["headers"]
    season_row = next(
        (dict(zip(headers, row)) for row in reg_season["rowSet"]
         if row[headers.index("SEASON_ID")] == season),
        None,
    )
    if not season_row:
        return {}
    return {
        "points":   season_row.get("PTS"),
        "rebounds": season_row.get("REB"),
        "assists":  season_row.get("AST"),
        "steals":   season_row.get("STL"),
        "blocks":   season_row.get("BLK"),
        "fg_pct":   season_row.get("FG_PCT"),
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
