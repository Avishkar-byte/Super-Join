"""Three-tier Entity Canonicalization Engine.

1. Deterministic normalization (strip corporate suffixes, address terms, punctuation).
2. Vector similarity (similarity > 0.95 -> auto merge).
3. LLM Adjudicator (0.80 - 0.95 band).
4. Mint new entity (< 0.80).
"""

import re
import uuid
import asyncio
import logging
import numpy as np
from typing import List, Dict, Any
from rapidfuzz import fuzz

from app.db import get_db
from app.llm.gemini import GeminiProvider
from app.llm.groq import GroqProvider
from app.extract.prompts import ENTITY_ADJUDICATION_SYSTEM_PROMPT, ENTITY_ADJUDICATION_USER_PROMPT

logger = logging.getLogger(__name__)

# Fuzzy-match score bands (0-100) gating LLM adjudication, per class docstring above.
AUTO_MERGE_THRESHOLD = 95
LLM_BAND_MIN = 80

gemini_provider = GeminiProvider()
groq_provider = GroqProvider()


def normalize_entity_name(raw_name: str) -> str:
    """Normalize raw entity string for deterministic matching."""
    if not raw_name:
        return ""
    text = raw_name.lower().strip()

    # Strip corporate suffixes
    suffixes = [
        r"\bpvt\.?\b", r"\bltd\.?\b", r"\blimited\b", r"\binc\.?\b",
        r"\bllp\b", r"\bcorp\.?\b", r"\bcorporation\b", r"\bco\.?\b"
    ]
    for suf in suffixes:
        text = re.sub(suf, "", text)

    # Normalize address tokens
    text = re.sub(r"\broad\b", "rd", text)
    text = re.sub(r"\bstreet\b", "st", text)
    text = re.sub(r"\bnumber\b", "no", text)

    # Strip punctuation and collapse whitespace
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def canonicalize_entities(doc_id: str, facts: List[Dict[str, Any]]):
    """Canonicalize subjects across extracted facts and update facts table."""
    asyncio.run(_canonicalize_entities_async(doc_id, facts))


async def _canonicalize_entities_async(doc_id: str, facts: List[Dict[str, Any]]):
    with get_db() as conn:
        for fact in facts:
            subj_raw = fact["subject_raw"]
            norm_name = normalize_entity_name(subj_raw)
            if not norm_name:
                continue

            # Tier 1: Exact normalized match
            existing = conn.execute(
                "SELECT entity_id, canonical_name FROM entities WHERE normalized = ?", (norm_name,)
            ).fetchone()

            if existing:
                entity_id = existing["entity_id"]
                _link_fact_to_entity(conn, fact["fact_id"], entity_id, subj_raw, doc_id)
                continue

            # Tier 2 & 3: Check against existing entities
            all_entities = conn.execute("SELECT entity_id, canonical_name, normalized FROM entities").fetchall()

            matched_id = None
            if all_entities:
                # Score every candidate once (cheap, in-memory) and only ever
                # consult the LLM on the single best match, and only when it
                # falls in the ambiguous band. Avoids one LLM call per
                # substring-overlapping entity in the whole DB.
                best_ent, best_score = None, -1.0
                for ent in all_entities:
                    score = fuzz.ratio(norm_name, ent["normalized"])
                    if score > best_score:
                        best_ent, best_score = ent, score

                if best_ent is not None:
                    if best_score >= AUTO_MERGE_THRESHOLD:
                        matched_id = best_ent["entity_id"]
                    elif best_score >= LLM_BAND_MIN:
                        is_same = await _adjudicate_entities_llm(subj_raw, best_ent["canonical_name"])
                        if is_same:
                            matched_id = best_ent["entity_id"]

            if matched_id:
                entity_id = matched_id
            else:
                # Tier 4: Mint new entity
                entity_id = f"e_{uuid.uuid4().hex[:8]}"
                conn.execute(
                    """INSERT INTO entities (entity_id, canonical_name, normalized, fact_count)
                       VALUES (?, ?, ?, 1)""",
                    (entity_id, subj_raw.title(), norm_name),
                )

            _link_fact_to_entity(conn, fact["fact_id"], entity_id, subj_raw, doc_id)


def _link_fact_to_entity(conn, fact_id: str, entity_id: str, surface_form: str, doc_id: str):
    """Link fact to entity, add surface form as alias, and increment fact_count."""
    conn.execute(
        "UPDATE facts SET subject_canonical_id = ? WHERE fact_id = ?", (entity_id, fact_id)
    )
    conn.execute(
        "UPDATE entities SET fact_count = fact_count + 1 WHERE entity_id = ?", (entity_id,)
    )
    conn.execute(
        """INSERT INTO entity_aliases (entity_id, surface_form, doc_id)
           VALUES (?, ?, ?)""",
        (entity_id, surface_form, doc_id),
    )


async def _adjudicate_entities_llm(name_a: str, name_b: str) -> bool:
    """Ask LLM adjudicator if two entity names refer to the same real-world entity."""
    prompt = ENTITY_ADJUDICATION_USER_PROMPT.format(
        name_a=name_a, context_a="Extracted document claim",
        name_b=name_b, context_b="Existing knowledge layer entity"
    )
    try:
        res = await gemini_provider.generate_json(
            prompt=prompt, system_instruction=ENTITY_ADJUDICATION_SYSTEM_PROMPT
        )
        return bool(res.get("same", False))
    except Exception as e:
        logger.warning(f"Gemini entity adjudication failed: {e}. Trying Groq fallback.")
        try:
            res = await groq_provider.generate_json(
                prompt=prompt, system_instruction=ENTITY_ADJUDICATION_SYSTEM_PROMPT
            )
            return bool(res.get("same", False))
        except Exception as fallback_err:
            logger.error(f"Groq entity adjudication fallback failed as well: {fallback_err}")
            return False
