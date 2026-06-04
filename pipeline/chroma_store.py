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


def retrieve_relevant_history(query, n_results=3):
    """
    Query the vectorstore for the most semantically similar past recaps.
    Returns a list of matching document strings.
    """
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
