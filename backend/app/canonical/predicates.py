"""Predicate Canonicalization Engine (The Evolving Schema Registry).

Normalizes raw predicates, maps them to canonical predicate IDs,
and updates the predicate registry.

Three tiers (mirrors entity canonicalization in app/canonical/entities.py):
1. Exact normalized string match -> auto merge.
2. Fuzzy similarity > AUTO_MERGE_THRESHOLD -> auto merge.
3. Fuzzy similarity in [LLM_BAND_MIN, AUTO_MERGE_THRESHOLD) -> LLM adjudicator
   decides, since financial line items are often the same concept under very
   different wording (e.g. "revenue from contract with customers" vs
   "consolidated revenue from operations") — fuzzy string distance alone
   cannot tell that apart from genuinely distinct metrics ("total revenue"
   vs "total income" scores similarly high despite being different lines).
4. Below LLM_BAND_MIN -> mint new predicate.
"""

import re
import uuid
import asyncio
import logging
from typing import List, Dict, Any
from rapidfuzz import fuzz

from app.db import get_db
from app.llm.gemini import GeminiProvider
from app.llm.groq import GroqProvider
from app.extract.prompts import PREDICATE_ADJUDICATION_SYSTEM_PROMPT, PREDICATE_ADJUDICATION_USER_PROMPT

logger = logging.getLogger(__name__)

# Fuzzy-match score bands (0-100) gating LLM adjudication.
AUTO_MERGE_THRESHOLD = 92
LLM_BAND_MIN = 40

gemini_provider = GeminiProvider()
groq_provider = GroqProvider()


def normalize_predicate(raw_pred: str) -> str:
    """Normalize raw predicate string."""
    if not raw_pred:
        return ""
    text = raw_pred.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def canonicalize_predicates(doc_id: str, facts: List[Dict[str, Any]]):
    """Canonicalize predicates across extracted facts and update facts table."""
    asyncio.run(_canonicalize_predicates_async(doc_id, facts))


async def _canonicalize_predicates_async(doc_id: str, facts: List[Dict[str, Any]]):
    with get_db() as conn:
        for fact in facts:
            pred_raw = fact["predicate_raw"]
            norm_pred = normalize_predicate(pred_raw)
            if not norm_pred:
                continue

            # Tier 1: Exact normalized match
            existing = conn.execute(
                "SELECT pred_id FROM predicates WHERE normalized = ?", (norm_pred,)
            ).fetchone()

            if not existing:
                # Tier 2 & 3: score against every existing predicate (cheap,
                # in-memory) and only ever consult the LLM on the single best
                # match, and only when it falls in the ambiguous band.
                all_preds = conn.execute("SELECT pred_id, normalized FROM predicates").fetchall()
                best_id, best_score = None, -1.0
                for row in all_preds:
                    score = fuzz.ratio(norm_pred, row["normalized"])
                    if score > best_score:
                        best_id, best_score = row["pred_id"], score

                if best_id is not None:
                    if best_score >= AUTO_MERGE_THRESHOLD:
                        existing = {"pred_id": best_id}
                    elif best_score >= LLM_BAND_MIN:
                        best_row = next(r for r in all_preds if r["pred_id"] == best_id)
                        is_same = await _adjudicate_predicates_llm(pred_raw, best_row["normalized"])
                        if is_same:
                            existing = {"pred_id": best_id}

            if existing:
                pred_id = existing["pred_id"]
                conn.execute(
                    "UPDATE predicates SET fact_count = fact_count + 1 WHERE pred_id = ?",
                    (pred_id,),
                )
            else:
                # Mint new predicate (schema evolution)
                pred_id = f"p_{uuid.uuid4().hex[:8]}"
                conn.execute(
                    """INSERT INTO predicates (pred_id, canonical_name, normalized, fact_count)
                       VALUES (?, ?, ?, 1)""",
                    (pred_id, pred_raw.strip().lower(), norm_pred),
                )

            # Link fact
            conn.execute(
                "UPDATE facts SET predicate_canonical_id = ? WHERE fact_id = ?",
                (pred_id, fact["fact_id"]),
            )


async def _adjudicate_predicates_llm(pred_a: str, pred_b: str) -> bool:
    """Ask LLM adjudicator if two predicate names refer to the same underlying metric."""
    prompt = PREDICATE_ADJUDICATION_USER_PROMPT.format(pred_a=pred_a, pred_b=pred_b)
    try:
        res = await gemini_provider.generate_json(
            prompt=prompt, system_instruction=PREDICATE_ADJUDICATION_SYSTEM_PROMPT
        )
        return bool(res.get("same", False))
    except Exception as e:
        logger.warning(f"Gemini predicate adjudication failed: {e}. Trying Groq fallback.")
        try:
            res = await groq_provider.generate_json(
                prompt=prompt, system_instruction=PREDICATE_ADJUDICATION_SYSTEM_PROMPT
            )
            return bool(res.get("same", False))
        except Exception as fallback_err:
            logger.error(f"Groq predicate adjudication fallback failed as well: {fallback_err}")
            return False
