"""Deterministic Rule Engine for Fact Reconciliation.

Evaluates candidate pairs in priority order (first match wins):
1. Values equal after normalization (with 0.5% numeric tolerance) -> CORROBORATES (rule_1)
2. State predicate (status/role/appointment) & as_of differs -> SUPERSEDED (rule_4)
3. Values differ, qualifier intervals disjoint -> RECONCILED_BY_CONTEXT (rule_2)
4. Values differ, scale ratio ≈ 1e2/1e3/1e5/1e7 -> RECONCILED_BY_CONTEXT (rule_3)
5. Values differ, qualifiers overlap -> CONTRADICTS (rule_5)
6. Undecided -> LLM Adjudicator (rule_6 / llm)
"""

import uuid
import json
import asyncio
from typing import List, Dict, Any, Tuple

from app.db import get_db
from app.canonical.dates import parse_date_interval, are_intervals_disjoint
from app.reconcile.adjudicator import adjudicate_relation_llm

NUMERIC_TOLERANCE = 0.005  # 0.5% numerical rounding tolerance


def evaluate_pair_rules(fact_a: dict, fact_b: dict) -> Tuple[str, str, str, float]:
    """Evaluate deterministic rules for two facts.

    Returns: (verdict, rule_id, reason, confidence)
    """
    obj_a = json.loads(fact_a["object_value"]) if isinstance(fact_a["object_value"], str) else fact_a["object_value"]
    obj_b = json.loads(fact_b["object_value"]) if isinstance(fact_b["object_value"], str) else fact_b["object_value"]
    quals_a = json.loads(fact_a["qualifiers"]) if isinstance(fact_a["qualifiers"], str) else fact_a["qualifiers"]
    quals_b = json.loads(fact_b["qualifiers"]) if isinstance(fact_b["qualifiers"], str) else fact_b["qualifiers"]

    val_a = obj_a.get("value")
    val_b = obj_b.get("value")
    raw_a = str(obj_a.get("raw") or "").strip().lower()
    raw_b = str(obj_b.get("raw") or "").strip().lower()

    # Extract date/period intervals from qualifiers
    period_a = quals_a.get("period") or quals_a.get("as_of") or quals_a.get("date")
    period_b = quals_b.get("period") or quals_b.get("as_of") or quals_b.get("date")
    int_a = parse_date_interval(str(period_a)) if period_a else {}
    int_b = parse_date_interval(str(period_b)) if period_b else {}

    # ─── RULE 1: Values Equal ────────────────────────────────────────────────
    if val_a is not None and val_b is not None and isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
        if val_a != 0 and abs(val_a - val_b) / abs(val_a) <= NUMERIC_TOLERANCE:
            return "CORROBORATES", "rule_1", "Values match within 0.5% tolerance.", 0.95
        elif val_a == 0 and val_b == 0:
            return "CORROBORATES", "rule_1", "Both values are zero.", 0.95
    elif raw_a and raw_a == raw_b:
        return "CORROBORATES", "rule_1", "Raw object strings match exactly.", 0.90

    # ─── RULE 4 (Priority over disjoint rule for state predicates): State Predicate & Superceding Date ───
    pred_raw = fact_a["predicate_raw"].lower()
    is_state_pred = any(term in pred_raw for term in ("status", "role", "appointment", "director", "address", "active"))
    if is_state_pred and period_a and period_b and (int_a.get("end") != int_b.get("end")):
        newer_label = int_a.get("label") if int_a.get("end", "") > int_b.get("end", "") else int_b.get("label")
        return (
            "SUPERSEDED",
            "rule_4",
            f"State predicate updated; newer status ({newer_label}) supersedes older record.",
            0.88,
        )

    # ─── RULE 2: Disjoint Qualifier Intervals ────────────────────────────────
    if period_a and period_b and are_intervals_disjoint(int_a, int_b):
        return (
            "RECONCILED_BY_CONTEXT",
            "rule_2",
            f"Apparent difference explained by disjoint time periods ({int_a.get('label')} vs {int_b.get('label')}).",
            0.92,
        )

    # ─── RULE 3: Scale / Unit Mismatch Ratio (1e2, 1e3, 1e5, 1e7) ───────────
    if val_a is not None and val_b is not None and isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
        if val_a != 0 and val_b != 0:
            ratio = max(abs(val_a), abs(val_b)) / min(abs(val_a), abs(val_b))
            for scale in (100.0, 1000.0, 1e5, 1e7):
                if abs(ratio - scale) / scale <= 0.05:  # Within 5% of scale ratio
                    return (
                        "RECONCILED_BY_CONTEXT",
                        "rule_3",
                        f"Difference explained by unit scale mismatch (ratio ≈ {scale:g}).",
                        0.90,
                    )

    # ─── RULE 5: Overlapping Qualifiers & Conflicting Values ─────────────────
    if (
        (int_a.get("start") and int_b.get("start") and not are_intervals_disjoint(int_a, int_b))
        or (quals_a.get("scope") and quals_b.get("scope") and quals_a["scope"] == quals_b["scope"])
    ):
        return (
            "CONTRADICTS",
            "rule_5",
            "Facts conflict over overlapping period/scope.",
            0.85,
        )

    # ─── RULE 6: Undecided Residue -> LLM Adjudicator ───────────────────────
    return "LLM_REQUIRED", "rule_6", "Requires LLM context adjudication.", 0.5


def apply_rules(candidate_pairs: List[Tuple[dict, dict]]):
    """Apply rules to candidate pairs and record relations in SQLite."""
    asyncio.run(_apply_rules_async(candidate_pairs))


async def _apply_rules_async(candidate_pairs: List[Tuple[dict, dict]]):
    with get_db() as conn:
        for fact_a, fact_b in candidate_pairs:
            existing = conn.execute(
                """SELECT relation_id FROM relations
                   WHERE (fact_id_a = ? AND fact_id_b = ?)
                      OR (fact_id_a = ? AND fact_id_b = ?)""",
                (fact_a["fact_id"], fact_b["fact_id"], fact_b["fact_id"], fact_a["fact_id"]),
            ).fetchone()

            if existing:
                continue

            verdict, rule_id, reason, conf = evaluate_pair_rules(fact_a, fact_b)

            if verdict == "LLM_REQUIRED":
                verdict, reason, conf = await adjudicate_relation_llm(fact_a, fact_b)
                rule_id = "llm"

            relation_id = f"r_{uuid.uuid4().hex[:8]}"
            conn.execute(
                """INSERT INTO relations (relation_id, fact_id_a, fact_id_b, verdict, rule_id, reason, confidence)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (relation_id, fact_a["fact_id"], fact_b["fact_id"], verdict, rule_id, reason, conf),
            )
