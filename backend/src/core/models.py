"""
Pydantic data models for all PersonaCR V2 entities.
"""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field


# ── Layer 1: Fingerprint ────────────────────────────────────────────────────

class FingerprintData(BaseModel):
    avg_function_length: float = 0.0
    max_function_length: int = 0
    docstring_coverage: float = 0.0
    naming_style: str = "unknown"
    error_handling_rate: float = 0.0
    type_hint_usage: float = 0.0
    avg_complexity: float = 0.0
    common_patterns: list[str] = []
    pattern_frequency: dict[str, int] = {}
    languages: list[str] = []
    language_distribution: dict[str, int] = {}
    total_functions: int = 0


class FingerprintResponse(BaseModel):
    repo_url: str
    repo_name: str
    fingerprint: FingerprintData
    num_functions: int
    last_commit_sha: str
    cache_status: str  # 'fresh' | 'stale' | 'new'


# ── Chat ────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str
    message: str
    file_content: str | None = None
    file_name: str | None = None
    repo_url: str | None = None  # active repo context


class ChatMessage(BaseModel):
    id: str | None = None
    session_id: str
    role: str  # 'user' | 'assistant'
    content: str
    message_type: str = "text"  # 'text' | 'review_result' | 'fingerprint' | 'file_upload' | 'chart'
    attached_file_name: str | None = None
    attached_review_id: str | None = None


# ── Review ──────────────────────────────────────────────────────────────────

class ReviewRequest(BaseModel):
    submitted_code: str = Field(min_length=1)
    repo_url: str | None = None
    user_id: str | None = None
    language: str | None = None


class IssueFound(BaseModel):
    category: str       # 'naming' | 'error_handling' | 'complexity' | 'documentation' | 'security' | 'logic'
    severity: str       # 'low' | 'medium' | 'high'
    description: str
    line: int | None = None


class ReviewScores(BaseModel):
    comprehensiveness: float = 0.0
    relevance: float = 0.0
    conciseness: float = 0.0
    overall: float = 0.0


class ReviewOutput(BaseModel):
    plan: str = ""
    style_feedback: str = ""
    defect_findings: list[IssueFound] = []
    qa_approved: bool = True
    scores: ReviewScores = ReviewScores()
    iterations: int = 1
    agent_traces: list[dict] = []


class ReviewResponse(BaseModel):
    review_id: str
    status: str
    output: ReviewOutput


class StatusResponse(BaseModel):
    job_id: str
    state: str
    progress: int
    message: str | None = None


class ReportResponse(BaseModel):
    job_id: str
    review_id: str
    status: str
    report: dict


# ── Analytics ───────────────────────────────────────────────────────────────

class MonthlyScore(BaseModel):
    month: str
    avg_score: float
    review_count: int


class IssueCategory(BaseModel):
    category: str
    count: int
    percentage: float


class AnalyticsResponse(BaseModel):
    total_reviews: int
    avg_score: float
    vs_last_month: float  # percentage change
    top_issue: str
    monthly_scores: list[MonthlyScore]
    issue_breakdown: list[IssueCategory]
    confidence_loop_rate: float   # how often confidence loop triggered
    quality_gate_pass_rate: float # how often review passed on first try


# ── Documentation ───────────────────────────────────────────────────────────

class DocRequest(BaseModel):
    repo_url: str
    doc_type: str = "all"  # 'architecture' | 'file_summary' | 'function_docs' | 'pattern_guide' | 'onboarding' | 'all'


class DocContent(BaseModel):
    doc_type: str
    content: str
    repo_name: str


class DocResponse(BaseModel):
    repo_url: str
    repo_name: str
    documents: list[DocContent]
