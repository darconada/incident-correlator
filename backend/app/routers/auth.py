"""
Authentication router.
Handles Jira credentials validation and session management.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Response, Request, Depends
from pydantic import BaseModel

from ..config import get_settings
from ..models import LoginRequest, LoginResponse, SessionInfo
from ..services.jira_client import JiraClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

# Simple in-memory session store
# In production, use Redis or database-backed sessions
_sessions: dict[str, dict] = {}


class SessionData(BaseModel):
    username: str
    password: str
    display_name: str


def get_session_id(request: Request) -> Optional[str]:
    """Extract session ID from cookie."""
    return request.cookies.get("session_id")


def get_current_session(request: Request) -> Optional[SessionData]:
    """Get current session data."""
    session_id = get_session_id(request)
    if session_id and session_id in _sessions:
        return SessionData(**_sessions[session_id])
    return None


def require_auth(request: Request) -> SessionData:
    """Dependency that requires authentication."""
    session = get_current_session(request)
    if not session:
        # Check for default credentials from env
        settings = get_settings()
        if settings.jira_user and settings.jira_password:
            return SessionData(
                username=settings.jira_user,
                password=settings.jira_password,
                display_name=settings.jira_user
            )
        raise HTTPException(status_code=401, detail="Not authenticated")
    return session


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, response: Response):
    """
    Validate Jira credentials and create session.
    """
    logger.info(f"Login attempt for user: {request.username}")

    # Try to connect to Jira
    client = JiraClient(request.username, request.password)
    success, message = client.connect()

    if not success:
        logger.warning(f"Login failed for {request.username}: {message}")
        raise HTTPException(status_code=401, detail=message)

    # Create session
    import uuid
    session_id = str(uuid.uuid4())

    _sessions[session_id] = {
        "username": request.username,
        "password": request.password,  # Needed for Jira API calls
        "display_name": request.username,
    }

    # Set session cookie
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        max_age=get_settings().session_expire_hours * 3600,
        samesite="lax"
    )

    logger.info(f"Login successful for {request.username}")

    return LoginResponse(
        success=True,
        message=message,
        token=session_id
    )


@router.post("/logout")
async def logout(request: Request, response: Response):
    """
    Clear session and logout.
    """
    session_id = get_session_id(request)
    if session_id and session_id in _sessions:
        del _sessions[session_id]

    response.delete_cookie("session_id")

    return {"success": True, "message": "Logged out"}


@router.get("/session", response_model=SessionInfo)
async def get_session(request: Request):
    """
    Get current session info.
    """
    settings = get_settings()
    session = get_current_session(request)

    if session:
        return SessionInfo(
            authenticated=True,
            username=session.username,
            jira_url=settings.jira_url
        )

    # Check for default credentials
    if settings.jira_user and settings.jira_password:
        return SessionInfo(
            authenticated=True,
            username=settings.jira_user,
            jira_url=settings.jira_url
        )

    return SessionInfo(
        authenticated=False,
        username=None,
        jira_url=settings.jira_url
    )
