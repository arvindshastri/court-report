import warnings
warnings.filterwarnings("ignore")

import sys
from pathlib import Path
from datetime import date
import chromadb

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import dotenv_values
from pipeline.claude_recap import format_recap_for_storage

config = dotenv_values(Path(__file__).parent.parent / ".env")

PROJECT_ROOT = Path(__file__).parent.parent
CHROMA_PATH  = PROJECT_ROOT / "data" / "chroma_db"


def init_collection():
    """
    Creates a persistent Chroma client stored at data/chroma_db and
    returns the 'court_report_history' collection (created if needed).
    """
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection = client.get_or_create_collection(name="court_report_history")
    return collection


def store_game_recap(game, recap_text, game_date=None):
    """
    Store a single game recap in Chroma.
    Skips silently if the document ID already exists.
    """
    if game_date is None:
        game_date = date.today().isoformat()

    game_id  = game["game_id"]
    home     = game["home_team"]
    away     = game["away_team"]
    doc_id   = f"game_{game_id}_{game_date}"

    document = format_recap_for_storage(game, recap_text, game_date)

    metadata = {
        "game_id":      game_id,
        "date":         game_date,
        "home_team":    f"{home['city']} {home['name']}",
        "away_team":    f"{away['city']} {away['name']}",
        "home_score":   int(home["score"]) if home["score"] not in (None, "") else 0,
        "away_score":   int(away["score"]) if away["score"] not in (None, "") else 0,
        "home_record":  f"{home['wins']}-{home['losses']}",
        "away_record":  f"{away['wins']}-{away['losses']}",
    }

    collection = init_collection()

    # Check for existing document
    existing = collection.get(ids=[doc_id])
    if existing["ids"]:
        print(f"  [skip] Already stored: {doc_id}")
        return

    collection.add(
        documents=[document],
        metadatas=[metadata],
        ids=[doc_id],
    )
    print(f"  [stored] {doc_id}  |  {away['tricode']} {away['score']} @ {home['tricode']} {home['score']}")


def retrieve_relevant_history(query, n_results=3):
    """
    Query the collection for the most relevant past game recaps.
    Returns a list of matching document strings.
    """
    collection = init_collection()

    if collection.count() == 0:
        print("  [info] No history available yet — collection is empty.")
        return []

    results = collection.query(
        query_texts=[query],
        n_results=min(n_results, collection.count()),
    )

    documents = results.get("documents", [[]])[0]
    return documents


def delete_document(doc_id):
    """
    Delete a single document from the collection by its ID.
    Prints a confirmation or a warning if the ID was not found.
    """
    collection = init_collection()
    existing = collection.get(ids=[doc_id])
    if not existing["ids"]:
        print(f"  [warn] Document not found, nothing deleted: {doc_id}")
        return
    collection.delete(ids=[doc_id])
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

        # Enrich with player stats
        time.sleep(0.6)
        game["player_stats"] = get_player_stats(game["game_id"])

        # Generate card recap
        recap = generate_game_card_recap(game)
        print(f"  Recap generated.")

        # Store in Chroma
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

    # Clean up fake test document
    print("\nRemoving fake test document...\n")
    delete_document("game_TEST001_2025-06-10")

    collection = init_collection()
    print(f"\n  Collection now contains {collection.count()} document(s).")
