import json
import time
import sys
import io
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.claude_recap import client, DIGEST_SYSTEM_PROMPT
from pipeline.fetcher import get_games, get_player_stats, get_upcoming_games
from pipeline.claude_recap import generate_digest, generate_game_card_recap
from pipeline.chroma_store import retrieve_relevant_history, get_vectorstore
from pipeline.pipeline import (
    build_full_game,
    calculate_game_score,
    get_underrated_player,
    attach_historical_context,
)

TEST_CASES_PATH = Path(__file__).parent / "test_cases.json"

JUDGE_SYSTEM_PROMPT = (
    "You are an expert evaluator for an NBA digest AI system. "
    "You will be given a generated digest and a list of evaluation criteria. "
    "Grade the digest on each criterion individually. "
    "Return ONLY a valid JSON object with no extra text, in this exact format: "
    '{ "criteria_scores": [ {"criterion": "...", "score": 0 or 1, "reason": "one sentence explanation"} ], '
    '"must_not_contain_violations": ["list any banned phrases found, empty list if none"], '
    '"total_score": number from 0 to 100, '
    '"summary": "2-3 sentence overall assessment" } '
    "Score each criterion as 1 (pass) or 0 (fail). "
    "Total score = (sum of criteria scores / total criteria) * 100, "
    "minus 10 points for each must_not_contain violation found."
)


def generate_digest_from_test_case(tc):
    """Generate a digest using static test case data via Haiku."""

    def _join(val):
        """Format a field value: join lists with newlines, stringify scalars."""
        if isinstance(val, list):
            return "\n".join(str(item) for item in val) if val else "(none)"
        return str(val)

    lines = []

    scalar_fields = [
        ("GAME",           "game"),
        ("DATE",           "game_date"),
        ("FINAL",          "final"),
        ("MARGIN",         "margin"),
        ("SERIES CONTEXT", "series_context"),
        ("RECORDS",        "records"),
        ("DNP",            "dnp"),
        ("QUARTER SCORES", "quarter_scores"),
        ("CONTEXT",        "context"),
    ]
    for label, key in scalar_fields:
        val = tc.get(key)
        if val is not None:
            lines.append(f"{label}: {_join(val)}")

    list_fields = [
        ("NOTABLE GAMES",      "notable_games"),
        ("NOTABLE PERFORMERS", "notable_performers"),
        ("KEY PERFORMERS",     "key_performers"),
    ]
    for label, key in list_fields:
        val = tc.get(key)
        if val is not None:
            lines.append(f"{label}:\n{_join(val)}")

    prompt = "\n".join(lines)

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        system=DIGEST_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def grade_digest(digest_text, eval_criteria, must_not_contain):
    """Call the LLM judge to score the digest."""
    numbered_criteria = "\n".join(
        f"{i+1}. {c}" for i, c in enumerate(eval_criteria)
    )
    banned = "\n".join(must_not_contain) if must_not_contain else "(none)"

    user_message = (
        f"GENERATED DIGEST:\n{digest_text}\n\n"
        f"EVALUATION CRITERIA:\n{numbered_criteria}\n\n"
        f"MUST NOT CONTAIN:\n{banned}\n\n"
        "Grade this digest against the criteria above and return the JSON score."
    )

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1500,
        system=JUDGE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    raw = message.content[0].text
    try:
        return json.loads(raw[raw.index("{") : raw.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError) as e:
        print(f"  JSON parse failed: {e}")
        print(f"  Raw judge response:\n{raw}")
        raise


def run_live_test_case(tc):
    """Run a test case using live NBA API data."""
    game_date = tc["game_date"]
    print(f"  Fetching live games for {game_date}...")

    games, _ = get_games(game_date=game_date)
    if not games:
        print(f"  WARNING: No games found for {game_date}. Skipping.")
        return None

    print(f"  Found {len(games)} game(s). Enriching with player stats...")
    enriched = [build_full_game(g) for g in games]

    vs = get_vectorstore()
    attach_historical_context(enriched, vs=vs)

    upcoming = get_upcoming_games()
    underrated = get_underrated_player(enriched)

    digest_text = generate_digest(enriched, upcoming_games=upcoming, underrated_player=underrated)

    if len(enriched) > 1:
        for game in enriched:
            generate_game_card_recap(game)

    return digest_text


def run_static_test_case(tc):
    """Run a test case using static test case data."""
    return generate_digest_from_test_case(tc)


def print_result(tc, digest_text, result):
    print(f"\n{'='*60}")
    print(f"TEST CASE: {tc['id']} — {tc['scenario']}")
    print(f"{'='*60}")

    print("\n--- GENERATED DIGEST ---")
    print(digest_text)
    print("--- END DIGEST ---\n")

    for cs in result["criteria_scores"]:
        status = "PASS" if cs["score"] == 1 else "FAIL"
        print(f"  [{status}] {cs['criterion']}")
        print(f"         {cs['reason']}")

    if result["must_not_contain_violations"]:
        print(f"\n  VIOLATIONS FOUND:")
        for v in result["must_not_contain_violations"]:
            print(f"    - \"{v}\"")
    else:
        print(f"\n  No banned phrase violations.")

    print(f"\n  SCORE: {result['total_score']:.1f}/100")
    print(f"  SUMMARY: {result['summary']}")


def build_summary_lines(summary_rows, total_cases):
    """Render the summary table as a list of strings, independent of stdout."""
    numeric_scores = [
        r["score"] for r in summary_rows if isinstance(r["score"], (int, float))
    ]

    lines = [
        "",
        "",
        "=" * 70,
        "  EVAL SUMMARY",
        "=" * 70,
        f"  {'ID':<10} {'Score':>7}  Scenario",
        f"  {'-'*8}  {'-'*7}  {'-'*45}",
    ]

    for row in summary_rows:
        score = row["score"]
        score_str = f"{score:.1f}" if isinstance(score, (int, float)) else str(score)
        lines.append(f"  {row['id']:<10} {score_str:>7}  {row['scenario']}")

    lines.append("")
    lines.append(f"  Total test cases run: {len(summary_rows)} of {total_cases}")
    lines.append(
        f"  Evaluated: {len(numeric_scores)}"
        f"  |  Skipped/Error: {len(summary_rows) - len(numeric_scores)}"
    )

    if numeric_scores:
        avg = sum(numeric_scores) / len(numeric_scores)
        best = max(summary_rows, key=lambda r: r["score"] if isinstance(r["score"], (int, float)) else -1)
        worst = min(summary_rows, key=lambda r: r["score"] if isinstance(r["score"], (int, float)) else 101)
        lines.append("")
        lines.append(f"  Average score: {avg:.1f}/100")
        lines.append(f"  Highest: {best['id']} — {best['scenario']} ({best['score']:.1f})")
        lines.append(f"  Lowest:  {worst['id']} — {worst['scenario']} ({worst['score']:.1f})")

    return lines


def main():
    with open(TEST_CASES_PATH) as f:
        test_cases = json.load(f)

    print(f"Loaded {len(test_cases)} test cases from {TEST_CASES_PATH}\n")

    summary_rows = []

    try:
        for tc in test_cases:
            tc_id = tc["id"]
            scenario = tc["scenario"]
            print(f"\nRunning {tc_id}: {scenario}")

            digest_text = None
            try:
                if tc.get("use_live_data", False):
                    digest_text = run_live_test_case(tc)
                    if digest_text is None:
                        summary_rows.append({"id": tc_id, "scenario": scenario, "score": "SKIPPED"})
                        continue
                else:
                    digest_text = run_static_test_case(tc)

                result = grade_digest(
                    digest_text,
                    tc.get("eval_criteria", []),
                    tc.get("must_not_contain", []),
                )
                print_result(tc, digest_text, result)
                summary_rows.append({
                    "id": tc_id,
                    "scenario": scenario,
                    "score": result["total_score"],
                    "result": result,
                })

            except Exception as e:
                print(f"  ERROR in {tc_id}: {e}")
                summary_rows.append({"id": tc_id, "scenario": scenario, "score": "ERROR"})

            time.sleep(1)

    finally:
        # Write summary to the current stdout (the output file while redirected)
        summary_lines = build_summary_lines(summary_rows, len(test_cases))
        for line in summary_lines:
            print(line)

    # Return rows and lines so the caller can also echo them to the real console
    return summary_rows, summary_lines, len(test_cases)


if __name__ == "__main__":
    output_dir = Path(__file__).parent / "results"
    output_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"eval_{timestamp}.txt"

    original_stdout = sys.stdout
    summary_lines = []

    with open(output_path, "w", encoding="utf-8") as f:
        tee = io.TextIOWrapper(f.buffer, encoding="utf-8") if hasattr(f, "buffer") else f
        sys.stdout = tee
        try:
            _, summary_lines, _ = main()
        finally:
            sys.stdout.flush()
            sys.stdout = original_stdout

    # Always echo the summary table to the real console after the file is closed
    print(f"\nEval results written to: {output_path}\n")
    for line in summary_lines:
        print(line)
