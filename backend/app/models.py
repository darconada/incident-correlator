"""
Modelos Pydantic para la API.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


# ══════════════════════════════════════════════════════════════════════════════
#  ENUMS
# ══════════════════════════════════════════════════════════════════════════════

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ══════════════════════════════════════════════════════════════════════════════
#  AUTH
# ══════════════════════════════════════════════════════════════════════════════

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    message: str
    token: Optional[str] = None


class SessionInfo(BaseModel):
    authenticated: bool
    username: Optional[str] = None
    jira_url: str


# ══════════════════════════════════════════════════════════════════════════════
#  EXTRACTION / ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

class ExtractionRequest(BaseModel):
    inc: str = Field(..., description="INC ticket key, e.g., INC-117346")
    window: str = Field(default="48h", description="Time window, e.g., 48h, 2d, 7d")


class ExtractionResponse(BaseModel):
    job_id: str
    message: str


class JobInfo(BaseModel):
    job_id: str
    inc: str
    window: str
    status: JobStatus
    progress: int = 0
    total_teccms: Optional[int] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class JobListResponse(BaseModel):
    jobs: List[JobInfo]


# ══════════════════════════════════════════════════════════════════════════════
#  SCORING
# ══════════════════════════════════════════════════════════════════════════════

class Weights(BaseModel):
    time: float = Field(default=0.35, ge=0, le=1)
    service: float = Field(default=0.30, ge=0, le=1)
    infra: float = Field(default=0.20, ge=0, le=1)
    org: float = Field(default=0.15, ge=0, le=1)


class ScoreRequest(BaseModel):
    job_id: str
    weights: Optional[Weights] = None


class SubScoreDetail(BaseModel):
    score: float
    reason: str
    matches: List[str] = []


class TECCMRankingItem(BaseModel):
    rank: int
    issue_key: str
    summary: str
    final_score: float
    sub_scores: Dict[str, float]
    details: Dict[str, Any]

    # Extra info for detail view
    assignee: Optional[str] = None
    team: Optional[str] = None
    planned_start: Optional[str] = None
    planned_end: Optional[str] = None
    live_intervals: List[Dict[str, str]] = []
    resolution: Optional[str] = None
    services: List[str] = []
    hosts: List[str] = []
    technologies: List[str] = []

    # Penalties and bonuses applied
    penalties: List[str] = []
    bonuses: List[str] = []


class IncidentInfo(BaseModel):
    issue_key: str
    summary: str
    first_impact_time: Optional[str] = None
    created_at: Optional[str] = None
    services: List[str] = []
    hosts: List[str] = []
    technologies: List[str] = []


class RankingResponse(BaseModel):
    incident: IncidentInfo
    analysis: Dict[str, Any]
    ranking: List[TECCMRankingItem]


class TECCMDetailResponse(BaseModel):
    issue_key: str
    summary: str
    final_score: float
    sub_scores: Dict[str, SubScoreDetail]
    teccm_info: Dict[str, Any]
    jira_url: str


# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════════════════

class WeightsConfig(BaseModel):
    weights: Weights


class WeightsUpdateRequest(BaseModel):
    time: Optional[float] = None
    service: Optional[float] = None
    infra: Optional[float] = None
    org: Optional[float] = None


class AppConfig(BaseModel):
    weights: Weights
    top_results: int = Field(default=20, ge=5, le=200)


class AppConfigUpdateRequest(BaseModel):
    weights: Optional[Weights] = None
    top_results: Optional[int] = Field(default=None, ge=5, le=200)
