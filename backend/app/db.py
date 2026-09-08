"""SQLite database schema and connection management."""

import sqlite3
import os
import json
from contextlib import contextmanager
from typing import Generator

from app.config import settings

# Ensure data directory exists
os.makedirs(os.path.dirname(settings.database_path), exist_ok=True)

SCHEMA_VERSION = 1

SCHEMA_SQL = """
-- Documents table
CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    sha256 TEXT UNIQUE NOT NULL,
    page_count INTEGER,
    file_size INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    status TEXT NOT NULL DEFAULT 'processing'
);

-- Chunks table
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL REFERENCES documents(doc_id),
    page INTEGER NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    is_table INTEGER NOT NULL DEFAULT 0,
    text TEXT NOT NULL,
    token_count INTEGER,
    embedding BLOB
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_chunks_page ON chunks(doc_id, page);

-- Entities table (canonical entities)
CREATE TABLE IF NOT EXISTS entities (
    entity_id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    normalized TEXT NOT NULL,
    embedding BLOB,
    fact_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_entities_normalized ON entities(normalized);

-- Entity aliases table
CREATE TABLE IF NOT EXISTS entity_aliases (
    alias_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL REFERENCES entities(entity_id),
    surface_form TEXT NOT NULL,
    doc_id TEXT REFERENCES documents(doc_id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_aliases_entity ON entity_aliases(entity_id);
CREATE INDEX IF NOT EXISTS idx_aliases_surface ON entity_aliases(surface_form);

-- Predicates table (canonical predicates — the evolving schema)
CREATE TABLE IF NOT EXISTS predicates (
    pred_id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    normalized TEXT NOT NULL,
    embedding BLOB,
    fact_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_predicates_normalized ON predicates(normalized);

-- Facts table
CREATE TABLE IF NOT EXISTS facts (
    fact_id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL REFERENCES documents(doc_id),
    chunk_id TEXT NOT NULL REFERENCES chunks(chunk_id),
    subject_raw TEXT NOT NULL,
    subject_canonical_id TEXT REFERENCES entities(entity_id),
    predicate_raw TEXT NOT NULL,
    predicate_canonical_id TEXT REFERENCES predicates(pred_id),
    object_type TEXT NOT NULL CHECK(object_type IN ('quantity', 'date', 'entity', 'status', 'text')),
    object_value TEXT NOT NULL,  -- JSON
    qualifiers TEXT NOT NULL DEFAULT '{}',  -- JSON
    evidence TEXT NOT NULL,  -- JSON: {doc_id, page, char_start, char_end, bbox, quote}
    confidence REAL NOT NULL DEFAULT 0.5,
    extractor TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_facts_doc ON facts(doc_id);
CREATE INDEX IF NOT EXISTS idx_facts_subject ON facts(subject_canonical_id);
CREATE INDEX IF NOT EXISTS idx_facts_predicate ON facts(predicate_canonical_id);
CREATE INDEX IF NOT EXISTS idx_facts_type ON facts(object_type);
CREATE INDEX IF NOT EXISTS idx_facts_subject_predicate ON facts(subject_canonical_id, predicate_canonical_id);

-- FTS5 virtual table for full-text search over facts
CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
    subject_raw, predicate_raw, evidence_quote, content=facts, content_rowid=rowid
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS facts_ai AFTER INSERT ON facts BEGIN
    INSERT INTO facts_fts(rowid, subject_raw, predicate_raw, evidence_quote)
    VALUES (new.rowid, new.subject_raw, new.predicate_raw,
            json_extract(new.evidence, '$.quote'));
END;
CREATE TRIGGER IF NOT EXISTS facts_ad AFTER DELETE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, subject_raw, predicate_raw, evidence_quote)
    VALUES ('delete', old.rowid, old.subject_raw, old.predicate_raw,
            json_extract(old.evidence, '$.quote'));
END;

-- Relations table
CREATE TABLE IF NOT EXISTS relations (
    relation_id TEXT PRIMARY KEY,
    fact_id_a TEXT NOT NULL REFERENCES facts(fact_id),
    fact_id_b TEXT NOT NULL REFERENCES facts(fact_id),
    verdict TEXT NOT NULL CHECK(verdict IN (
        'CORROBORATES', 'CONTRADICTS', 'RECONCILED_BY_CONTEXT', 'SUPERSEDED', 'UNRELATED'
    )),
    rule_id TEXT NOT NULL,  -- integer string for deterministic rules, 'llm' for adjudicated
    reason TEXT NOT NULL,
    confidence REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_relations_verdict ON relations(verdict);
CREATE INDEX IF NOT EXISTS idx_relations_fact_a ON relations(fact_id_a);
CREATE INDEX IF NOT EXISTS idx_relations_fact_b ON relations(fact_id_b);

-- Rejected facts table (Case 4: extraction/reasoning failures)
CREATE TABLE IF NOT EXISTS rejected_facts (
    rejected_id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL REFERENCES documents(doc_id),
    chunk_id TEXT REFERENCES chunks(chunk_id),
    raw_output TEXT NOT NULL,  -- JSON: the raw LLM output
    reason TEXT NOT NULL,
    details TEXT,  -- JSON: additional context about the rejection
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_rejected_doc ON rejected_facts(doc_id);
CREATE INDEX IF NOT EXISTS idx_rejected_reason ON rejected_facts(reason);

-- Qualifier registry (tracks observed qualifier keys — schema evolution)
CREATE TABLE IF NOT EXISTS qualifier_registry (
    key TEXT PRIMARY KEY,
    count INTEGER NOT NULL DEFAULT 1,
    first_seen TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Jobs table (async processing state)
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL REFERENCES documents(doc_id),
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK(status IN ('queued', 'parsing', 'chunking', 'extracting',
                         'grounding', 'canonicalizing', 'reconciling', 'done', 'failed')),
    stage TEXT,
    progress REAL DEFAULT 0.0,
    chunks_total INTEGER DEFAULT 0,
    chunks_done INTEGER DEFAULT 0,
    facts_found INTEGER DEFAULT 0,
    errors TEXT NOT NULL DEFAULT '[]',  -- JSON array
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_jobs_doc ON jobs(doc_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);

-- LLM cache table
CREATE TABLE IF NOT EXISTS llm_cache (
    cache_key TEXT PRIMARY KEY,
    prompt_version TEXT NOT NULL,
    response TEXT NOT NULL,  -- JSON
    model TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def get_connection() -> sqlite3.Connection:
    """Create a new SQLite connection with recommended settings."""
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for database connections."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize the database schema."""
    with get_db() as conn:
        conn.executescript(SCHEMA_SQL)
        # Set schema version
        conn.execute(
            "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )
    print(f"Database initialized at {settings.database_path} (schema v{SCHEMA_VERSION})")


def dict_from_row(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a plain dictionary."""
    return dict(row) if row else None
