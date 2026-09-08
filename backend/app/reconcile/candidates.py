"""Candidate Linking Engine.

Buckets facts by (subject_canonical_id, predicate_canonical_id) to avoid naive O(N^2) comparison.
Reports candidate reduction ratio.
"""

from typing import List, Dict, Any, Tuple
from app.db import get_db


def find_candidates(doc_id: str) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """Find candidate fact pairs for reconciliation.

    Compares facts from doc_id against all existing facts in the system.
    Only pairs sharing subject & predicate (or normalized forms) are evaluated.
    """
    candidate_pairs = []

    with get_db() as conn:
        # Get all facts in document
        doc_facts = conn.execute(
            "SELECT * FROM facts WHERE doc_id = ?", (doc_id,)
        ).fetchall()

        # Get all other facts in database
        other_facts = conn.execute(
            "SELECT * FROM facts WHERE doc_id != ?", (doc_id,)
        ).fetchall()

        if not doc_facts or not other_facts:
            return []

        # Index existing facts by (subject_key, predicate_key)
        buckets: Dict[Tuple[str, str], List[dict]] = {}
        for f in other_facts:
            subj_key = f["subject_canonical_id"] or f["subject_raw"].lower().strip()
            pred_key = f["predicate_canonical_id"] or f["predicate_raw"].lower().strip()
            bucket_key = (subj_key, pred_key)
            if bucket_key not in buckets:
                buckets[bucket_key] = []
            buckets[bucket_key].append(dict(f))

        # Match document facts against buckets
        for df in doc_facts:
            doc_fact_dict = dict(df)
            subj_key = df["subject_canonical_id"] or df["subject_raw"].lower().strip()
            pred_key = df["predicate_canonical_id"] or df["predicate_raw"].lower().strip()
            bucket_key = (subj_key, pred_key)

            matching_other_facts = buckets.get(bucket_key, [])
            for of in matching_other_facts:
                candidate_pairs.append((doc_fact_dict, of))

    return candidate_pairs
