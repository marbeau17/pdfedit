"""Health check endpoint."""
import platform
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    architecture: str
    python_version: str
    platform: str


@router.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        architecture="local-first",
        python_version=platform.python_version(),
        platform=platform.system(),
    )
