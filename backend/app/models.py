"""Pydantic models for API request/response shapes."""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime


# --- Enums ---

ObjectType = Literal["quantity", "date", "entity", "status", "text"]
Verdict = Literal["CORROBORATES", "CONTRADICTS", "RECONCILED_BY_CONTEXT", "SUPERSEDED", "UNRELATED"]
JobStatus = Literal[
    "queued", "parsing", "chunking", "extracting",
    "grounding", "canonicalizing", "reconciling", "done", "failed"
]


# --- Object value models ---

class ObjectValue(BaseModel):
    type: ObjectType
    value: Any = None
    unit: Optional[str] = None
    raw: str


# --- Evidence model ---

class Evidence(BaseModel):
    doc_id: str
    page: int
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    bbox: Optional[List[float]] = None
    quote: str


# --- Fact models ---

class FactBase(BaseModel):
    fact_id: str
    doc_id: str
    subject_raw: str
    subject_canonical_id: Optional[str] = None
    predicate_raw: str
    predicate_canonical_id: Optional[str] = None
    object_type: ObjectType
    object_value: ObjectValue
    qualifiers: Dict[str, Any] = Field(default_factory=dict)
    evidence: Evidence
    confidence: float
    extractor: str
    created_at: str


class FactDetail(FactBase):
    """Fact with its relations."""
    relations: List["RelationSummary"] = Field(default_factory=list)
    subject_canonical_name: Optional[str] = None
    predicate_canonical_name: Optional[str] = None


class FactListItem(BaseModel):
    """Compact fact for list views."""
    fact_id: str
    doc_id: str
    subject_raw: str
    subject_canonical_name: Optional[str] = None
    predicate_raw: str
    predicate_canonical_name: Optional[str] = None
    object_type: ObjectType
    object_value: ObjectValue
    qualifiers: Dict[str, Any] = Field(default_factory=dict)
    confidence: float
    evidence_quote: str
    evidence_page: int


# --- Relation models ---

class RelationSummary(BaseModel):
    relation_id: str
    fact_id_a: str
    fact_id_b: str
    verdict: Verdict
    rule_id: str
    reason: str
    confidence: Optional[float] = None


class RelationDetail(RelationSummary):
    """Relation with both facts included."""
    fact_a: FactBase
    fact_b: FactBase


# --- Entity models ---

class EntityAlias(BaseModel):
    surface_form: str
    doc_id: Optional[str] = None


class EntitySummary(BaseModel):
    entity_id: str
    canonical_name: str
    aliases: List[EntityAlias] = Field(default_factory=list)
    fact_count: int


# --- Predicate models ---

class PredicateSummary(BaseModel):
    pred_id: str
    canonical_name: str
    fact_count: int


# --- Document models ---

class DocumentSummary(BaseModel):
    doc_id: str
    filename: str
    page_count: Optional[int] = None
    file_size: Optional[int] = None
    fact_count: int = 0
    status: str
    created_at: str


class DocumentDetail(DocumentSummary):
    sha256: str
    page_fact_counts: Dict[int, int] = Field(default_factory=dict)


# --- Job models ---

class JobStatus_(BaseModel):
    job_id: str
    doc_id: str
    status: JobStatus
    stage: Optional[str] = None
    progress: float = 0.0
    chunks_total: int = 0
    chunks_done: int = 0
    facts_found: int = 0
    errors: List[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


# --- Upload response ---

class UploadResponse(BaseModel):
    job_id: str
    doc_id: str
    cached: bool


# --- Rejected fact models ---

class RejectedFact(BaseModel):
    rejected_id: str
    doc_id: str
    chunk_id: Optional[str] = None
    raw_output: Any
    reason: str
    details: Optional[Any] = None
    created_at: str


# --- Qualifier registry ---

class QualifierKey(BaseModel):
    key: str
    count: int
    first_seen: str
    last_seen: str


# --- Graph projection ---

class GraphNode(BaseModel):
    id: str
    label: str
    type: Literal["entity", "fact"]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    label: str
    verdict: Optional[Verdict] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]


# --- Stats ---

class SystemStats(BaseModel):
    document_count: int = 0
    fact_count: int = 0
    rejected_fact_count: int = 0
    entity_count: int = 0
    predicate_count: int = 0
    relation_count: int = 0
    hallucination_rate: Optional[float] = None
    pair_reduction_ratio: Optional[float] = None
    cache_hit_rate: Optional[float] = None
    qualifier_key_count: int = 0
    verdicts: Dict[str, int] = Field(default_factory=dict)


# --- Health ---

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
