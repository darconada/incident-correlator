"""
FastAPI main application.
INC-TECCM Correlation Analyzer Backend.
"""

import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .config import get_settings
from .routers import auth, analysis, config
from .db.storage import get_db

# Path to frontend static files
FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend" / "dist"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting INC-TECCM Correlation Analyzer...")
    settings = get_settings()
    logger.info(f"Jira URL: {settings.jira_url}")

    # Initialize database
    db = get_db()
    logger.info(f"Database initialized: {db.db_path}")

    yield

    # Shutdown
    logger.info("Shutting down...")


# Create FastAPI app
app = FastAPI(
    title="INC-TECCM Correlation Analyzer",
    description="API for analyzing correlations between incidents and changes in Jira",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(analysis.router, prefix=settings.api_prefix)
app.include_router(config.router, prefix=settings.api_prefix)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


# Serve frontend static files if they exist
if FRONTEND_DIR.exists():
    # Mount static assets (JS, CSS, etc.)
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

    # Catch-all route for SPA - must be last
    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        """Serve the SPA frontend for all non-API routes."""
        # Don't serve frontend for API routes
        if full_path.startswith("api/"):
            return {"error": "Not found"}, 404

        # Serve index.html for all other routes (SPA routing)
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"error": "Frontend not built"}, 404
else:
    @app.get("/")
    async def root():
        """Root endpoint when frontend is not available."""
        return {
            "name": "INC-TECCM Correlation Analyzer",
            "version": "1.0.0",
            "status": "running",
            "note": "Frontend not built. Run 'npm run build' in frontend directory."
        }
