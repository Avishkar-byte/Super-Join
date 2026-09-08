"""Fact Knowledge Layer — FastAPI Application.

A system that ingests PDFs, extracts atomic facts with verbatim evidence,
canonicalizes entities and predicates, and determines when facts corroborate,
contradict, or are reconcilable through context.
"""

import json
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.config import settings
from app.db import init_db, get_db
from app.models import (
    HealthResponse, UploadResponse, JobStatus_, DocumentSummary, DocumentDetail,
    FactListItem, FactDetail, RelationDetail, RelationSummary, EntitySummary,
    PredicateSummary, QualifierKey, RejectedFact, GraphResponse, SystemStats,
    ObjectValue, Evidence,
)
from app.jobs import create_job, get_job


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    init_db()
    yield


app = FastAPI(
    title="Fact Knowledge Layer",
    description="Extract, ground, canonicalize, and reconcile facts across documents.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
def health_check():
    return HealthResponse()


# ─── Documents ────────────────────────────────────────────────────────────────

@app.post("/documents", response_model=UploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """Upload a PDF document for processing. Returns immediately with a job_id."""
    import hashlib
    import uuid

    # Read file bytes
    file_bytes = await file.read()
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    # Check for existing document with same hash
    with get_db() as conn:
        existing = conn.execute(
            "SELECT doc_id FROM documents WHERE sha256 = ?", (file_hash,)
        ).fetchone()

        if existing:
            # Already processed — return existing doc_id, no new job needed
            doc_id = existing["doc_id"]
            # Check if there's an existing job
            job_row = conn.execute(
                "SELECT job_id FROM jobs WHERE doc_id = ? ORDER BY created_at DESC LIMIT 1",
                (doc_id,),
            ).fetchone()
            job_id = job_row["job_id"] if job_row else create_job(doc_id)
            return UploadResponse(job_id=job_id, doc_id=doc_id, cached=True)

        # New document
        doc_id = f"d_{uuid.uuid4().hex[:8]}"
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        conn.execute(
            """INSERT INTO documents (doc_id, filename, sha256, file_size, created_at, status)
               VALUES (?, ?, ?, ?, ?, 'processing')""",
            (doc_id, file.filename, file_hash, len(file_bytes), now),
        )

    job_id = create_job(doc_id)

    # Save file to disk for processing
    upload_dir = os.path.join(os.path.dirname(settings.database_path), "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{doc_id}.pdf")
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    # Launch background processing
    from app.pipeline import process_document
    background_tasks.add_task(process_document, doc_id, job_id, file_path)

    return UploadResponse(job_id=job_id, doc_id=doc_id, cached=False)


@app.get("/documents")
def list_documents():
    """List all documents with fact counts."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT d.*, COALESCE(fc.cnt, 0) as fact_count
            FROM documents d
            LEFT JOIN (SELECT doc_id, COUNT(*) as cnt FROM facts GROUP BY doc_id) fc
                ON d.doc_id = fc.doc_id
            ORDER BY d.created_at DESC
        """).fetchall()
        return [
            DocumentSummary(
                doc_id=r["doc_id"],
                filename=r["filename"],
                page_count=r["page_count"],
                file_size=r["file_size"],
                fact_count=r["fact_count"],
                status=r["status"],
                created_at=r["created_at"],
            )
            for r in rows
        ]


@app.get("/documents/{doc_id}")
def get_document(doc_id: str):
    """Get document detail with per-page fact counts."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")

        # Per-page fact counts
        page_counts = conn.execute("""
            SELECT json_extract(evidence, '$.page') as page, COUNT(*) as cnt
            FROM facts WHERE doc_id = ?
            GROUP BY page
        """, (doc_id,)).fetchall()

        fact_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM facts WHERE doc_id = ?", (doc_id,)
        ).fetchone()["cnt"]

        return DocumentDetail(
            doc_id=row["doc_id"],
            filename=row["filename"],
            sha256=row["sha256"],
            page_count=row["page_count"],
            file_size=row["file_size"],
            fact_count=fact_count,
            status=row["status"],
            created_at=row["created_at"],
            page_fact_counts={int(pc["page"]): pc["cnt"] for pc in page_counts if pc["page"]},
        )


@app.get("/documents/{doc_id}/page/{page_num}")
def get_document_page(doc_id: str, page_num: int):
    """Get rendered page image for the evidence viewer."""
    page_path = os.path.join(settings.pages_dir, doc_id, f"page_{page_num}.png")
    if not os.path.exists(page_path):
        raise HTTPException(status_code=404, detail="Page image not found")
    return FileResponse(page_path, media_type="image/png")


# ─── Jobs ─────────────────────────────────────────────────────────────────────

@app.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    """Get job processing status."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatus_(
        job_id=job["job_id"],
        doc_id=job["doc_id"],
        status=job["status"],
        stage=job["stage"],
        progress=job["progress"],
        chunks_total=job["chunks_total"],
        chunks_done=job["chunks_done"],
        facts_found=job["facts_found"],
        errors=job["errors"],
        created_at=job["created_at"],
        updated_at=job["updated_at"],
    )


# ─── Facts ────────────────────────────────────────────────────────────────────

def _parse_fact_row(row) -> dict:
    """Parse a fact row from SQLite into a structured dict."""
    obj = json.loads(row["object_value"])
    ev = json.loads(row["evidence"])
    quals = json.loads(row["qualifiers"])
    return {
        "fact_id": row["fact_id"],
        "doc_id": row["doc_id"],
        "subject_raw": row["subject_raw"],
        "subject_canonical_id": row["subject_canonical_id"],
        "predicate_raw": row["predicate_raw"],
        "predicate_canonical_id": row["predicate_canonical_id"],
        "object_type": row["object_type"],
        "object_value": ObjectValue(**obj),
        "qualifiers": quals,
        "evidence": Evidence(**ev),
        "confidence": row["confidence"],
        "extractor": row["extractor"],
        "created_at": row["created_at"],
    }


@app.get("/facts")
def list_facts(
    doc_id: Optional[str] = None,
    subject: Optional[str] = None,
    predicate: Optional[str] = None,
    object_type: Optional[str] = None,
    min_confidence: Optional[float] = None,
    q: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
):
    """List facts with filters."""
    with get_db() as conn:
        conditions = []
        params = []

        if q:
            # FTS search
            fts_sql = """
                SELECT f.* FROM facts f
                JOIN facts_fts fts ON f.rowid = fts.rowid
                WHERE facts_fts MATCH ?
            """
            params.append(q)
            if doc_id:
                fts_sql += " AND f.doc_id = ?"
                params.append(doc_id)
            fts_sql += " ORDER BY rank LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            rows = conn.execute(fts_sql, params).fetchall()
        else:
            where_parts = []
            if doc_id:
                where_parts.append("f.doc_id = ?")
                params.append(doc_id)
            if subject:
                where_parts.append("(f.subject_raw LIKE ? OR f.subject_canonical_id = ?)")
                params.extend([f"%{subject}%", subject])
            if predicate:
                where_parts.append("(f.predicate_raw LIKE ? OR f.predicate_canonical_id = ?)")
                params.extend([f"%{predicate}%", predicate])
            if object_type:
                where_parts.append("f.object_type = ?")
                params.append(object_type)
            if min_confidence is not None:
                where_parts.append("f.confidence >= ?")
                params.append(min_confidence)

            where_clause = " AND ".join(where_parts) if where_parts else "1=1"
            sql = f"""
                SELECT f.*, e.canonical_name as subject_name, p.canonical_name as predicate_name
                FROM facts f
                LEFT JOIN entities e ON f.subject_canonical_id = e.entity_id
                LEFT JOIN predicates p ON f.predicate_canonical_id = p.pred_id
                WHERE {where_clause}
                ORDER BY f.created_at DESC
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])
            rows = conn.execute(sql, params).fetchall()

        results = []
        for row in rows:
            parsed = _parse_fact_row(row)
            results.append(FactListItem(
                fact_id=parsed["fact_id"],
                doc_id=parsed["doc_id"],
                subject_raw=parsed["subject_raw"],
                subject_canonical_name=row["subject_name"] if "subject_name" in row.keys() else None,
                predicate_raw=parsed["predicate_raw"],
                predicate_canonical_name=row["predicate_name"] if "predicate_name" in row.keys() else None,
                object_type=parsed["object_type"],
                object_value=parsed["object_value"],
                qualifiers=parsed["qualifiers"],
                confidence=parsed["confidence"],
                evidence_quote=parsed["evidence"].quote,
                evidence_page=parsed["evidence"].page,
            ))
        return results


@app.get("/facts/{fact_id}")
def get_fact(fact_id: str):
    """Get a single fact with all its relations."""
    with get_db() as conn:
        row = conn.execute("""
            SELECT f.*, e.canonical_name as subject_name, p.canonical_name as predicate_name
            FROM facts f
            LEFT JOIN entities e ON f.subject_canonical_id = e.entity_id
            LEFT JOIN predicates p ON f.predicate_canonical_id = p.pred_id
            WHERE f.fact_id = ?
        """, (fact_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Fact not found")

        parsed = _parse_fact_row(row)

        # Get relations involving this fact
        rel_rows = conn.execute("""
            SELECT * FROM relations
            WHERE fact_id_a = ? OR fact_id_b = ?
        """, (fact_id, fact_id)).fetchall()

        relations = [
            RelationSummary(
                relation_id=r["relation_id"],
                fact_id_a=r["fact_id_a"],
                fact_id_b=r["fact_id_b"],
                verdict=r["verdict"],
                rule_id=r["rule_id"],
                reason=r["reason"],
                confidence=r["confidence"],
            )
            for r in rel_rows
        ]

        return FactDetail(
            **parsed,
            relations=relations,
            subject_canonical_name=row["subject_name"],
            predicate_canonical_name=row["predicate_name"],
        )


# ─── Relations ────────────────────────────────────────────────────────────────

@app.get("/relations")
def list_relations(
    verdict: Optional[str] = None,
    doc_id: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
):
    """List relations with paired facts."""
    with get_db() as conn:
        conditions = []
        params = []

        if verdict:
            conditions.append("r.verdict = ?")
            params.append(verdict)
        if doc_id:
            conditions.append("(fa.doc_id = ? OR fb.doc_id = ?)")
            params.extend([doc_id, doc_id])

        where = " AND ".join(conditions) if conditions else "1=1"

        rows = conn.execute(f"""
            SELECT r.*,
                   fa.fact_id as fa_id, fa.doc_id as fa_doc_id, fa.subject_raw as fa_subject,
                   fa.predicate_raw as fa_predicate, fa.object_type as fa_obj_type,
                   fa.object_value as fa_obj_val, fa.qualifiers as fa_quals,
                   fa.evidence as fa_evidence, fa.confidence as fa_confidence,
                   fa.extractor as fa_extractor, fa.created_at as fa_created,
                   fa.subject_canonical_id as fa_subj_canon, fa.predicate_canonical_id as fa_pred_canon,
                   fb.fact_id as fb_id, fb.doc_id as fb_doc_id, fb.subject_raw as fb_subject,
                   fb.predicate_raw as fb_predicate, fb.object_type as fb_obj_type,
                   fb.object_value as fb_obj_val, fb.qualifiers as fb_quals,
                   fb.evidence as fb_evidence, fb.confidence as fb_confidence,
                   fb.extractor as fb_extractor, fb.created_at as fb_created,
                   fb.subject_canonical_id as fb_subj_canon, fb.predicate_canonical_id as fb_pred_canon
            FROM relations r
            JOIN facts fa ON r.fact_id_a = fa.fact_id
            JOIN facts fb ON r.fact_id_b = fb.fact_id
            WHERE {where}
            ORDER BY r.created_at DESC
            LIMIT ? OFFSET ?
        """, params + [limit, offset]).fetchall()

        results = []
        for row in rows:
            fact_a_obj = json.loads(row["fa_obj_val"])
            fact_a_ev = json.loads(row["fa_evidence"])
            fact_a_quals = json.loads(row["fa_quals"])
            fact_b_obj = json.loads(row["fb_obj_val"])
            fact_b_ev = json.loads(row["fb_evidence"])
            fact_b_quals = json.loads(row["fb_quals"])

            results.append(RelationDetail(
                relation_id=row["relation_id"],
                fact_id_a=row["fact_id_a"],
                fact_id_b=row["fact_id_b"],
                verdict=row["verdict"],
                rule_id=row["rule_id"],
                reason=row["reason"],
                confidence=row["confidence"],
                fact_a=dict(
                    fact_id=row["fa_id"], doc_id=row["fa_doc_id"],
                    subject_raw=row["fa_subject"],
                    subject_canonical_id=row["fa_subj_canon"],
                    predicate_raw=row["fa_predicate"],
                    predicate_canonical_id=row["fa_pred_canon"],
                    object_type=row["fa_obj_type"],
                    object_value=ObjectValue(**fact_a_obj),
                    qualifiers=fact_a_quals,
                    evidence=Evidence(**fact_a_ev),
                    confidence=row["fa_confidence"],
                    extractor=row["fa_extractor"],
                    created_at=row["fa_created"],
                ),
                fact_b=dict(
                    fact_id=row["fb_id"], doc_id=row["fb_doc_id"],
                    subject_raw=row["fb_subject"],
                    subject_canonical_id=row["fb_subj_canon"],
                    predicate_raw=row["fb_predicate"],
                    predicate_canonical_id=row["fb_pred_canon"],
                    object_type=row["fb_obj_type"],
                    object_value=ObjectValue(**fact_b_obj),
                    qualifiers=fact_b_quals,
                    evidence=Evidence(**fact_b_ev),
                    confidence=row["fb_confidence"],
                    extractor=row["fb_extractor"],
                    created_at=row["fb_created"],
                ),
            ))
        return results


# ─── Entities ─────────────────────────────────────────────────────────────────

@app.get("/entities")
def list_entities(
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
):
    """List canonical entities with aliases."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM entities ORDER BY fact_count DESC LIMIT ? OFFSET ?
        """, (limit, offset)).fetchall()

        results = []
        for row in rows:
            aliases = conn.execute(
                "SELECT surface_form, doc_id FROM entity_aliases WHERE entity_id = ?",
                (row["entity_id"],)
            ).fetchall()
            results.append(EntitySummary(
                entity_id=row["entity_id"],
                canonical_name=row["canonical_name"],
                fact_count=row["fact_count"],
                aliases=[{"surface_form": a["surface_form"], "doc_id": a["doc_id"]} for a in aliases],
            ))
        return results


# ─── Predicates ───────────────────────────────────────────────────────────────

@app.get("/predicates")
def list_predicates(
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
):
    """List the evolving predicate registry."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM predicates ORDER BY fact_count DESC LIMIT ? OFFSET ?
        """, (limit, offset)).fetchall()
        return [
            PredicateSummary(
                pred_id=r["pred_id"],
                canonical_name=r["canonical_name"],
                fact_count=r["fact_count"],
            )
            for r in rows
        ]


# ─── Qualifiers ──────────────────────────────────────────────────────────────

@app.get("/qualifiers")
def list_qualifiers():
    """List observed qualifier keys (schema evolution view)."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM qualifier_registry ORDER BY count DESC"
        ).fetchall()
        return [
            QualifierKey(
                key=r["key"], count=r["count"],
                first_seen=r["first_seen"], last_seen=r["last_seen"],
            )
            for r in rows
        ]


# ─── Rejected Facts ──────────────────────────────────────────────────────────

@app.get("/rejected")
def list_rejected(
    doc_id: Optional[str] = None,
    reason: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
):
    """List rejected facts with reasons (Case 4)."""
    with get_db() as conn:
        conditions = []
        params = []
        if doc_id:
            conditions.append("doc_id = ?")
            params.append(doc_id)
        if reason:
            conditions.append("reason = ?")
            params.append(reason)

        where = " AND ".join(conditions) if conditions else "1=1"
        rows = conn.execute(f"""
            SELECT * FROM rejected_facts
            WHERE {where}
            ORDER BY created_at DESC LIMIT ? OFFSET ?
        """, params + [limit, offset]).fetchall()

        return [
            RejectedFact(
                rejected_id=r["rejected_id"],
                doc_id=r["doc_id"],
                chunk_id=r["chunk_id"],
                raw_output=json.loads(r["raw_output"]) if r["raw_output"] else None,
                reason=r["reason"],
                details=json.loads(r["details"]) if r["details"] else None,
                created_at=r["created_at"],
            )
            for r in rows
        ]


# ─── Graph ────────────────────────────────────────────────────────────────────

@app.get("/graph")
def get_graph():
    """Project facts + relations as a graph (nodes + edges)."""
    with get_db() as conn:
        # Get all entities as nodes
        entities = conn.execute("SELECT * FROM entities").fetchall()
        # Get all relations
        relations = conn.execute("""
            SELECT r.*, fa.subject_canonical_id as fa_subj, fb.subject_canonical_id as fb_subj
            FROM relations r
            JOIN facts fa ON r.fact_id_a = fa.fact_id
            JOIN facts fb ON r.fact_id_b = fb.fact_id
        """).fetchall()

        nodes = [
            {
                "id": e["entity_id"],
                "label": e["canonical_name"],
                "type": "entity",
                "metadata": {"fact_count": e["fact_count"]},
            }
            for e in entities
        ]

        edges = []
        for r in relations:
            edges.append({
                "source": r["fact_id_a"],
                "target": r["fact_id_b"],
                "label": r["verdict"],
                "verdict": r["verdict"],
                "metadata": {"rule_id": r["rule_id"], "reason": r["reason"]},
            })

        return GraphResponse(nodes=nodes, edges=edges)


# ─── Stats ────────────────────────────────────────────────────────────────────

@app.get("/stats")
def get_stats():
    """System-wide statistics."""
    with get_db() as conn:
        doc_count = conn.execute("SELECT COUNT(*) as c FROM documents").fetchone()["c"]
        fact_count = conn.execute("SELECT COUNT(*) as c FROM facts").fetchone()["c"]
        rejected_count = conn.execute("SELECT COUNT(*) as c FROM rejected_facts").fetchone()["c"]
        entity_count = conn.execute("SELECT COUNT(*) as c FROM entities").fetchone()["c"]
        pred_count = conn.execute("SELECT COUNT(*) as c FROM predicates").fetchone()["c"]
        rel_count = conn.execute("SELECT COUNT(*) as c FROM relations").fetchone()["c"]
        qual_count = conn.execute("SELECT COUNT(*) as c FROM qualifier_registry").fetchone()["c"]

        # Verdict breakdown
        verdict_rows = conn.execute(
            "SELECT verdict, COUNT(*) as c FROM relations GROUP BY verdict"
        ).fetchall()
        verdicts = {r["verdict"]: r["c"] for r in verdict_rows}

        # Hallucination rate
        hallucination_rate = None
        if fact_count + rejected_count > 0:
            hallucination_rate = round(rejected_count / (fact_count + rejected_count), 4)

        # Cache hit rate
        cache_total = conn.execute("SELECT COUNT(*) as c FROM llm_cache").fetchone()["c"]

        return SystemStats(
            document_count=doc_count,
            fact_count=fact_count,
            rejected_fact_count=rejected_count,
            entity_count=entity_count,
            predicate_count=pred_count,
            relation_count=rel_count,
            hallucination_rate=hallucination_rate,
            qualifier_key_count=qual_count,
            verdicts=verdicts,
        )
