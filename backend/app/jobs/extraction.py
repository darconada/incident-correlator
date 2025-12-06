"""
Background job for Jira extraction.
Uses asyncio to run extractions in background.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

from ..db.storage import get_db
from ..models import JobStatus
from ..services.jira_client import JiraClient
from ..services.extractor import extract_inc_with_teccms, extract_teccms_for_manual_analysis
from ..services.scorer import calculate_ranking

logger = logging.getLogger(__name__)

# Thread pool for blocking Jira operations
_executor = ThreadPoolExecutor(max_workers=4)

# Store for active jobs (in-memory, for progress tracking)
_active_jobs: Dict[str, Dict[str, Any]] = {}


def get_job_progress(job_id: str) -> Optional[Dict[str, Any]]:
    """Get progress info for an active job."""
    return _active_jobs.get(job_id)


async def run_extraction_job(
    job_id: str,
    inc_key: str,
    window: str,
    username: str,
    password: str,
    search_options: Optional[Dict[str, Any]] = None
):
    """
    Run extraction job in background.

    This function:
    1. Connects to Jira
    2. Extracts the INC and related TECCMs
    3. Calculates the initial ranking
    4. Saves everything to the database

    Args:
        job_id: Unique job identifier
        inc_key: INC ticket key
        window: Time window (legacy, ignored if search_options present)
        username: Jira username
        password: Jira password
        search_options: Advanced search options dict
    """
    db = get_db()
    _active_jobs[job_id] = {"progress": 0, "total": 0, "status": "connecting"}

    try:
        # Update status to running
        db.update_job_status(job_id, JobStatus.RUNNING)
        logger.info(f"Starting extraction job {job_id} for {inc_key}")
        if search_options:
            logger.info(f"Using advanced search options: {search_options}")

        # Connect to Jira (blocking operation, run in thread pool)
        _active_jobs[job_id]["status"] = "connecting"

        loop = asyncio.get_event_loop()

        def connect_jira():
            client = JiraClient(username, password)
            success, message = client.connect()
            if not success:
                raise Exception(f"Failed to connect to Jira: {message}")
            return client

        client = await loop.run_in_executor(_executor, connect_jira)
        logger.info(f"Connected to Jira for job {job_id}")

        # Define progress callback
        def progress_callback(current: int, total: int):
            _active_jobs[job_id].update({
                "progress": current,
                "total": total,
                "status": "extracting"
            })
            progress_pct = int((current / total) * 100) if total > 0 else 0
            db.update_job_status(job_id, JobStatus.RUNNING, progress=progress_pct, total_teccms=total - 1)

        # Run extraction (blocking, in thread pool)
        _active_jobs[job_id]["status"] = "extracting"

        def do_extraction():
            return extract_inc_with_teccms(
                client.client,
                inc_key,
                window,
                progress_callback,
                search_options=search_options
            )

        extraction_data = await loop.run_in_executor(_executor, do_extraction)
        logger.info(f"Extraction complete for job {job_id}: {len(extraction_data.get('tickets', []))} tickets")

        # Save extraction data
        db.save_extraction(job_id, extraction_data)

        # Calculate initial ranking
        _active_jobs[job_id]["status"] = "scoring"

        def do_scoring():
            return calculate_ranking(extraction_data)

        ranking_data = await loop.run_in_executor(_executor, do_scoring)
        logger.info(f"Scoring complete for job {job_id}: {len(ranking_data.get('ranking', []))} TECCMs ranked")

        # Save ranking
        from ..models import Weights
        db.save_ranking(job_id, Weights(), ranking_data)

        # Update job as completed
        # Count TECCMs based on include_external_maintenance setting
        include_ext = extraction_data.get('extraction_info', {}).get('search_options', {}).get('include_external_maintenance', False)
        if include_ext:
            total_teccms = len([t for t in extraction_data.get('tickets', []) if t.get('ticket_type') in ('CHANGE', 'EXTERNAL MAINTENANCE')])
        else:
            total_teccms = len([t for t in extraction_data.get('tickets', []) if t.get('ticket_type') == 'CHANGE'])
        db.update_job_status(job_id, JobStatus.COMPLETED, progress=100, total_teccms=total_teccms)

        _active_jobs[job_id]["status"] = "completed"
        logger.info(f"Job {job_id} completed successfully")

    except Exception as e:
        logger.exception(f"Job {job_id} failed: {e}")
        db.update_job_status(job_id, JobStatus.FAILED, error=str(e))
        _active_jobs[job_id]["status"] = "failed"
        _active_jobs[job_id]["error"] = str(e)

    finally:
        # Clean up after a delay (keep progress info available for a bit)
        await asyncio.sleep(60)
        if job_id in _active_jobs:
            del _active_jobs[job_id]


def start_extraction_job(
    job_id: str,
    inc_key: str,
    window: str,
    username: str,
    password: str,
    search_options: Optional[Dict[str, Any]] = None
):
    """Start an extraction job in background."""
    asyncio.create_task(
        run_extraction_job(job_id, inc_key, window, username, password, search_options)
    )


async def run_manual_analysis_job(
    job_id: str,
    virtual_incident: Dict[str, Any],
    username: str,
    password: str,
    search_options: Optional[Dict[str, Any]] = None
):
    """
    Run manual analysis job in background.

    This function:
    1. Connects to Jira
    2. Searches for TECCMs based on the virtual incident's impact_time
    3. Extracts the TECCMs
    4. Calculates the ranking against the virtual incident
    5. Saves everything to the database

    Args:
        job_id: Unique job identifier
        virtual_incident: Dict with manual incident data (impact_time, services, hosts, technologies, team)
        username: Jira username
        password: Jira password
        search_options: Advanced search options dict
    """
    db = get_db()
    _active_jobs[job_id] = {"progress": 0, "total": 0, "status": "connecting"}

    try:
        # Update status to running
        db.update_job_status(job_id, JobStatus.RUNNING)
        logger.info(f"Starting manual analysis job {job_id}")
        logger.info(f"Virtual incident: {virtual_incident}")

        # Connect to Jira
        _active_jobs[job_id]["status"] = "connecting"
        loop = asyncio.get_event_loop()

        def connect_jira():
            client = JiraClient(username, password)
            success, message = client.connect()
            if not success:
                raise Exception(f"Failed to connect to Jira: {message}")
            return client

        client = await loop.run_in_executor(_executor, connect_jira)
        logger.info(f"Connected to Jira for manual analysis job {job_id}")

        # Define progress callback
        def progress_callback(current: int, total: int):
            _active_jobs[job_id].update({
                "progress": current,
                "total": total,
                "status": "extracting"
            })
            progress_pct = int((current / total) * 100) if total > 0 else 0
            db.update_job_status(job_id, JobStatus.RUNNING, progress=progress_pct, total_teccms=total)

        # Run extraction with virtual incident
        _active_jobs[job_id]["status"] = "extracting"

        def do_extraction():
            return extract_teccms_for_manual_analysis(
                client.client,
                virtual_incident,
                progress_callback,
                search_options=search_options
            )

        extraction_data = await loop.run_in_executor(_executor, do_extraction)
        logger.info(f"Manual extraction complete for job {job_id}: {len(extraction_data.get('tickets', []))} tickets")

        # Save extraction data
        db.save_extraction(job_id, extraction_data)

        # Calculate ranking
        _active_jobs[job_id]["status"] = "scoring"

        def do_scoring():
            return calculate_ranking(extraction_data)

        ranking_data = await loop.run_in_executor(_executor, do_scoring)
        logger.info(f"Scoring complete for manual job {job_id}: {len(ranking_data.get('ranking', []))} TECCMs ranked")

        # Save ranking
        from ..models import Weights
        db.save_ranking(job_id, Weights(), ranking_data)

        # Update job as completed
        include_ext = extraction_data.get('extraction_info', {}).get('search_options', {}).get('include_external_maintenance', False)
        if include_ext:
            total_teccms = len([t for t in extraction_data.get('tickets', []) if t.get('ticket_type') in ('CHANGE', 'EXTERNAL MAINTENANCE')])
        else:
            total_teccms = len([t for t in extraction_data.get('tickets', []) if t.get('ticket_type') == 'CHANGE'])
        db.update_job_status(job_id, JobStatus.COMPLETED, progress=100, total_teccms=total_teccms)

        _active_jobs[job_id]["status"] = "completed"
        logger.info(f"Manual analysis job {job_id} completed successfully")

    except Exception as e:
        logger.exception(f"Manual analysis job {job_id} failed: {e}")
        db.update_job_status(job_id, JobStatus.FAILED, error=str(e))
        _active_jobs[job_id]["status"] = "failed"
        _active_jobs[job_id]["error"] = str(e)

    finally:
        await asyncio.sleep(60)
        if job_id in _active_jobs:
            del _active_jobs[job_id]


def start_manual_analysis_job(
    job_id: str,
    virtual_incident: Dict[str, Any],
    username: str,
    password: str,
    search_options: Optional[Dict[str, Any]] = None
):
    """Start a manual analysis job in background."""
    asyncio.create_task(
        run_manual_analysis_job(job_id, virtual_incident, username, password, search_options)
    )
