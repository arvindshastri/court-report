import warnings
warnings.filterwarnings("ignore")

from dotenv import dotenv_values
from pathlib import Path
import anthropic

config = dotenv_values(Path(__file__).parent.parent / ".env")
client = anthropic.Anthropic(api_key=config["ANTHROPIC_API_KEY"])

SYSTEM_PROMPT = (
    "You are a WNBA sports analyst writing a morning digest. "
    "For each game write exactly 3 sentences. "
    "Sentence 1: how the game unfolded — momentum shifts, turning points, quarter story. "
    "Sentence 2: the standout performer and why their performance was notable given the context. "
    "Sentence 3: one thing a casual fan would miss from just reading the final score. "
    "Be specific, be concise, do not start with the final score, do not hallucinate any stats not provided to you."
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

    return "\n".join(lines)


def generate_recap(game):
    prompt_text = format_game_for_prompt(game)

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system=SYSTEM_PROMPT,
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


def main():
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from pipeline.fetcher import get_games

    print("Fetching most recent WNBA games...\n")
    parsed, found_date = get_games()

    if not parsed:
        print("No recent games found.")
        return

    print(f"Generating recaps for {len(parsed)} game(s) from {found_date}:\n")
    print("=" * 60)

    for game in parsed:
        home = game["home_team"]
        away = game["away_team"]
        print(f"\n{away['city']} {away['name']} {away['score']}  —  "
              f"{home['city']} {home['name']} {home['score']}")
        print("-" * 60)
        recap = generate_recap(game)
        print(recap)
        print()


if __name__ == "__main__":
    main()
