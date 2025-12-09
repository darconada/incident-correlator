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
    CANCELLED = "cancelled"


class JobType(str, Enum):
    STANDARD = "standard"    # INC con opciones por defecto
    CUSTOM = "custom"        # INC con búsqueda avanzada
    MANUAL = "manual"        # Sin ticket de incidente


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

class SearchOptions(BaseModel):
    """Opciones avanzadas de búsqueda de TECCMs."""
    window_before: str = Field(default="48h", description="Ventana temporal hacia atrás desde el INC")
    window_after: str = Field(default="2h", description="Ventana temporal hacia adelante desde el INC")
    include_active: bool = Field(default=True, description="Incluir TECCMs activos al momento del INC")
    include_no_end: bool = Field(default=True, description="Incluir TECCMs sin fecha de fin")
    include_external_maintenance: bool = Field(default=False, description="Incluir tickets de tipo EXTERNAL MAINTENANCE en el scoring")
    max_results: int = Field(default=500, ge=10, le=2000, description="Máximo de resultados por búsqueda")
    extra_jql: str = Field(default="", description="Filtro JQL adicional (ej: AND assignee = 'user')")
    project: str = Field(default="TECCM", description="Proyecto Jira a buscar")


class ExtractionRequest(BaseModel):
    inc: str = Field(..., description="INC ticket key, e.g., INC-117346")
    window: str = Field(default="48h", description="Time window (legacy, use search_options)")
    search_options: Optional[SearchOptions] = Field(default=None, description="Opciones avanzadas de búsqueda")


class ManualAnalysisRequest(BaseModel):
    """Request for manual analysis without an incident ticket."""
    name: Optional[str] = Field(default=None, description="Nombre opcional para identificar el análisis")
    impact_time: str = Field(..., description="Fecha/hora del impacto en formato ISO (YYYY-MM-DDTHH:MM)")
    services: List[str] = Field(default_factory=list, description="Servicios afectados")
    hosts: List[str] = Field(default_factory=list, description="Hosts afectados")
    technologies: List[str] = Field(default_factory=list, description="Tecnologías involucradas")
    team: Optional[str] = Field(default=None, description="Equipo responsable")
    search_options: Optional[SearchOptions] = Field(default=None, description="Opciones de búsqueda de TECCMs")


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
    # New fields for job metadata
    job_type: Optional[str] = "standard"  # standard, custom, manual
    username: Optional[str] = None
    search_summary: Optional[str] = None  # Brief summary of search options


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


# ══════════════════════════════════════════════════════════════════════════════
#  SERVICE MAPPINGS
# ══════════════════════════════════════════════════════════════════════════════

class ServiceSynonymsResponse(BaseModel):
    """Response with service synonyms mapping."""
    synonyms: Dict[str, List[str]] = Field(
        ...,
        description="Map of canonical service name -> list of aliases"
    )


class ServiceSynonymsUpdateRequest(BaseModel):
    """Request to update service synonyms."""
    synonyms: Dict[str, List[str]] = Field(
        ...,
        description="Complete map of service synonyms to save"
    )


class ServiceGroupsResponse(BaseModel):
    """Response with related service groups."""
    groups: Dict[str, List[str]] = Field(
        ...,
        description="Map of ecosystem name -> list of services in that ecosystem"
    )


class ServiceGroupsUpdateRequest(BaseModel):
    """Request to update service groups."""
    groups: Dict[str, List[str]] = Field(
        ...,
        description="Complete map of service groups to save"
    )


class ServiceMappingsResponse(BaseModel):
    """Combined response with all service mappings."""
    synonyms: Dict[str, List[str]]
    groups: Dict[str, List[str]]
