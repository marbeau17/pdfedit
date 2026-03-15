"""Health check and system info endpoints."""
import platform
from datetime import datetime, UTC

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.session_service import SessionService


router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    active_sessions: int
    python_version: str
    platform: str


@router.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for monitoring."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(UTC).isoformat(),
        active_sessions=SessionService.active_count(),
        python_version=platform.python_version(),
        platform=platform.system(),
    )


@router.post("/api/cleanup")
async def cleanup_sessions():
    """Manually trigger expired session cleanup."""
    removed = SessionService.cleanup_expired()
    return {"removed": removed, "remaining": SessionService.active_count()}
