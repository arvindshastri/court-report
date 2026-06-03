import warnings
warnings.filterwarnings("ignore")

from dotenv import dotenv_values
from pathlib import Path
import anthropic

config = dotenv_values(Path(__file__).parent.parent / ".env")
client = anthropic.Anthropic(api_key=config["ANTHROPIC_API_KEY"])

DIGEST_SYSTEM_PROMPT = (
    "You are Court Report, a sharp NBA morning digest. "
    "Given last night's box scores, generate a digest with exactly these sections:\n\n"
    "STORY OF THE NIGHT\n"
    "Start with one bolded sentence — the single most dramatic moment of the night. "
    "Then 2 sentences of broader context about how the night unfolded across the league.\n\n"
    "PLAYER OF THE NIGHT\n"
    "One player, the most impactful performance considering game context not just points. "
    "Format: [Name] — [stats line] | [one sentence on why this performance mattered]\n\n"
    "BY THE NUMBERS\n"
    "4 bullet points. Each is one standalone stat that needs no explanation to be impressive. "
    "Mix teams, players, and team stats. Flag career highs or season lows where relevant.\n\n"
    "WATCH TONIGHT\n"
    "One sentence. The one game worth watching tonight based on the series context, recent form, "
    "or rivalry. Include tip-off time if available.\n\n"
    "Rules: be specific, be concise, do not hallucinate any stats not in the data provided, "
    "do not use filler phrases like wire-to-wire or dominant performance. "
    "Where historical context is provided, reference it to make comparisons. "
    "If a player is performing above or below their historical norm, say so explicitly."
)

GAME_CARD_SYSTEM_PROMPT = (
    "Write exactly 2 sentences about this NBA game. "
    "Sentence 1: how the game unfolded with specific reference to quarter momentum. "
    "Sentence 2: the one stat or moment a casual fan would miss from the final score alone. "
    "Be specific, no filler."
)


def _format_player_row(p):
    fg_pct = f"{p['fg_pct']:.1%}" if p["fg_pct"] is not None else "N/A"
    pm = f"{p['plus_minus']:+.0f}" if p.get("plus_minus") is not None else "N/A"
    return (
        f"  {p['name']:25s} "
        f"PTS {p['points']:3}  REB {p['rebounds']:3}  AST {p['assists']:2}  "
        f"STL {p['steals']:2}  BLK {p['blocks']:2}  FG% {fg_pct}  +/- {pm}"
    )


def format_game_for_prompt(game):
    home = game["home_team"]
    away = game["away_team"]
    gl   = game["game_leaders"]
    sl   = game["season_leaders"]

    quarters = [f"Q{i+1}" for i in range(len(home["quarters"]))]
    q_labels = "  ".join(quarters)
    away_q   = "  ".join(str(s) for s in away["quarters"])
    home_q   = "  ".join(str(s) for s in home["quarters"])

    lines = [
        f"MATCHUP: {away['city']} {away['name']} ({away['wins']}-{away['losses']}) "
        f"@ {home['city']} {home['name']} ({home['wins']}-{home['losses']})",

        f"FINAL SCORE: {away['tricode']} {away['score']}  —  {home['tricode']} {home['score']}",

        f"\nQUARTER SCORES:",
        f"  {'':>10}   {q_labels}",
        f"  {away['tricode']:>10}:  {away_q}",
        f"  {home['tricode']:>10}:  {home_q}",

        f"\nGAME LEADERS:",
        f"  {away['tricode']} — {gl['away']['name']}: "
        f"{gl['away']['points']} PTS, {gl['away']['rebounds']} REB, {gl['away']['assists']} AST",
        f"  {home['tricode']} — {gl['home']['name']}: "
        f"{gl['home']['points']} PTS, {gl['home']['rebounds']} REB, {gl['home']['assists']} AST",

        f"\nSEASON AVERAGE LEADERS:",
        f"  {away['tricode']} — {sl['away']['name']}: "
        f"{sl['away']['points']} PPG, {sl['away']['rebounds']} RPG, {sl['away']['assists']} APG",
        f"  {home['tricode']} — {sl['home']['name']}: "
        f"{sl['home']['points']} PPG, {sl['home']['rebounds']} RPG, {sl['home']['assists']} APG",
    ]

    if "player_stats" in game:
        ps = game["player_stats"]
        lines.append(f"\nTOP PERFORMERS — {away['city']} {away['name']} ({away['tricode']}):")
        for p in ps.get("away_players", [])[:5]:
            lines.append(_format_player_row(p))
        lines.append(f"\nTOP PERFORMERS — {home['city']} {home['name']} ({home['tricode']}):")
        for p in ps.get("home_players", [])[:5]:
            lines.append(_format_player_row(p))

    return "\n".join(lines)


def format_all_games_for_digest(games):
    sections = []
    for i, game in enumerate(games, start=1):
        home = game["home_team"]
        away = game["away_team"]
        gl   = game["game_leaders"]
        ps   = game.get("player_stats", {})

        quarters = [f"Q{j+1}" for j in range(len(home["quarters"]))]
        q_labels = "  ".join(quarters)
        away_q   = "  ".join(str(s) for s in away["quarters"])
        home_q   = "  ".join(str(s) for s in home["quarters"])

        lines = [
            f"--- GAME {i}: {away['tricode']} @ {home['tricode']} ---",
            f"{away['city']} {away['name']} ({away['wins']}-{away['losses']})  "
            f"{away['score']}  @  "
            f"{home['city']} {home['name']} ({home['wins']}-{home['losses']})  "
            f"{home['score']}",

            f"\nQUARTER SCORES:",
            f"  {'':>10}   {q_labels}",
            f"  {away['tricode']:>10}:  {away_q}",
            f"  {home['tricode']:>10}:  {home_q}",

            f"\nGAME LEADERS:",
            f"  {away['tricode']} — {gl['away']['name']}: "
            f"{gl['away']['points']} PTS, {gl['away']['rebounds']} REB, {gl['away']['assists']} AST",
            f"  {home['tricode']} — {gl['home']['name']}: "
            f"{gl['home']['points']} PTS, {gl['home']['rebounds']} REB, {gl['home']['assists']} AST",
        ]

        if ps:
            lines.append(f"\nTOP PERFORMERS — {away['tricode']}:")
            for p in ps.get("away_players", [])[:5]:
                lines.append(_format_player_row(p))
            lines.append(f"\nTOP PERFORMERS — {home['tricode']}:")
            for p in ps.get("home_players", [])[:5]:
                lines.append(_format_player_row(p))

        history = game.get("historical_context", [])
        if history:
            lines.append("\nHISTORICAL CONTEXT:")
            for j, doc in enumerate(history, 1):
                lines.append(f"  [{j}] {doc}")

        sections.append("\n".join(lines))

    return "\n\n".join(sections)


def generate_digest(games):
    prompt_text = format_all_games_for_digest(games)

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        system=DIGEST_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt_text}],
    )

    return message.content[0].text


def generate_game_card_recap(game):
    prompt_text = format_game_for_prompt(game)

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=250,
        system=GAME_CARD_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt_text}],
    )

    return message.content[0].text


def format_recap_for_storage(game, recap_text, game_date):
    home = game["home_team"]
    away = game["away_team"]
    away_full = f"{away['city']} {away['name']}"
    home_full  = f"{home['city']} {home['name']}"
    final = f"{away['score']}-{home['score']}"

    return (
        f"Game: {away_full} vs {home_full} | "
        f"Date: {game_date} | "
        f"Final: {final} | "
        f"Recap: {recap_text.strip()}"
    )
