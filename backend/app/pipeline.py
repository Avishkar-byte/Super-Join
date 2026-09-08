"""Document processing pipeline — orchestrates all stages.

Called as a background task from POST /documents.
Stages: parsing → chunking → extracting → grounding → canonicalizing → reconciling → done
"""

import traceback

from app.jobs import update_job

# Terms drawn from the metrics the reconciliation stage actually cares about
# (revenue, hub counts, periods) — used to bias the small extraction budget
# toward chunks likely to overlap across documents, instead of cover pages.
FINANCIAL_KEYWORDS = [
    "revenue", "crore", "total income", "profit", "loss", "ebitda",
    "consolidated", "standalone", "fy24", "fy23", "fy22", "hub", "hubs",
    "shipment", "gross merchandise", "margin", "expenses",
]


def _select_relevant_chunks(chunks, limit=6):
    """Rank chunks by financial-keyword density and take the top `limit`.

    The extraction budget is small (free-tier LLM quota), so instead of
    blindly taking the first N chunks by page order (which tends to land on
    cover pages / TOC / admin boilerplate), prioritize chunks that are
    likely to carry the cross-document financial metrics the reconciliation
    stage depends on to find corroborating/contradicting facts.
    """
    def score(chunk):
        text_lower = chunk["text"].lower()
        return sum(text_lower.count(kw) for kw in FINANCIAL_KEYWORDS)

    ranked = sorted(chunks, key=score, reverse=True)
    selected = [c for c in ranked[:limit] if score(c) > 0]
    if len(selected) < limit:
        # Fill remaining slots with earliest chunks not already selected, so
        # the total processed count stays predictable even for a document
        # with no keyword hits at all.
        selected_ids = {c["chunk_id"] for c in selected}
        for c in chunks:
            if len(selected) >= limit:
                break
            if c["chunk_id"] not in selected_ids:
                selected.append(c)
                selected_ids.add(c["chunk_id"])

    order = {c["chunk_id"]: i for i, c in enumerate(chunks)}
    selected.sort(key=lambda c: order[c["chunk_id"]])
    return selected


def process_document(doc_id: str, job_id: str, file_path: str):
    """Main pipeline entry point. Runs as a background task."""
    try:
        # Stage 1: Parse PDF
        update_job(job_id, status="parsing", stage="Parsing PDF")
        from app.ingest.pdf_parser import parse_pdf
        pages = parse_pdf(doc_id, file_path, job_id=job_id)
        update_job(job_id, stage=f"Parsed {len(pages)} pages")

        # Stage 2: Chunk
        update_job(job_id, status="chunking", stage="Chunking text")
        from app.ingest.chunker import chunk_document
        chunks = chunk_document(doc_id, pages)
        chunks = _select_relevant_chunks(chunks, limit=6)  # Superficial level for assignment
        update_job(job_id, chunks_total=len(chunks), stage=f"Created {len(chunks)} chunks")

        # Stage 3: Extract facts
        update_job(job_id, status="extracting", stage="Extracting facts")
        from app.extract.extractor import extract_facts
        raw_facts = extract_facts(doc_id, job_id, chunks)

        # Stage 4: Ground and verify
        update_job(job_id, status="grounding", stage="Grounding evidence")
        from app.extract.grounding import ground_facts
        verified_facts = ground_facts(doc_id, raw_facts, chunks)
        update_job(job_id, facts_found=len(verified_facts))

        # Stage 5: Canonicalize
        update_job(job_id, status="canonicalizing", stage="Canonicalizing entities")
        from app.canonical.entities import canonicalize_entities
        from app.canonical.predicates import canonicalize_predicates
        canonicalize_entities(doc_id, verified_facts)
        canonicalize_predicates(doc_id, verified_facts)

        # Stage 6: Reconcile
        update_job(job_id, status="reconciling", stage="Reconciling facts")
        from app.reconcile.candidates import find_candidates
        from app.reconcile.rules import apply_rules
        candidates = find_candidates(doc_id)
        apply_rules(candidates)

        # Done
        update_job(job_id, status="done", stage="Complete", progress=1.0)

        # Update document status
        from app.db import get_db
        with get_db() as conn:
            conn.execute(
                "UPDATE documents SET status = 'ready' WHERE doc_id = ?",
                (doc_id,),
            )

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        tb = traceback.format_exc()
        update_job(job_id, status="failed", stage="Error", error=f"{error_msg}\n{tb}")
        # Update document status
        try:
            from app.db import get_db
            with get_db() as conn:
                conn.execute(
                    "UPDATE documents SET status = 'failed' WHERE doc_id = ?",
                    (doc_id,),
                )
        except Exception:
            pass
