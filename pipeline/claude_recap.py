import warnings
warnings.filterwarnings("ignore")

from dotenv import dotenv_values
from pathlib import Path
import anthropic

config = dotenv_values(Path(__file__).parent.parent / ".env")
client = anthropic.Anthropic(api_key=config["ANTHROPIC_API_KEY"])

DIGEST_SYSTEM_PROMPT = (
    "CRITICAL: You MUST output each section with its exact header text on its own line in ALL CAPS, "
    "exactly as shown below. Do not skip, rename, or reformat any header. "
    "The headers must appear exactly as: STORY OF THE NIGHT, PLAYERS OF THE NIGHT, BY THE NUMBERS, WATCH NEXT. "
    "If any header is missing the output cannot be parsed.\n\n"
    "You are Court Report, a sharp NBA morning digest. "
    "Given last night's box scores, generate a digest with exactly these sections:\n\n"
    "STORY OF THE NIGHT\n"
    "Start with one bolded sentence — the single most dramatic moment of the night. "
    "Then 2 sentences of broader context about how the night unfolded across the league. "
    "If only one game is provided, the STORY OF THE NIGHT serves as the complete recap — "
    "do not generate a separate game card section.\n\n"
    "PLAYERS OF THE NIGHT\n"
    "Always use this exact section header. Two entries, always in this order:\n"
    "🏆 [Top performer by game score] — [stats line] | [one sentence on why their performance mattered]\n"
    "⭐ [Underrated player] — [stats line] | Underrated: [one sentence explaining the gap between their points rank and impact score rank]\n\n"
    "BY THE NUMBERS\n"
    "4 bullet points. Each must be 20 words or fewer. Lead with the number, then the player "
    "or team name, then one short clause of context. "
    "Example: 28.6% FG: Victor Wembanyama — worst shooting performance of the series. "
    "Mix teams, players, and team stats. Flag career highs or season lows where relevant.\n\n"
    "WATCH NEXT\n"
    "One sentence. The one upcoming game worth watching based on series context, recent form, "
    "or rivalry. Reference the UPCOMING GAMES data provided. Include the date if available.\n\n"
    "Rules: be specific, be concise, do not hallucinate any stats not in the data provided, "
    "do not use filler phrases like wire-to-wire or dominant performance. "
    "Always refer to players by their full first and last name. Only use a title or descriptor "
    "if it is a specific verified accolade such as reigning MVP or reigning DPOY. "
    "Never use vague references like 'their star' or 'the team's best player'. "
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


def _format_player_highlight(label, player):
    """Format a single player highlight line for the digest prompt."""
    fg_pct = f"{player['fg_pct']:.1%}" if player.get("fg_pct") is not None else "N/A"
    pm = f"{player['plus_minus']:+.0f}" if player.get("plus_minus") is not None else "N/A"
    gs = player.get("game_score")
    gs_str = f"GS {gs}" if gs is not None else ""
    pts_rank = player.get("_pts_rank")
    gs_rank = player.get("_gs_rank")
    rank_str = ""
    if pts_rank is not None and gs_rank is not None:
        rank_str = f"  [Points rank #{pts_rank+1}, Impact rank #{gs_rank+1}]"
    return (
        f"  {label}: {player['name']} ({player['team_tricode']})  "
        f"PTS {player['points']}  REB {player['rebounds']}  AST {player['assists']}  "
        f"STL {player['steals']}  BLK {player['blocks']}  FG% {fg_pct}  +/- {pm}  {gs_str}{rank_str}"
    )


def format_all_games_for_digest(games, upcoming_games=None, underrated_player=None):
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

    full_prompt = "\n\n".join(sections)

    # Best performer by game score across all games
    all_players = []
    for game in games:
        ps = game.get("player_stats", {})
        for side in ("home_players", "away_players"):
            for p in ps.get(side, []):
                if p.get("game_score") is not None:
                    all_players.append(p)

    if all_players:
        best = max(all_players, key=lambda p: p["game_score"])
        full_prompt += "\n\n--- PLAYER RECOGNITION ---"
        full_prompt += "\n" + _format_player_highlight("BEST PERFORMER", best)
        if underrated_player:
            full_prompt += "\n" + _format_player_highlight("UNDERRATED PERFORMER", underrated_player)

    if upcoming_games:
        upcoming_lines = ["\n--- UPCOMING GAMES ---"]
        for u in upcoming_games:
            upcoming_lines.append(
                f"  {u['away_tricode']} @ {u['home_tricode']}  |  "
                f"{u['away_team']} vs {u['home_team']}  |  "
                f"{u['scheduled_date']}  {u.get('game_status_text', '')}".rstrip()
            )
        full_prompt += "\n" + "\n".join(upcoming_lines)

    return full_prompt


def generate_digest(games, upcoming_games=None, underrated_player=None):
    prompt_text = format_all_games_for_digest(
        games, upcoming_games=upcoming_games, underrated_player=underrated_player
    )

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


def generate_chat_response(question, context, history, last_night_context=''):
    CHAT_SYSTEM_PROMPT = (
        "You are Court Report, a sharp NBA analyst. Answer the user's question using only the "
        "context provided from recent games and conversation history. Be specific and concise — "
        "2-3 sentences maximum. If the context doesn't contain enough information to answer, "
        "say so honestly rather than guessing. "
        "If the user refers to a player by nickname, abbreviation, or first name only, use your "
        "knowledge of the NBA to identify the full player name being referenced, then find that "
        "player in the provided context. "
        "The game data provided is accurate and current — do not question or second-guess the dates "
        "in the context. Treat all provided data as ground truth regardless of the date. "
        "When the user says 'last night' or 'recently', interpret this as referring to the most "
        "recent game in the provided context, regardless of the actual date."
    )

    messages = []
    for msg in history[-6:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    if last_night_context:
        full_context = (
            f"LAST NIGHT'S GAME DATA (use this first for any questions about recent games):\n"
            f"{last_night_context}\n\n"
            f"HISTORICAL CONTEXT FROM CHROMA:\n{context}"
        )
    else:
        full_context = context

    user_content = f"{full_context}\n\nQuestion: {question}"
    messages.append({"role": "user", "content": user_content})

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            system=CHAT_SYSTEM_PROMPT,
            messages=messages,
        )
        return response.content[0].text
    except Exception as e:
        raise RuntimeError(f"Anthropic API call failed: {e}") from e


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
