import warnings
warnings.filterwarnings("ignore")

import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import dotenv_values
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from pipeline.claude_recap import format_recap_for_storage

config = dotenv_values(Path(__file__).parent.parent / ".env")

PROJECT_ROOT    = Path(__file__).parent.parent
CHROMA_PATH     = str(PROJECT_ROOT / "data" / "chroma_db")
COLLECTION_NAME = "court_report_history"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def get_vectorstore():
    """
    Initialize and return a LangChain Chroma vectorstore backed by
    HuggingFace sentence-transformer embeddings, persisted to data/chroma_db.
    """
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=CHROMA_PATH,
    )
    return vectorstore


def store_game_recap(game, recap_text, game_date=None):
    """
    Store a single game recap in the vectorstore.
    Skips if a document with the same game_id and date already exists.
    """
    if game_date is None:
        game_date = date.today().isoformat()

    game_id = game["game_id"]
    home    = game["home_team"]
    away    = game["away_team"]
    doc_id  = f"game_{game_id}_{game_date}"

    document = format_recap_for_storage(game, recap_text, game_date)

    metadata = {
        "game_id":    game_id,
        "date":       game_date,
        "home_team":  f"{home['city']} {home['name']}",
        "away_team":  f"{away['city']} {away['name']}",
        "home_score": int(home["score"]) if home["score"] not in (None, "") else 0,
        "away_score": int(away["score"]) if away["score"] not in (None, "") else 0,
        "home_record": f"{home['wins']}-{home['losses']}",
        "away_record": f"{away['wins']}-{away['losses']}",
    }

    vs = get_vectorstore()

    # Duplicate check — query by game_id in metadata
    existing = vs.get(where={"game_id": game_id})
    if existing and existing.get("ids"):
        print(f"  [skip] Already stored: {doc_id}")
        return

    vs.add_texts(texts=[document], metadatas=[metadata], ids=[doc_id])
    print(f"  [stored] {doc_id}  |  {away['tricode']} {away['score']} @ {home['tricode']} {home['score']}")


def _parse_minutes(minutes_str):
    """Convert 'MM:SS' string to float minutes."""
    try:
        parts = str(minutes_str).split(":")
        return int(parts[0]) + int(parts[1]) / 60
    except Exception:
        return 0.0


def store_player_game_stats(games, game_date):
    """
    Store one Chroma document per player per game for every player who played
    more than 5 minutes. Skips duplicates by document ID.
    """
    vs = get_vectorstore()
    stored = 0
    skipped = 0

    for game in games:
        game_id   = game["game_id"]
        home_tri  = game["home_team"]["tricode"]
        away_tri  = game["away_team"]["tricode"]
        ps        = game.get("player_stats", {})

        for side in ("home_players", "away_players"):
            opponent_tri = away_tri if side == "home_players" else home_tri
            for p in ps.get(side, []):
                if _parse_minutes(p.get("minutes") or "0:00") <= 5:
                    continue

                player_name   = p["name"]
                team_tri      = p["team_tricode"]
                fg_made       = p.get("fg_made") or 0
                fg_att        = p.get("fg_attempted") or 0
                fg_pct        = p.get("fg_pct")
                fg_pct_str    = f"{fg_pct * 100:.1f}" if fg_pct is not None else "0.0"
                ft_made       = p.get("ft_made") or 0
                ft_att        = p.get("ft_attempted") or 0
                pm            = p.get("plus_minus")
                pm_str        = f"{pm:+.0f}" if pm is not None else "+0"

                document = (
                    f"{player_name} | {team_tri} vs {opponent_tri} | {game_date} | "
                    f"{p.get('points', 0)} PTS {p.get('rebounds', 0)} REB "
                    f"{p.get('assists', 0)} AST {p.get('steals', 0)} STL "
                    f"{p.get('blocks', 0)} BLK {p.get('turnovers', 0)} TO "
                    f"{fg_made}-{fg_att} FG ({fg_pct_str}%) "
                    f"{ft_made}-{ft_att} FT {pm_str} +/-"
                )

                safe_name = player_name.replace(" ", "_")
                doc_id    = f"player_{safe_name}_{game_id}"
                metadata  = {
                    "type":        "player_game",
                    "date":        game_date,
                    "player_name": player_name,
                    "team":        team_tri,
                    "game_id":     game_id,
                }

                existing = vs.get(ids=[doc_id])
                if existing and existing.get("ids"):
                    skipped += 1
                    continue

                vs.add_texts(texts=[document], metadatas=[metadata], ids=[doc_id])
                stored += 1

    print(f"  [player stats] Stored {stored} player-game document(s), skipped {skipped} duplicate(s).")


def delete_season_averages(season):
    """
    Delete all documents from Chroma where metadata type='season_averages'
    and season matches the given season string (e.g. '2025-26').
    Prints document count before and after.
    """
    vs = get_vectorstore()
    before = vs._collection.count()
    print(f"  [delete_season_averages] Total docs before: {before}")

    results = vs.get(where={"$and": [{"type": "season_averages"}, {"season": season}]})
    ids_to_delete = results.get("ids", [])

    if ids_to_delete:
        vs.delete(ids=ids_to_delete)
        print(f"  [delete_season_averages] Deleted {len(ids_to_delete)} document(s) for season {season}.")
    else:
        print(f"  [delete_season_averages] No documents found for season {season}.")

    after = vs._collection.count()
    print(f"  [delete_season_averages] Total docs after: {after}")


def store_season_averages(players, season="2025-26"):
    """
    Store one Chroma document per player containing their season averages.
    Skips duplicates by document ID.
    """
    vs = get_vectorstore()
    stored = 0
    skipped = 0

    for p in players:
        player_name = p["player_name"]
        team        = p["team"]
        gp          = p.get("gp", 0)
        pts         = p.get("pts", 0)
        reb         = p.get("reb", 0)
        ast         = p.get("ast", 0)
        stl         = p.get("stl", 0)
        blk         = p.get("blk", 0)
        fg_pct      = p.get("fg_pct", 0)
        fg3_pct     = p.get("fg3_pct", 0)
        ft_pct      = p.get("ft_pct", 0)

        document = (
            f"{player_name} | {team} | {season} season averages | "
            f"{pts} PPG {reb} RPG {ast} APG {stl} SPG {blk} BPG "
            f"{fg_pct}% FG {fg3_pct}% 3P {ft_pct}% FT | "
            f"{gp} games played"
        )

        safe_name = player_name.replace(" ", "_")
        doc_id    = f"avg_{safe_name}_{season}"
        metadata  = {
            "type":        "season_averages",
            "player_name": player_name,
            "team":        team,
            "season":      season,
        }

        existing = vs.get(ids=[doc_id])
        if existing and existing.get("ids"):
            skipped += 1
            continue

        vs.add_texts(texts=[document], metadatas=[metadata], ids=[doc_id])
        stored += 1

    print(f"  [season averages] Stored {stored} document(s), skipped {skipped} duplicate(s).")
    return vs._collection.count()


def retrieve_relevant_history(query, n_results=3, vs=None):
    """
    Query the vectorstore for the most semantically similar past recaps.
    Returns a list of matching document strings.
    Pass a pre-initialized vectorstore via `vs` to avoid reloading the embedding model.
    """
    if vs is None:
        vs = get_vectorstore()

    if vs._collection.count() == 0:
        print("  [info] No history available yet — collection is empty.")
        return []

    retriever = vs.as_retriever(search_kwargs={"k": n_results})
    results   = retriever.invoke(query)
    return [doc.page_content for doc in results]


def delete_document(doc_id):
    """
    Delete a single document from the vectorstore by its ID.
    """
    vs = get_vectorstore()
    existing = vs.get(ids=[doc_id])
    if not existing or not existing.get("ids"):
        print(f"  [warn] Document not found, nothing deleted: {doc_id}")
        return
    vs.delete(ids=[doc_id])
    print(f"  [deleted] {doc_id}")


def store_nightly_recaps(games, card_recaps, game_date=None):
    """
    Store recaps for all games from a nightly run.
    card_recaps: dict keyed by game_id -> recap string
    """
    if game_date is None:
        game_date = date.today().isoformat()

    stored = 0
    for game in games:
        game_id = game["game_id"]
        recap   = card_recaps.get(game_id, "")
        if not recap:
            print(f"  [warn] No recap found for game_id {game_id}, skipping.")
            continue
        store_game_recap(game, recap, game_date=game_date)
        stored += 1

    print(f"\n  Summary: {stored}/{len(games)} recap(s) stored for {game_date}.")


if __name__ == "__main__":
    import time
    from pipeline.fetcher import get_games, get_player_stats
    from pipeline.claude_recap import generate_game_card_recap

    # Fetch most recent real NBA games
    print("Fetching most recent NBA games...\n")
    games, found_date = get_games()

    if not games:
        print("No recent games found. Exiting.")
        sys.exit(0)

    print(f"Found {len(games)} game(s) from {found_date}. Enriching with player stats...\n")

    for game in games:
        home = game["home_team"]
        away = game["away_team"]
        print(f"  Processing: {away['tricode']} @ {home['tricode']} (game {game['game_id']})")

        time.sleep(0.6)
        game["player_stats"] = get_player_stats(game["game_id"])

        recap = generate_game_card_recap(game)
        print(f"  Recap generated.")

        store_game_recap(game, recap, game_date=found_date)
        print()

    # Query the collection
    query = "Spurs fourth quarter comeback"
    print(f"\nQuerying collection: '{query}'\n")
    results = retrieve_relevant_history(query, n_results=3)

    if results:
        for i, doc in enumerate(results, 1):
            print(f"Result {i}:\n{doc}\n")
    else:
        print("No results returned.")
