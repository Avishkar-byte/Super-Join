"""On-disk cache for LLM calls keyed by sha256(chunk_text + prompt_version).

Ensures repeated runs cost nothing and stay well within free tier quota.
"""

import hashlib
import json
from typing import Optional, Any
from app.db import get_db


def compute_cache_key(text: str, prompt_version: str) -> str:
    """Compute sha256 cache key."""
    combined = f"{prompt_version}:{text}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def get_cached_response(cache_key: str) -> Optional[Any]:
    """Retrieve cached response if present."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT response FROM llm_cache WHERE cache_key = ?", (cache_key,)
        ).fetchone()
        if row:
            return json.loads(row["response"])
    return None


def save_cached_response(cache_key: str, prompt_version: str, response: Any, model: str = "gemini-3.6-flash"):
    """Save response to SQLite LLM cache."""
    with get_db() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO llm_cache (cache_key, prompt_version, response, model)
               VALUES (?, ?, ?, ?)""",
            (cache_key, prompt_version, json.dumps(response), model),
        )
