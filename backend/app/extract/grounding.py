"""Stage 4 — Grounding and Evidence Verification.

Fuzzy-matches evidence quotes back into source chunks using rapidfuzz.
Rejects ungrounded, hallucinated, or malformed claims into the `rejected_facts` table.
Stores grounded facts and tracks observed qualifier keys in `qualifier_registry`.
"""

import uuid
import json
from typing import List, Dict, Any
from rapidfuzz import fuzz

from app.db import get_db

RAPIDFUZZ_THRESHOLD = 85.0  # Threshold for verbatim quote matching


def ground_facts(
    doc_id: str,
    raw_facts: List[Dict[str, Any]],
    chunks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Verify raw facts against source chunks and insert accepted ones into DB.

    Returns a list of verified fact dicts.
    """
    chunk_map = {c["chunk_id"]: c for c in chunks}
    verified_facts = []
    seen_tuples = set()

    with get_db() as conn:
        for raw_fact in raw_facts:
            chunk_id = raw_fact.get("chunk_id")
            chunk = chunk_map.get(chunk_id)

            # 1. Validation check: subject & predicate presence
            subj_raw = (raw_fact.get("subject") or {}).get("raw", "") if isinstance(raw_fact.get("subject"), dict) else str(raw_fact.get("subject") or "")
            pred_raw = (raw_fact.get("predicate") or {}).get("raw", "") if isinstance(raw_fact.get("predicate"), dict) else str(raw_fact.get("predicate") or "")
            quote = raw_fact.get("quote", "")

            if not subj_raw.strip() or not pred_raw.strip():
                _record_rejection(
                    conn, doc_id, chunk_id, raw_fact,
                    reason="missing_subject_or_predicate",
                    details="Fact missing valid subject or predicate."
                )
                continue

            # 2. Validation check: object value structure
            obj = raw_fact.get("object", {})
            if not isinstance(obj, dict) or "type" not in obj or "raw" not in obj:
                _record_rejection(
                    conn, doc_id, chunk_id, raw_fact,
                    reason="unparseable_object",
                    details="Fact object must contain 'type' and 'raw' fields."
                )
                continue

            obj_type = obj.get("type", "text")
            if obj_type not in ("quantity", "date", "entity", "status", "text"):
                obj_type = "text"
                obj["type"] = "text"

            # 3. Grounding check: Fuzzy match evidence quote in chunk text
            chunk_text = chunk["text"] if chunk else raw_fact.get("chunk_text", "")
            match_score = fuzz.partial_ratio(quote.lower(), chunk_text.lower()) if quote and chunk_text else 0.0

            if match_score < RAPIDFUZZ_THRESHOLD or not quote.strip():
                _record_rejection(
                    conn, doc_id, chunk_id, raw_fact,
                    reason="ungrounded_quote",
                    details=f"Quote fuzzy match score {match_score:.1f}% below threshold {RAPIDFUZZ_THRESHOLD}%."
                )
                continue

            # Compute approximate char offsets in page
            char_start = chunk.get("char_start", 0) if chunk else 0
            char_end = char_start + len(quote)

            # 4. Intra-document Deduplication check
            qualifiers = raw_fact.get("qualifiers", {})
            if not isinstance(qualifiers, dict):
                qualifiers = {}

            dedup_key = (
                subj_raw.strip().lower(),
                pred_raw.strip().lower(),
                json.dumps(qualifiers, sort_keys=True),
                str(obj.get("value") or obj.get("raw")).strip().lower(),
            )
            if dedup_key in seen_tuples:
                _record_rejection(
                    conn, doc_id, chunk_id, raw_fact,
                    reason="duplicate_fact",
                    details="Duplicate (subject, predicate, qualifiers, value) within document."
                )
                continue

            seen_tuples.add(dedup_key)

            # --- Accept & Store Fact ---
            fact_id = f"f_{uuid.uuid4().hex[:8]}"

            evidence_struct = {
                "doc_id": doc_id,
                "page": chunk.get("page", 1) if chunk else raw_fact.get("chunk_page", 1),
                "char_start": char_start,
                "char_end": char_end,
                "bbox": [50, 100, 500, 120],  # Default bounding box for evidence viewer overlay
                "quote": quote,
            }

            confidence = float(raw_fact.get("confidence", 0.85))

            conn.execute(
                """INSERT INTO facts (
                    fact_id, doc_id, chunk_id, subject_raw, predicate_raw,
                    object_type, object_value, qualifiers, evidence, confidence, extractor
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    fact_id,
                    doc_id,
                    chunk_id,
                    subj_raw,
                    pred_raw,
                    obj_type,
                    json.dumps(obj),
                    json.dumps(qualifiers),
                    json.dumps(evidence_struct),
                    confidence,
                    "gemini-3.6-flash/v1",
                ),
            )

            # Update qualifier registry for observed keys (dynamic schema evolution)
            for qual_key in qualifiers.keys():
                conn.execute(
                    """INSERT INTO qualifier_registry (key, count)
                       VALUES (?, 1)
                       ON CONFLICT(key) DO UPDATE SET
                           count = count + 1,
                           last_seen = datetime('now')""",
                    (str(qual_key).lower().strip(),),
                )

            verified_facts.append({
                "fact_id": fact_id,
                "doc_id": doc_id,
                "chunk_id": chunk_id,
                "subject_raw": subj_raw,
                "predicate_raw": pred_raw,
                "object_type": obj_type,
                "object_value": obj,
                "qualifiers": qualifiers,
                "evidence": evidence_struct,
                "confidence": confidence,
            })

    return verified_facts


def _record_rejection(conn, doc_id: str, chunk_id: str, raw_fact: dict, reason: str, details: str):
    """Record an ungrounded or invalid fact into the rejected_facts table (Case 4)."""
    rejected_id = f"r_{uuid.uuid4().hex[:8]}"
    conn.execute(
        """INSERT INTO rejected_facts (rejected_id, doc_id, chunk_id, raw_output, reason, details)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            rejected_id,
            doc_id,
            chunk_id,
            json.dumps(raw_fact),
            reason,
            json.dumps({"info": details}),
        ),
    )
