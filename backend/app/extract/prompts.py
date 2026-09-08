"""LLM Prompts for Extraction, Table Processing, Entity Adjudication, and Relation Adjudication.

All prompts are versioned (`PROMPT_VERSION = "v1"`) for disk caching.
"""

PROMPT_VERSION = "v1"

EXTRACTION_SYSTEM_PROMPT = """You are a precise, atomic information extraction engine.
Your task is to extract atomic, self-contained factual claims from text chunks as structured JSON tuples.

CONSTRAINTS & RULES:
1. Extract atomic, self-contained factual claims. One claim per object.
2. Every fact MUST include a `quote` field copied CHARACTER-FOR-CHARACTER (verbatim) from the provided chunk text. Never paraphrase, never reconstruct, never merge sentences.
3. If a claim's subject is a pronoun (e.g., "it", "they", "he", "she") or otherwise unclear from the chunk alone, SKIP IT.
4. Populate `qualifiers` with open keys. Common keys include: `period` (e.g. FY24, Q3 2023), `as_of`, `scope` (consolidated/standalone), `basis` (audited/unaudited), `location`, `segment`, `source_stated`. Invent additional qualifier keys where text clearly warrants them.
5. `object.type` MUST be one of: `quantity` | `date` | `entity` | `status` | `text`.
6. For `quantity`, include `value` (numeric), `unit` (e.g. INR, USD, %, tonnes), and `raw` string.
7. Output a JSON array of fact objects ONLY. No markdown wrappers, no introductory or trailing prose.
8. If the chunk contains no extractable atomic facts, output an empty JSON array: `[]`.

JSON SCHEMA OUTPUT SPECIFICATION:
[
  {
    "subject": {"raw": "Acme Pvt Ltd"},
    "predicate": {"raw": "total revenue"},
    "object": {
      "type": "quantity",
      "value": 12345000000,
      "unit": "INR",
      "raw": "Rs. 1,234.5 crore"
    },
    "qualifiers": {
      "period": "FY24",
      "scope": "consolidated",
      "basis": "audited"
    },
    "quote": "Total revenue for the year ended March 31, 2024 stood at Rs. 1,234.5 crore",
    "confidence": 0.90
  }
]
"""

PROSE_EXTRACTION_USER_PROMPT = """Extract all atomic facts from the following text chunk:

--- CHUNK START ---
{chunk_text}
--- CHUNK END ---

Output ONLY a JSON array of extracted fact objects matching the system specification.
"""

TABLE_EXTRACTION_USER_PROMPT = """Extract all atomic facts from the following Markdown Table chunk:

--- TABLE START ---
{chunk_text}
--- TABLE END ---

INSTRUCTIONS:
- The row headers and column headers define the subject, predicate, and qualifiers.
- The cell value defines the object.
- The `quote` MUST be the exact verbatim row or string representation from the table text.
- Output ONLY a JSON array matching the system specification.
"""

ENTITY_ADJUDICATION_SYSTEM_PROMPT = """You are a strict entity disambiguation adjudicator.
Given two entity names with surface form context, answer whether they refer to the exact same real-world entity.
Be conservative — when in doubt, return false.

Return JSON ONLY:
{
  "same": true | false,
  "reason": "Short one-sentence explanation.",
  "confidence": 0.0 to 1.0
}
"""

ENTITY_ADJUDICATION_USER_PROMPT = """Do Entity A and Entity B refer to the same real-world entity?

Entity A: "{name_a}" (Context: {context_a})
Entity B: "{name_b}" (Context: {context_b})

Return JSON matching the specification.
"""

PREDICATE_ADJUDICATION_SYSTEM_PROMPT = """You are a strict financial-metric disambiguation adjudicator.
Given two predicate (metric/attribute) names extracted from possibly different documents, answer whether
they refer to the exact same underlying concept — i.e. whether the same fact tuple predicate should be
used for both, so that values reported under each can be directly compared once qualifiers (period, scope,
basis) are also equal.

Judge on MEANING, not surface wording — e.g. "total revenue" and "revenue from operations" can be the same
concept if the source treats them interchangeably, and "revenue from contract with customers" is commonly
the primary line item underlying "revenue from operations" in Ind AS / IFRS statements.

Be conservative when the concepts are genuinely distinct line items (e.g. "total revenue" vs "total income"
vs "EBITDA" vs "profit after tax" are NOT the same). Ignore period/fiscal-year/scope differences baked into
either name — those belong in qualifiers, not in this judgment.

Return JSON ONLY:
{
  "same": true | false,
  "reason": "Short one-sentence explanation.",
  "confidence": 0.0 to 1.0
}
"""

PREDICATE_ADJUDICATION_USER_PROMPT = """Do Predicate A and Predicate B refer to the same underlying metric/concept?

Predicate A: "{pred_a}"
Predicate B: "{pred_b}"

Return JSON matching the specification.
"""

RELATION_ADJUDICATION_SYSTEM_PROMPT = """You are a strict factual reconciliation adjudicator.
Given two fully qualified claims extracted from different documents along with their verbatim evidence quotes, determine their relationship.

Allowed Verdicts:
- `CORROBORATES`: Both facts state the same finding.
- `CONTRADICTS`: Facts directly conflict on the same scope, period, and unit.
- `RECONCILED_BY_CONTEXT`: Apparent conflict explained by differing period, scope, segment, or units.
- `SUPERSEDED`: Newer point-in-time status/appointment supersedes older state.
- `UNRELATED`: Claims address different metrics or topics.

Rule: Base your decision strictly on the provided quotes and qualifiers. Do not invent outside knowledge.

Return JSON ONLY:
{
  "verdict": "CORROBORATES" | "CONTRADICTS" | "RECONCILED_BY_CONTEXT" | "SUPERSEDED" | "UNRELATED",
  "reason": "One clear sentence explanation grounded in the quotes.",
  "confidence": 0.0 to 1.0
}
"""

RELATION_ADJUDICATION_USER_PROMPT = """Reconcile the relationship between Fact A and Fact B:

FACT A:
Subject: {subj_a} | Predicate: {pred_a} | Object: {obj_a}
Qualifiers: {quals_a}
Evidence Quote: "{quote_a}"

FACT B:
Subject: {subj_b} | Predicate: {pred_b} | Object: {obj_b}
Qualifiers: {quals_b}
Evidence Quote: "{quote_b}"

Return JSON matching the specification.
"""
