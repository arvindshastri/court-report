import warnings
warnings.filterwarnings("ignore")

import sys
import json
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pipeline.pipeline import run_pipeline

app = FastAPI(title="Court Report API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CACHE_PATH = Path(__file__).parent / "data" / "digest_cache.json"


@app.get("/health")
def health():
    return {"status": "ok"}


CACHE_TTL_HOURS = 12


@app.get("/digest")
def digest():
    now = datetime.utcnow()

    # Return cache if it exists and is within the TTL window
    if CACHE_PATH.exists():
        try:
            cached = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            cached_at = datetime.fromisoformat(cached["cached_at"])
            age = now - cached_at
            if age < timedelta(hours=CACHE_TTL_HOURS):
                print(f"[cache] Returning cached digest (age: {age}, cached_at: {cached['cached_at']})")
                return {k: v for k, v in cached.items() if k != "cached_at"}
        except Exception as e:
            print(f"[cache] Could not read cache, regenerating: {e}")

    # Run pipeline and write fresh cache with timestamp
    print(f"[cache] Cache missing or expired — running pipeline")
    result = run_pipeline()
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        cache_payload = {**result, "cached_at": now.isoformat()}
        CACHE_PATH.write_text(json.dumps(cache_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[cache] Digest cached to {CACHE_PATH} at {now.isoformat()}")
    except Exception as e:
        print(f"[cache] Could not write cache: {e}")

    return result
