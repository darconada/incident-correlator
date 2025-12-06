"""
SQLite storage for jobs and analysis results.
"""

import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from ..models import JobStatus, JobInfo, Weights, Penalties, Bonuses, Thresholds


class Database:
    """SQLite database manager."""

    def __init__(self, db_path: str = "data/correlator.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.executescript("""
                -- Jobs table
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    inc TEXT NOT NULL,
                    window TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    progress INTEGER DEFAULT 0,
                    total_teccms INTEGER,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    job_type TEXT DEFAULT 'standard',
                    username TEXT,
                    search_summary TEXT
                );

                -- Extraction data (JSON blob)
                CREATE TABLE IF NOT EXISTS extractions (
                    job_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
                );

                -- Ranking results (JSON blob)
                CREATE TABLE IF NOT EXISTS rankings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    weights TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
                );

                -- Config table
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                -- Indexes
                CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
                CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_rankings_job ON rankings(job_id);
            """)

            # Migration: add new columns if they don't exist
            try:
                conn.execute("ALTER TABLE jobs ADD COLUMN job_type TEXT DEFAULT 'standard'")
            except:
                pass  # Column already exists
            try:
                conn.execute("ALTER TABLE jobs ADD COLUMN username TEXT")
            except:
                pass
            try:
                conn.execute("ALTER TABLE jobs ADD COLUMN search_summary TEXT")
            except:
                pass

    # ══════════════════════════════════════════════════════════════════════════
    #  JOBS
    # ══════════════════════════════════════════════════════════════════════════

    def create_job(
        self,
        inc: str,
        window: str,
        job_type: str = "standard",
        username: str = None,
        search_summary: str = None
    ) -> str:
        """Create a new job and return its ID."""
        job_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + "Z"

        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO jobs (job_id, inc, window, status, created_at, job_type, username, search_summary)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (job_id, inc.upper(), window, JobStatus.PENDING.value, now, job_type, username, search_summary)
            )

        return job_id

    def get_job(self, job_id: str) -> Optional[JobInfo]:
        """Get job info by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()

            if not row:
                return None

            return JobInfo(
                job_id=row["job_id"],
                inc=row["inc"],
                window=row["window"],
                status=JobStatus(row["status"]),
                progress=row["progress"] or 0,
                total_teccms=row["total_teccms"],
                error=row["error"],
                created_at=datetime.fromisoformat(row["created_at"].replace("Z", "")),
                completed_at=datetime.fromisoformat(row["completed_at"].replace("Z", "")) if row["completed_at"] else None,
                job_type=row["job_type"] if "job_type" in row.keys() else "standard",
                username=row["username"] if "username" in row.keys() else None,
                search_summary=row["search_summary"] if "search_summary" in row.keys() else None,
            )

    def get_jobs(self, limit: int = 50) -> List[JobInfo]:
        """Get recent jobs."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()

            return [
                JobInfo(
                    job_id=row["job_id"],
                    inc=row["inc"],
                    window=row["window"],
                    status=JobStatus(row["status"]),
                    progress=row["progress"] or 0,
                    total_teccms=row["total_teccms"],
                    error=row["error"],
                    created_at=datetime.fromisoformat(row["created_at"].replace("Z", "")),
                    completed_at=datetime.fromisoformat(row["completed_at"].replace("Z", "")) if row["completed_at"] else None,
                    job_type=row["job_type"] if "job_type" in row.keys() else "standard",
                    username=row["username"] if "username" in row.keys() else None,
                    search_summary=row["search_summary"] if "search_summary" in row.keys() else None,
                )
                for row in rows
            ]

    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        progress: int = None,
        total_teccms: int = None,
        error: str = None
    ):
        """Update job status and progress."""
        with self._get_connection() as conn:
            updates = ["status = ?"]
            params = [status.value]

            if progress is not None:
                updates.append("progress = ?")
                params.append(progress)

            if total_teccms is not None:
                updates.append("total_teccms = ?")
                params.append(total_teccms)

            if error is not None:
                updates.append("error = ?")
                params.append(error)

            if status in (JobStatus.COMPLETED, JobStatus.FAILED):
                updates.append("completed_at = ?")
                params.append(datetime.utcnow().isoformat() + "Z")

            params.append(job_id)

            conn.execute(
                f"UPDATE jobs SET {', '.join(updates)} WHERE job_id = ?",
                params
            )

    def delete_job(self, job_id: str) -> bool:
        """Delete a job and its related data."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM rankings WHERE job_id = ?", (job_id,))
            conn.execute("DELETE FROM extractions WHERE job_id = ?", (job_id,))
            result = conn.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
            return result.rowcount > 0

    # ══════════════════════════════════════════════════════════════════════════
    #  EXTRACTIONS
    # ══════════════════════════════════════════════════════════════════════════

    def save_extraction(self, job_id: str, data: Dict[str, Any]):
        """Save extraction data."""
        with self._get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO extractions (job_id, data)
                   VALUES (?, ?)""",
                (job_id, json.dumps(data, ensure_ascii=False))
            )

    def get_extraction(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get extraction data."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT data FROM extractions WHERE job_id = ?", (job_id,)
            ).fetchone()

            if not row:
                return None

            return json.loads(row["data"])

    # ══════════════════════════════════════════════════════════════════════════
    #  RANKINGS
    # ══════════════════════════════════════════════════════════════════════════

    def save_ranking(self, job_id: str, weights: Weights, data: Dict[str, Any]):
        """Save ranking result."""
        now = datetime.utcnow().isoformat() + "Z"

        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO rankings (job_id, weights, data, created_at)
                   VALUES (?, ?, ?, ?)""",
                (job_id, json.dumps(weights.model_dump()), json.dumps(data, ensure_ascii=False), now)
            )

    def get_latest_ranking(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get the latest ranking for a job."""
        with self._get_connection() as conn:
            row = conn.execute(
                """SELECT data FROM rankings
                   WHERE job_id = ?
                   ORDER BY created_at DESC LIMIT 1""",
                (job_id,)
            ).fetchone()

            if not row:
                return None

            return json.loads(row["data"])

    # ══════════════════════════════════════════════════════════════════════════
    #  CONFIG
    # ══════════════════════════════════════════════════════════════════════════

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get config value."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM config WHERE key = ?", (key,)
            ).fetchone()

            if not row:
                return default

            return json.loads(row["value"])

    def set_config(self, key: str, value: Any):
        """Set config value."""
        with self._get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO config (key, value)
                   VALUES (?, ?)""",
                (key, json.dumps(value))
            )

    def get_weights(self) -> Weights:
        """Get default weights from config."""
        data = self.get_config("weights")
        if data:
            return Weights(**data)
        return Weights()

    def set_weights(self, weights: Weights):
        """Save default weights to config."""
        self.set_config("weights", weights.model_dump())

    def get_top_results(self) -> int:
        """Get default top results from config."""
        value = self.get_config("top_results")
        if value is not None:
            return value
        from ..config import get_settings
        return get_settings().default_top_results

    def set_top_results(self, top: int):
        """Save default top results to config."""
        self.set_config("top_results", top)

    def get_penalties(self) -> Penalties:
        """Get penalties from config."""
        data = self.get_config("penalties")
        if data:
            return Penalties(**data)
        return Penalties()

    def set_penalties(self, penalties: Penalties):
        """Save penalties to config."""
        self.set_config("penalties", penalties.model_dump())

    def get_bonuses(self) -> Bonuses:
        """Get bonuses from config."""
        data = self.get_config("bonuses")
        if data:
            return Bonuses(**data)
        return Bonuses()

    def set_bonuses(self, bonuses: Bonuses):
        """Save bonuses to config."""
        self.set_config("bonuses", bonuses.model_dump())

    def get_thresholds(self) -> Thresholds:
        """Get thresholds from config."""
        data = self.get_config("thresholds")
        if data:
            return Thresholds(**data)
        return Thresholds()

    def set_thresholds(self, thresholds: Thresholds):
        """Save thresholds to config."""
        self.set_config("thresholds", thresholds.model_dump())


# Singleton instance
_db: Optional[Database] = None


def get_db() -> Database:
    """Get database instance."""
    global _db
    if _db is None:
        from ..config import get_settings
        settings = get_settings()
        _db = Database(settings.database_path)
    return _db
