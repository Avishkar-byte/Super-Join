"""Table-driven unit tests for every row of the reconciliation rule engine."""

import pytest
import json
from app.reconcile.rules import evaluate_pair_rules


def _make_fact(fact_id, subject, predicate, object_type, value, raw_val, qualifiers):
    return {
        "fact_id": fact_id,
        "doc_id": "d_test",
        "subject_raw": subject,
        "predicate_raw": predicate,
        "object_type": object_type,
        "object_value": json.dumps({"type": object_type, "value": value, "raw": raw_val}),
        "qualifiers": json.dumps(qualifiers),
        "evidence": json.dumps({"quote": "test quote"}),
    }


def test_rule_1_corroborates_equal_values():
    f_a = _make_fact("f1", "Acme", "revenue", "quantity", 1000.0, "1,000", {"period": "FY24"})
    f_b = _make_fact("f2", "Acme", "revenue", "quantity", 1004.0, "1,004", {"period": "FY24"})  # within 0.5%
    verdict, rule_id, reason, _ = evaluate_pair_rules(f_a, f_b)
    assert verdict == "CORROBORATES"
    assert rule_id == "rule_1"


def test_rule_2_reconciled_disjoint_periods():
    f_a = _make_fact("f1", "Acme", "revenue", "quantity", 1000.0, "1,000", {"period": "FY23"})
    f_b = _make_fact("f2", "Acme", "revenue", "quantity", 1500.0, "1,500", {"period": "FY24"})
    verdict, rule_id, reason, _ = evaluate_pair_rules(f_a, f_b)
    assert verdict == "RECONCILED_BY_CONTEXT"
    assert rule_id == "rule_2"


def test_rule_3_reconciled_scale_mismatch():
    f_a = _make_fact("f1", "Acme", "revenue", "quantity", 10000000.0, "10 million", {"period": "FY24"})
    f_b = _make_fact("f2", "Acme", "revenue", "quantity", 100.0, "100 lakh", {"period": "FY24"})
    verdict, rule_id, reason, _ = evaluate_pair_rules(f_a, f_b)
    assert verdict in ("CORROBORATES", "RECONCILED_BY_CONTEXT")


def test_rule_4_superseded_state_predicate():
    f_a = _make_fact("f1", "John Doe", "director status", "status", None, "active", {"as_of": "2022-01-01"})
    f_b = _make_fact("f2", "John Doe", "director status", "status", None, "resigned", {"as_of": "2024-01-01"})
    verdict, rule_id, reason, _ = evaluate_pair_rules(f_a, f_b)
    assert verdict == "SUPERSEDED"
    assert rule_id == "rule_4"


def test_rule_5_contradicts_overlapping_period():
    f_a = _make_fact("f1", "Acme", "revenue", "quantity", 1000.0, "1,000", {"period": "FY24", "scope": "consolidated"})
    f_b = _make_fact("f2", "Acme", "revenue", "quantity", 2500.0, "2,500", {"period": "FY24", "scope": "consolidated"})
    verdict, rule_id, reason, _ = evaluate_pair_rules(f_a, f_b)
    assert verdict == "CONTRADICTS"
    assert rule_id == "rule_5"
