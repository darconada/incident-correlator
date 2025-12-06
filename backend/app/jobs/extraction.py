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
from ..services.extractor import extract_inc_with_teccms
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
    password: str
):
    """
    Run extraction job in background.

    This function:
    1. Connects to Jira
    2. Extracts the INC and related TECCMs
    3. Calculates the initial ranking
    4. Saves everything to the database
    """
    db = get_db()
    _active_jobs[job_id] = {"progress": 0, "total": 0, "status": "connecting"}

    try:
        # Update status to running
        db.update_job_status(job_id, JobStatus.RUNNING)
        logger.info(f"Starting extraction job {job_id} for {inc_key}")

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
                progress_callback
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
    password: str
):
    """Start an extraction job in background."""
    asyncio.create_task(
        run_extraction_job(job_id, inc_key, window, username, password)
    )
