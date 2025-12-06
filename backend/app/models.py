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


class Penalties(BaseModel):
    no_live_intervals: float = Field(default=0.8, ge=0, le=1, description="Sin intervalos reales documentados")
    no_hosts: float = Field(default=0.95, ge=0, le=1, description="Sin hosts identificados")
    no_services: float = Field(default=0.90, ge=0, le=1, description="Sin servicios identificados")
    generic_change: float = Field(default=0.5, ge=0, le=1, description="Cambio afecta >10 servicios")
    long_duration_week: float = Field(default=0.8, ge=0, le=1, description="Duracion >1 semana")
    long_duration_month: float = Field(default=0.6, ge=0, le=1, description="Duracion >1 mes")
    long_duration_quarter: float = Field(default=0.4, ge=0, le=1, description="Duracion >3 meses")


class Bonuses(BaseModel):
    proximity_exact: float = Field(default=1.5, ge=1, le=3, description="TECCM empezo <30 min del INC")
    proximity_1h: float = Field(default=1.3, ge=1, le=3, description="TECCM empezo <1 hora del INC")
    proximity_2h: float = Field(default=1.2, ge=1, le=3, description="TECCM empezo <2 horas del INC")
    proximity_4h: float = Field(default=1.1, ge=1, le=3, description="TECCM empezo <4 horas del INC")


class Thresholds(BaseModel):
    time_decay_hours: float = Field(default=4, ge=1, le=48, description="Horas para decay completo del time_score")
    min_score_to_show: float = Field(default=0.0, ge=0, le=100, description="Score minimo para mostrar en ranking")


class AppConfig(BaseModel):
    weights: Weights
    penalties: Penalties = Field(default_factory=Penalties)
    bonuses: Bonuses = Field(default_factory=Bonuses)
    thresholds: Thresholds = Field(default_factory=Thresholds)
    top_results: int = Field(default=20, ge=5, le=200)


class AppConfigUpdateRequest(BaseModel):
    weights: Optional[Weights] = None
    penalties: Optional[Penalties] = None
    bonuses: Optional[Bonuses] = None
    thresholds: Optional[Thresholds] = None
    top_results: Optional[int] = Field(default=None, ge=5, le=200)
