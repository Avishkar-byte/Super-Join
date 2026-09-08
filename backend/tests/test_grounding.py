"""Unit tests for Stage 4 Grounding and Quote Verification."""

import pytest
import json
from app.db import init_db, get_db
from app.extract.grounding import ground_facts


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_knowledge.db"
    monkeypatch.setattr("app.config.settings.database_path", str(db_file))
    init_db()


def test_grounding_accepted_quote():
    raw_facts = [{
        "chunk_id": "c1",
        "subject": {"raw": "Acme Corp"},
        "predicate": {"raw": "total revenue"},
        "object": {"type": "quantity", "value": 100.0, "raw": "100 crore"},
        "qualifiers": {"period": "FY24"},
        "quote": "Acme Corp reported total revenue of 100 crore in FY24.",
        "confidence": 0.9,
    }]
    chunks = [{
        "chunk_id": "c1",
        "doc_id": "d1",
        "page": 1,
        "char_start": 0,
        "char_end": 100,
        "text": "Acme Corp reported total revenue of 100 crore in FY24.",
    }]

    with get_db() as conn:
        conn.execute("INSERT INTO documents (doc_id, filename, sha256) VALUES ('d1', 'f.pdf', 'hash1')")
        conn.execute("INSERT INTO chunks (chunk_id, doc_id, page, char_start, char_end, text) VALUES ('c1', 'd1', 1, 0, 100, 'text')")

    verified = ground_facts("d1", raw_facts, chunks)
    assert len(verified) == 1
    assert verified[0]["subject_raw"] == "Acme Corp"


def test_grounding_rejected_fabricated_quote():
    raw_facts = [{
        "chunk_id": "c1",
        "subject": {"raw": "Acme Corp"},
        "predicate": {"raw": "total revenue"},
        "object": {"type": "quantity", "value": 500.0, "raw": "500 crore"},
        "qualifiers": {"period": "FY24"},
        "quote": "This statement is completely fabricated and absent from chunk text.",
        "confidence": 0.9,
    }]
    chunks = [{
        "chunk_id": "c1",
        "doc_id": "d1",
        "page": 1,
        "char_start": 0,
        "char_end": 100,
        "text": "Acme Corp reported total revenue of 100 crore in FY24.",
    }]

    with get_db() as conn:
        conn.execute("INSERT INTO documents (doc_id, filename, sha256) VALUES ('d1', 'f.pdf', 'hash1')")
        conn.execute("INSERT INTO chunks (chunk_id, doc_id, page, char_start, char_end, text) VALUES ('c1', 'd1', 1, 0, 100, 'text')")

    verified = ground_facts("d1", raw_facts, chunks)
    assert len(verified) == 0

    with get_db() as conn:
        rejected = conn.execute("SELECT * FROM rejected_facts WHERE doc_id = 'd1'").fetchall()
        assert len(rejected) == 1
        assert rejected[0]["reason"] == "ungrounded_quote"
