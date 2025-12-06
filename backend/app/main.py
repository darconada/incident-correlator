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

    # Routes that should NOT be handled by SPA (let FastAPI handle them)
    EXCLUDED_PATHS = {"/api", "/docs", "/redoc", "/openapi.json", "/health"}

    @app.middleware("http")
    async def spa_middleware(request: Request, call_next):
        """Middleware to serve SPA for non-API routes."""
        path = request.url.path

        # Check if path should be handled by FastAPI
        should_skip = (
            path.startswith("/api/") or
            path.startswith("/assets/") or
            path in EXCLUDED_PATHS
        )

        if should_skip:
            # Let FastAPI handle it
            return await call_next(request)

        # For all other GET requests, serve the SPA
        if request.method == "GET":
            index_file = FRONTEND_DIR / "index.html"
            if index_file.exists():
                return FileResponse(index_file)

        # For non-GET or if index doesn't exist, continue to FastAPI
        return await call_next(request)

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
