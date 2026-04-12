"""
Pydantic data models for all PersonaCR V2 entities.
"""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field


# ── Layer 1: Fingerprint ────────────────────────────────────────────────────

class FingerprintData(BaseModel):
    # ── Original features ────────────────────────────────────────────────────
    avg_function_length: float = 0.0
    max_function_length: int = 0
    docstring_coverage: float = 0.0
    naming_convention: str = "unknown"       # snake_case | camelCase | PascalCase
    error_handling_rate: float = 0.0
    type_hint_usage: float = 0.0
    avg_complexity: float = 0.0
    common_patterns: list[str] = []
    pattern_frequency: dict[str, int] = {}
    languages: list[str] = []
    language_distribution: dict[str, int] = {}
    total_functions: int = 0
    # ── Ghaleb MSR 2026 — comment features ──────────────────────────────────
    comment_density: float = 0.0            # comment lines / total lines
    inline_comment_ratio: float = 0.0       # inline comments / all comments
    comment_to_code_ratio: float = 0.0      # comment lines / code lines
    # ── Ghaleb MSR 2026 — conditional features ───────────────────────────────
    conditional_density: float = 0.0        # conditional keywords / lines
    conditionals_per_100_lines: float = 0.0 # conditional_density × 100
    # ── Ghaleb MSR 2026 — loop features ─────────────────────────────────────
    loop_density: float = 0.0               # loop keywords / lines
    for_to_while_ratio: float = 0.0         # for loops / (for + while loops)
    # ── Ghaleb MSR 2026 — style features ────────────────────────────────────
    comprehension_ratio: float = 0.0        # comprehensions / (comprehensions + for), Python only
    change_concentration_gini: float = 0.0  # Gini of function lengths
    # ── Ghaleb MSR 2026 — indentation features ───────────────────────────────
    indentation_consistency: float = 1.0    # fraction of functions using dominant style
    primary_indent_depth: float = 0.0       # average indent width in spaces
    # ── Ghaleb MSR 2026 — line length features ───────────────────────────────
    avg_line_length: float = 0.0
    max_line_length: int = 0
    std_line_length: float = 0.0
    lines_over_80: float = 0.0              # fraction of lines > 80 chars
    lines_over_120: float = 0.0             # fraction of lines > 120 chars
    # ── Ghaleb MSR 2026 — import features ────────────────────────────────────
    import_density: float = 0.0             # import statements / total lines
    wildcard_import_ratio: float = 0.0      # wildcard imports / total imports


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
