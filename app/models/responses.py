"""Pydantic response models for API endpoints."""
from pydantic import BaseModel


class UploadResponse(BaseModel):
    session_id: str
    filename: str
    page_count: int


class OperationResponse(BaseModel):
    success: bool
    message: str
    page_count: int = 0


class OptimizeResponse(BaseModel):
    success: bool
    original_size: int
    optimized_size: int
    reduction_percent: float


class PageInfo(BaseModel):
    page_num: int
    width: float
    height: float


class SessionInfo(BaseModel):
    session_id: str
    filename: str
    page_count: int
    has_undo: bool
