"""Pydantic request models for API endpoints."""
from pydantic import BaseModel, Field


class PageRemoveRequest(BaseModel):
    session_id: str
    pages: str = Field(..., example="1,3-5", description="Pages to remove (1-based)")


class PageReorderRequest(BaseModel):
    session_id: str
    order: list[int] = Field(..., example=[3, 1, 2], description="New page order (1-based)")


class MergeRequest(BaseModel):
    session_ids: list[str] = Field(..., description="Session IDs of PDFs to merge")


class OptimizeRequest(BaseModel):
    session_id: str


class WatermarkRemoveRequest(BaseModel):
    session_id: str
    margin_x: int = 106
    margin_y: int = 21
    special_pages: list[int] = []


class BrandingRequest(BaseModel):
    session_id: str
    target_pages: str | None = None
    enable_logo: bool = True
    enable_page_num: bool = True
    skip_first_logo: bool = True
    skip_first_num: bool = True
    logo_right_margin: int = 30
    logo_top_margin: int = 20
    logo_width: int = 100
    logo_height: int = 50
    page_num_right: int = 50
    page_num_bottom: int = 30


class AreaReplaceRequest(BaseModel):
    session_id: str
    page: int
    x: int
    y: int
    width: int
    height: int
    keep_aspect: bool = False


class AIAnalyzeRequest(BaseModel):
    session_id: str
    pages: str
    api_key: str


class AIGenerateRequest(BaseModel):
    session_id: str
    page: int
    xml_content: str
    api_key: str


class AnalyzeTextRequest(BaseModel):
    text: str = Field(..., description="Extracted PDF text to analyze")
    api_key: str
    analysis_type: str = Field(
        "summarize",
        description="Type of analysis: summarize, improve, translate, extract_data",
    )
