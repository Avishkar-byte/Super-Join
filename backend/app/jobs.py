"""Async job management for document processing."""

import uuid
import json
from datetime import datetime, timezone

from app.db import get_db


def create_job(doc_id: str) -> str:
    """Create a new processing job and return its ID."""
    job_id = f"j_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO jobs (job_id, doc_id, status, stage, progress,
               chunks_total, chunks_done, facts_found, errors, created_at, updated_at)
               VALUES (?, ?, 'queued', 'queued', 0.0, 0, 0, 0, '[]', ?, ?)""",
            (job_id, doc_id, now, now),
        )
    return job_id


def update_job(
    job_id: str,
    status: str = None,
    stage: str = None,
    progress: float = None,
    chunks_total: int = None,
    chunks_done: int = None,
    facts_found: int = None,
    error: str = None,
):
    """Update job state. Only non-None fields are updated."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        # Get current state
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if not row:
            return

        new_status = status or row["status"]
        new_stage = stage or row["stage"]
        new_progress = progress if progress is not None else row["progress"]
        new_chunks_total = chunks_total if chunks_total is not None else row["chunks_total"]
        new_chunks_done = chunks_done if chunks_done is not None else row["chunks_done"]
        new_facts_found = facts_found if facts_found is not None else row["facts_found"]

        errors = json.loads(row["errors"])
        if error:
            errors.append(error)

        conn.execute(
            """UPDATE jobs SET status=?, stage=?, progress=?, chunks_total=?,
               chunks_done=?, facts_found=?, errors=?, updated_at=?
               WHERE job_id=?""",
            (
                new_status, new_stage, new_progress, new_chunks_total,
                new_chunks_done, new_facts_found, json.dumps(errors), now, job_id,
            ),
        )


def get_job(job_id: str) -> dict:
    """Get job state."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["errors"] = json.loads(result["errors"])
        return result
