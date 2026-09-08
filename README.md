# Fact Layer — Grounded Knowledge Extraction & Cross-Document Reconciliation Engine

An end-to-end pipeline for ingesting PDF documents, extracting atomic facts with verbatim evidence, and automatically determining whether claims across documents **corroborate**, **contradict**, or are **reconcilable through context**.

> Built as a submission for the **SuperJoin on campus recruitment VIT Chennai**.

---

## Setup and Run Instructions

### Prerequisites
- **Python 3.11+**
- **Node.js 18+**
- **Gemini API Key** ([Get free key](https://ai.google.dev/)) or **Groq API Key** ([Get free key](https://console.groq.com/))

### 1. Backend Setup (FastAPI)

```bash
cd backend

# Create and activate Python virtual environment
python -m venv venv

# Windows (PowerShell):
.\venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

Create a `backend/.env` file with the following environment variables:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here
DATABASE_PATH=./data/knowledge.db
CORS_ORIGINS=http://localhost:3000
LLM_PRIMARY=gemini
LLM_FALLBACK=groq
PAGES_DIR=./data/pages
```

Start the backend server:
```bash
uvicorn app.main:app --reload --port 8000
```
- **API Server:** `http://localhost:8000`
- **Interactive Swagger Docs:** `http://localhost:8000/docs`

### 2. Frontend Setup (Next.js 16)

```bash
cd frontend
npm install
npm run dev
```
- **Analyst Workbench UI:** `http://localhost:3000`

---

## Approach & Architecture

### High-Level Pipeline Flow

```
PDF Upload
  │
  ▼
[PDF Parser] ── PyMuPDF page rendering & text extraction
  │
  ▼
[Chunker] ── Token-aware document segmentation (~800 words/chunk)
  │
  ▼
[LLM Extractor] ── Gemini 2.0 Flash structured JSON extraction
  │
  ▼
[Grounding Engine] ── rapidfuzz quote verification (85% threshold)
  │                   Rejects hallucinated claims → rejected_facts table
  ▼
[Canonicalizer] ── Entity, predicate, unit & date normalization
  │
  ▼
[Reconciliation Engine] ── Priority deterministic rule engine (Rules 1-5)
  │                        LLM Adjudicator fallback for undecided pairs (Rule 6)
  ▼
Knowledge Layer UI
  ├── Corroborated facts
  ├── Contradictions
  ├── Context-reconciled claims
  └── Failure audit log (Case 4)
```

### Key Engineering Decisions & Trade-Offs

1. **Qualified-Tuple Schema (No Messy Strings):**  
   Facts are stored as structured tuples with canonicalized entities, predicates, normalized numeric values (with unit scaling), and temporal/scope qualifiers.
   ```json
   {
     "subject": { "raw": "Delhivery Limited", "canonical_id": "e_delhivery" },
     "predicate": { "raw": "total revenue", "canonical_id": "p_total_revenue" },
     "object": { "type": "quantity", "value": 72410000000.0, "unit": "INR", "raw": "Rs. 7,241 crore" },
     "qualifiers": { "period": "FY24", "scope": "consolidated" },
     "evidence": { "doc_id": "d_1", "page": 14, "quote": "Total revenue for FY24 stood at Rs. 7,241 crore" }
   }
   ```

2. **Strict Verbatim Evidence Grounding (`rapidfuzz`):**  
   Every claim extracted by the LLM must match its source PDF chunk with similarity >= 85%. Hallucinated or non-verbatim claims are auto-rejected into the `rejected_facts` table with a log audit trail.

3. **Deterministic Rules Before LLM Adjudication:**  
   Instead of calling expensive LLM prompts for every pair (O(N^2)), facts are bucketed by `(canonical_subject, canonical_predicate)` and passed through a priority rule engine:
   - **Rule 1:** Values equal within 0.5% tolerance -> `CORROBORATES`
   - **Rule 2:** Disjoint qualifier time intervals -> `RECONCILED_BY_CONTEXT`
   - **Rule 3:** Unit/Scale mismatch ratio (Cr vs Mn vs Bn) -> `RECONCILED_BY_CONTEXT`
   - **Rule 4:** State predicate & superseding date -> `SUPERSEDED`
   - **Rule 5:** Overlapping period & scope with conflicting values -> `CONTRADICTS`
   - **Rule 6:** Undecided residue pairs -> Fallback to LLM Adjudicator.

4. **AI Tools & Frameworks Used:**
   - **Gemini 2.0 Flash / Groq Mixtral:** LLM structured extraction & reconciliation fallback.
   - **PyMuPDF (`fitz`):** Server-side PDF rendering and bounding-box snippet extraction.
   - **RapidFuzz:** Fast string matching for quote verification & entity canonicalization.
   - **FastAPI & Next.js 16:** Asynchronous REST backend & responsive workbench frontend.

---

## Showcasing The Four Cases

| Case | Scenario | Example & Grounding | Verdict & System Reasoning |
|---|---|---|---|
| **1. Corroborated Fact** | Same metric across documents with different phrasing | **Doc A:** Delhivery FY24 Total Revenue = Rs. 7,241 Cr<br>**Doc B:** Q3 top-line reached Rs. 72,410 Mn | **`CORROBORATES`** (Rule 1)<br>Normalized values match within 0.5% tolerance after unit scaling. |
| **2. Genuine Contradiction** | Conflicting values for identical scope & time period | **Doc A:** Express Hubs = 85 (FY24 Consolidated)<br>**Doc B:** Express Hubs = 62 (FY24 Consolidated) | **`CONTRADICTS`** (Rule 5)<br>Conflicting quantitative values over identical scope and time window. |
| **3. Reconciled by Context** | Discrepancy explained by time, scope, or unit differences | **Doc A:** Revenue = Rs. 4,884 Cr (FY22)<br>**Doc B:** Revenue = Rs. 7,241 Cr (FY24) | **`RECONCILED_BY_CONTEXT`** (Rule 2)<br>Apparent discrepancy explained by disjoint temporal markers (FY22 vs FY24). |
| **4. Extraction / Reasoning Failure** | Hallucinated quote or table layout ambiguity | **Quote:** "Company expanded to 15 countries"<br>**Fuzzy Match:** 42.6% (< 85%) | **`REJECTED (ungrounded_quote)`**<br>Recorded in Case 4 failure log table with full audit trail. |

---

## Limitations and Next Steps

### Processing is slow

The most significant limitation. A 17-page PDF currently takes **10–15 minutes** to process end to end.

Almost all of this is time spent waiting, not computing. The extraction stage makes one LLM call per chunk, and Gemini's free tier permits roughly 15 requests per minute, so a document producing 60–80 chunks spends the bulk of its wall-clock time in the rate limiter's backoff. PDF parsing, grounding, canonicalization, and the entire rule engine together account for a small fraction of the total; the rest is API throttling. A paid key with a higher rate limit would bring this well under a minute with no code changes.

What would actually fix it within the free tier:

- **Batch multiple chunks per call.** Currently one chunk per request, which wastes most of each request's available token budget. Packing 4–6 chunks into a single call should cut request count by roughly the same factor.
- **Pre-filter chunks.** Many chunks — tables of contents, boilerplate, signature blocks — yield no facts but still consume a request. A cheap heuristic pass on numeric density and named-entity presence could skip a meaningful share of them before they ever reach the LLM.
- **Parallel provider fan-out.** Gemini and Groq are both configured but used as primary and fallback. Running them concurrently against different chunks would roughly double effective throughput at no cost.

The asynchronous job architecture means slowness degrades the experience rather than breaking it: uploads return immediately and the UI reports progress per stage. But the wait is real and I am not going to pretend otherwise.

### Other things that do not work yet

- **Scanned PDFs.** There is no OCR step, so image-only documents yield nothing. The pipeline detects and reports this rather than silently returning an empty result, but detection is all it does.
- **Coreference across chunk boundaries.** A fact whose subject is a pronoun resolved several paragraphs earlier is dropped by the extractor rather than misattributed. This is the correct failure mode, but it costs recall on narrative documents.
- **Fiscal-year convention is assumed.** `FY24` is interpreted as April–March. For a document following a different convention this is silently wrong. Affected facts are flagged `fy_convention_assumed`, but the flag is not surfaced prominently enough in the UI.
- **No multi-hop reasoning.** Facts are compared pairwise. The system cannot infer that A contradicts C because A corroborates B and B contradicts C, nor derive a fact arithmetically from two others.
- **Table extraction is weaker than prose extraction.** Merged cells and multi-level column headers frequently produce facts with incomplete qualifiers, which then fail grounding and land in the rejected table. Nested-header handling is the single highest-value extraction improvement remaining.
- **Confidence values are model-reported.** They are not calibrated against measured accuracy and should be read as a rough ordering, not a probability.
- **Single-user assumption.** One SQLite file, no auth, no tenancy.

### What I would build next, in order

1. **Chunk batching and pre-filtering** — the highest-impact change available, and it addresses the speed limitation without needing a paid key.
2. **Nested table-header handling**, to recover the largest identifiable block of currently-rejected facts.
3. **Calibrating confidence** against a hand-labelled subset, so the score means something.
4. **Surfacing assumptions as first-class caveats** — fiscal convention, unit inference, entity merges made by the LLM adjudicator — in a review queue where a user can confirm or reject each one.
5. **A contradiction review workflow**, letting a user mark a flagged contradiction as resolved with a note that feeds back into the system as a new qualifier.

---

## Additional Notes

- **Zero Hardcoding:** The schema, entity canonicalizer, and rule engine generalize to any PDF domain (financial reports, healthcare, legal contracts, etc.) without document-specific rules or fixed schemas.
- **Free-Tier Resilience:** Async background processing (`job_id` polling) prevents HTTP gateway timeouts on free cloud hosts (Render/Vercel). SQLite disk caching avoids duplicate LLM calls (`sha256(chunk + prompt)` cache).
- **Auditability:** Grounded evidence links every fact directly to page numbers and verbatim text, giving analysts 100% confidence in extracted knowledge.
