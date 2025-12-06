"""
Analysis router.
Handles extraction jobs, scoring, and ranking.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Request

from ..models import (
    ExtractionRequest, ExtractionResponse,
    ManualAnalysisRequest,
    JobInfo, JobListResponse,
    ScoreRequest, RankingResponse, TECCMDetailResponse,
    Weights
)
from ..db.storage import get_db
from ..jobs.extraction import start_extraction_job, start_manual_analysis_job, get_job_progress
from ..services.scorer import calculate_ranking, get_teccm_detail
from ..routers.auth import require_auth, SessionData
from ..config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/extract", response_model=ExtractionResponse)
async def start_extraction(
    request: ExtractionRequest,
    session: SessionData = Depends(require_auth)
):
    """
    Start a new extraction job.
    Returns immediately with a job_id for polling.

    Supports advanced search options:
    - window_before: Time window before INC (default "48h")
    - window_after: Time window after INC (default "2h")
    - include_active: Include TECCMs active at INC time (default True)
    - include_no_end: Include TECCMs without end date (default True)
    - max_results: Max results per search (default 500)
    - extra_jql: Additional JQL filter
    - project: Jira project to search (default "TECCM")
    """
    db = get_db()

    # Validate INC format
    inc = request.inc.upper()
    if not inc.startswith("INC-"):
        raise HTTPException(status_code=400, detail="Invalid INC format. Expected INC-XXXXXX")

    # Determine window string for display
    if request.search_options:
        window_display = request.search_options.window_before
    else:
        window_display = request.window

    # Determine job type and build search summary
    job_type = "standard"
    search_summary = None
    if request.search_options:
        job_type = "custom"
        # Build a brief summary of non-default options
        summary_parts = []
        opts = request.search_options
        if not opts.include_active:
            summary_parts.append("sin activos")
        if not opts.include_no_end:
            summary_parts.append("sin abiertos")
        if opts.include_external_maintenance:
            summary_parts.append("+ext.maint")
        if opts.extra_jql:
            summary_parts.append("JQL extra")
        if opts.project != "TECCM":
            summary_parts.append(f"proj:{opts.project}")
        if summary_parts:
            search_summary = ", ".join(summary_parts)

    # Create job with metadata
    job_id = db.create_job(
        inc=inc,
        window=window_display,
        job_type=job_type,
        username=session.username,
        search_summary=search_summary
    )
    logger.info(f"Created job {job_id} for {inc} with window {window_display} (type={job_type}, user={session.username})")

    # Convert search_options to dict if present
    search_options_dict = None
    if request.search_options:
        search_options_dict = {
            "window_before": request.search_options.window_before,
            "window_after": request.search_options.window_after,
            "include_active": request.search_options.include_active,
            "include_no_end": request.search_options.include_no_end,
            "include_external_maintenance": request.search_options.include_external_maintenance,
            "max_results": request.search_options.max_results,
            "extra_jql": request.search_options.extra_jql,
            "project": request.search_options.project,
        }
        logger.info(f"Advanced search: include_active={request.search_options.include_active}, include_no_end={request.search_options.include_no_end}, include_external_maintenance={request.search_options.include_external_maintenance}")

    # Start background extraction
    start_extraction_job(
        job_id=job_id,
        inc_key=inc,
        window=request.window,
        username=session.username,
        password=session.password,
        search_options=search_options_dict
    )

    return ExtractionResponse(
        job_id=job_id,
        message=f"Extraction started for {inc}"
    )


@router.post("/manual", response_model=ExtractionResponse)
async def start_manual_analysis(
    request: ManualAnalysisRequest,
    session: SessionData = Depends(require_auth)
):
    """
    Start a manual analysis without an incident ticket.

    Creates a virtual incident from the provided parameters and searches
    for matching TECCMs in the time window.
    """
    from datetime import datetime

    db = get_db()

    # Parse and validate impact_time
    try:
        impact_dt = datetime.fromisoformat(request.impact_time.replace('Z', ''))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid impact_time format. Expected ISO format (YYYY-MM-DDTHH:MM)")

    # Build display name for the job
    if request.name:
        display_name = f"Manual: {request.name}"
    else:
        display_name = f"Manual - {impact_dt.strftime('%Y-%m-%d %H:%M')}"

    # Determine window from search_options or default
    if request.search_options:
        window_display = request.search_options.window_before
    else:
        window_display = "48h"

    # Build search summary
    summary_parts = []
    if request.services:
        summary_parts.append(f"{len(request.services)} servicios")
    if request.hosts:
        summary_parts.append(f"{len(request.hosts)} hosts")
    if request.technologies:
        summary_parts.append(f"{len(request.technologies)} techs")
    if request.team:
        summary_parts.append(f"equipo: {request.team}")
    search_summary = ", ".join(summary_parts) if summary_parts else None

    # Create job with manual type
    job_id = db.create_job(
        inc=display_name,
        window=window_display,
        job_type="manual",
        username=session.username,
        search_summary=search_summary
    )
    logger.info(f"Created manual analysis job {job_id}: {display_name} (user={session.username})")

    # Build search_options dict
    search_options_dict = None
    if request.search_options:
        search_options_dict = {
            "window_before": request.search_options.window_before,
            "window_after": request.search_options.window_after,
            "include_active": request.search_options.include_active,
            "include_no_end": request.search_options.include_no_end,
            "include_external_maintenance": request.search_options.include_external_maintenance,
            "max_results": request.search_options.max_results,
            "extra_jql": request.search_options.extra_jql,
            "project": request.search_options.project,
        }

    # Build virtual incident data
    virtual_incident = {
        "name": request.name,
        "impact_time": request.impact_time,
        "services": request.services,
        "hosts": request.hosts,
        "technologies": request.technologies,
        "team": request.team,
    }

    # Start background job
    start_manual_analysis_job(
        job_id=job_id,
        virtual_incident=virtual_incident,
        username=session.username,
        password=session.password,
        search_options=search_options_dict
    )

    return ExtractionResponse(
        job_id=job_id,
        message=f"Manual analysis started: {display_name}"
    )


@router.get("/options/technologies")
async def get_technologies(
    session: SessionData = Depends(require_auth)
):
    """Get list of available technologies for manual analysis."""
    from ..services.extractor import TECHNOLOGIES
    return {"technologies": sorted(TECHNOLOGIES)}


@router.get("/options/services")
async def get_services(
    session: SessionData = Depends(require_auth)
):
    """Get list of available service names for manual analysis."""
    from ..services.extractor import SERVICE_SYNONYMS
    # Return the canonical service names (keys of the synonyms dict)
    return {"services": sorted(SERVICE_SYNONYMS.keys())}


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    limit: int = 50,
    session: SessionData = Depends(require_auth)
):
    """
    Get list of recent jobs.
    """
    db = get_db()
    jobs = db.get_jobs(limit=limit)

    return JobListResponse(jobs=jobs)


@router.get("/jobs/{job_id}", response_model=JobInfo)
async def get_job(
    job_id: str,
    session: SessionData = Depends(require_auth)
):
    """
    Get job status and progress.
    """
    db = get_db()
    job = db.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Enrich with real-time progress if job is active
    progress = get_job_progress(job_id)
    if progress:
        # Update progress from in-memory state
        if progress.get("total", 0) > 0:
            job.progress = int((progress["progress"] / progress["total"]) * 100)

    return job


@router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: str,
    session: SessionData = Depends(require_auth)
):
    """
    Delete a job and its data.
    """
    db = get_db()

    if not db.delete_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found")

    return {"success": True, "message": "Job deleted"}


@router.post("/score", response_model=RankingResponse)
async def recalculate_score(
    request: ScoreRequest,
    session: SessionData = Depends(require_auth)
):
    """
    Recalculate ranking with custom weights.
    """
    db = get_db()

    # Get extraction data
    extraction = db.get_extraction(request.job_id)
    if not extraction:
        raise HTTPException(status_code=404, detail="Extraction data not found")

    # Get weights
    weights = request.weights or db.get_weights()

    # Calculate ranking
    try:
        ranking_data = calculate_ranking(
            extraction,
            weights={
                "time": weights.time,
                "service": weights.service,
                "infra": weights.infra,
                "org": weights.org
            }
        )
    except Exception as e:
        logger.exception(f"Error calculating ranking: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    # Save new ranking
    db.save_ranking(request.job_id, weights, ranking_data)

    # Transform to response model
    return _transform_ranking_response(ranking_data)


@router.get("/{job_id}/ranking", response_model=RankingResponse)
async def get_ranking(
    job_id: str,
    top: int = 50,
    session: SessionData = Depends(require_auth)
):
    """
    Get ranking for a job.
    """
    db = get_db()

    # Try to get cached ranking first
    ranking_data = db.get_latest_ranking(job_id)

    if not ranking_data:
        # Calculate ranking from extraction
        extraction = db.get_extraction(job_id)
        if not extraction:
            raise HTTPException(status_code=404, detail="Job data not found")

        weights = db.get_weights()
        ranking_data = calculate_ranking(
            extraction,
            weights={
                "time": weights.time,
                "service": weights.service,
                "infra": weights.infra,
                "org": weights.org
            }
        )

        db.save_ranking(job_id, weights, ranking_data)

    # Limit ranking
    if top and top < len(ranking_data.get("ranking", [])):
        ranking_data["ranking"] = ranking_data["ranking"][:top]

    return _transform_ranking_response(ranking_data)


@router.get("/{job_id}/teccm/{teccm_key}")
async def get_teccm_details(
    job_id: str,
    teccm_key: str,
    session: SessionData = Depends(require_auth)
):
    """
    Get detailed information about a specific TECCM.
    """
    db = get_db()
    settings = get_settings()

    extraction = db.get_extraction(job_id)
    if not extraction:
        raise HTTPException(status_code=404, detail="Job data not found")

    weights = db.get_weights()
    detail = get_teccm_detail(
        extraction,
        teccm_key,
        weights={
            "time": weights.time,
            "service": weights.service,
            "infra": weights.infra,
            "org": weights.org
        }
    )

    if not detail:
        raise HTTPException(status_code=404, detail=f"TECCM {teccm_key} not found")

    # Add Jira URL
    detail["jira_url"] = f"{settings.jira_url}/browse/{teccm_key}"

    return detail


def _transform_ranking_response(ranking_data: dict) -> RankingResponse:
    """Transform internal ranking data to API response model."""
    from ..models import IncidentInfo, TECCMRankingItem

    incident = IncidentInfo(
        issue_key=ranking_data["incident"]["issue_key"],
        summary=ranking_data["incident"]["summary"],
        first_impact_time=ranking_data["incident"].get("first_impact_time"),
        created_at=ranking_data["incident"].get("created_at"),
        services=ranking_data["incident"].get("services", []),
        hosts=ranking_data["incident"].get("hosts", []),
        technologies=ranking_data["incident"].get("technologies", []),
    )

    ranking_items = []
    for item in ranking_data.get("ranking", []):
        teccm_info = item.get("teccm_info", {})
        details = item.get("details", {})
        ranking_items.append(TECCMRankingItem(
            rank=item["rank"],
            issue_key=item["issue_key"],
            summary=item["summary"],
            final_score=item["final_score"],
            sub_scores=item["sub_scores"],
            details=details,
            assignee=teccm_info.get("assignee"),
            team=teccm_info.get("team"),
            planned_start=teccm_info.get("planned_start"),
            planned_end=teccm_info.get("planned_end"),
            live_intervals=teccm_info.get("live_intervals", []),
            resolution=teccm_info.get("resolution"),
            services=teccm_info.get("services", []),
            hosts=teccm_info.get("hosts", []),
            technologies=teccm_info.get("technologies", []),
            penalties=details.get("penalties", []),
            bonuses=details.get("bonuses", []),
        ))

    return RankingResponse(
        incident=incident,
        analysis=ranking_data["analysis"],
        ranking=ranking_items
    )
