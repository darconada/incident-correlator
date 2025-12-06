"""
Configuration router.
Handles weights and other settings.
"""

from fastapi import APIRouter, Depends

from ..models import Weights, WeightsConfig, WeightsUpdateRequest, AppConfig, AppConfigUpdateRequest, Penalties, Bonuses, Thresholds
from ..db.storage import get_db
from ..routers.auth import require_auth, SessionData

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/weights", response_model=WeightsConfig)
async def get_weights(session: SessionData = Depends(require_auth)):
    """
    Get current default weights.
    """
    db = get_db()
    weights = db.get_weights()

    return WeightsConfig(weights=weights)


@router.put("/weights", response_model=WeightsConfig)
async def update_weights(
    request: WeightsUpdateRequest,
    session: SessionData = Depends(require_auth)
):
    """
    Update default weights.
    """
    db = get_db()
    current = db.get_weights()

    # Update only provided fields
    new_weights = Weights(
        time=request.time if request.time is not None else current.time,
        service=request.service if request.service is not None else current.service,
        infra=request.infra if request.infra is not None else current.infra,
        org=request.org if request.org is not None else current.org,
    )

    db.set_weights(new_weights)

    return WeightsConfig(weights=new_weights)


@router.post("/weights/reset", response_model=WeightsConfig)
async def reset_weights(session: SessionData = Depends(require_auth)):
    """
    Reset weights to default values.
    """
    db = get_db()
    default_weights = Weights()
    db.set_weights(default_weights)

    return WeightsConfig(weights=default_weights)


@router.get("/app", response_model=AppConfig)
async def get_app_config(session: SessionData = Depends(require_auth)):
    """
    Get all app configuration.
    """
    db = get_db()
    return AppConfig(
        weights=db.get_weights(),
        penalties=db.get_penalties(),
        bonuses=db.get_bonuses(),
        thresholds=db.get_thresholds(),
        top_results=db.get_top_results()
    )


@router.put("/app", response_model=AppConfig)
async def update_app_config(
    request: AppConfigUpdateRequest,
    session: SessionData = Depends(require_auth)
):
    """
    Update app configuration.
    """
    db = get_db()

    if request.weights:
        db.set_weights(request.weights)

    if request.penalties:
        db.set_penalties(request.penalties)

    if request.bonuses:
        db.set_bonuses(request.bonuses)

    if request.thresholds:
        db.set_thresholds(request.thresholds)

    if request.top_results is not None:
        db.set_top_results(request.top_results)

    return AppConfig(
        weights=db.get_weights(),
        penalties=db.get_penalties(),
        bonuses=db.get_bonuses(),
        thresholds=db.get_thresholds(),
        top_results=db.get_top_results()
    )


@router.post("/app/reset", response_model=AppConfig)
async def reset_app_config(session: SessionData = Depends(require_auth)):
    """
    Reset all config to defaults.
    """
    db = get_db()
    from ..config import get_settings
    settings = get_settings()

    default_weights = Weights()
    default_penalties = Penalties()
    default_bonuses = Bonuses()
    default_thresholds = Thresholds()

    db.set_weights(default_weights)
    db.set_penalties(default_penalties)
    db.set_bonuses(default_bonuses)
    db.set_thresholds(default_thresholds)
    db.set_top_results(settings.default_top_results)

    return AppConfig(
        weights=default_weights,
        penalties=default_penalties,
        bonuses=default_bonuses,
        thresholds=default_thresholds,
        top_results=settings.default_top_results
    )
