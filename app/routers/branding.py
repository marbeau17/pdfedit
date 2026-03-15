"""Branding router - apply logo, page numbers, and footer overlays."""
from fastapi import APIRouter, HTTPException, Request, Form, UploadFile, File
from fastapi.templating import Jinja2Templates
from typing import Optional

from app.services.session_service import SessionService
from app.services.pdf_service import PDFService
from app.services.branding_service import BrandingService

router = APIRouter(prefix="/api/branding", tags=["branding"])
templates = Jinja2Templates(directory="app/templates")

# In-memory logo storage per session
_logo_store: dict[str, bytes] = {}


@router.post("/upload-logo")
async def upload_logo(
    request: Request,
    session_id: str = Form(...),
    logo: UploadFile = File(...),
):
    """Upload a logo image for branding.

    Returns an HTMX fragment showing the uploaded logo preview.
    """
    if not SessionService.exists(session_id):
        raise HTTPException(404, "Session not found")

    content = await logo.read()
    if not content:
        raise HTTPException(400, "Empty file")

    _logo_store[session_id] = content

    return templates.TemplateResponse(
        request,
        "fragments/branding_logo_preview.html",
        {
            "session_id": session_id,
            "logo_filename": logo.filename,
            "logo_size": len(content),
            "has_logo": True,
        },
    )


@router.post("/apply")
async def apply_branding(
    request: Request,
    session_id: str = Form(...),
    target_pages: str = Form(""),
    enable_logo: bool = Form(True),
    enable_page_num: bool = Form(True),
    skip_first_logo: bool = Form(True),
    skip_first_num: bool = Form(True),
    logo_right_margin: int = Form(30),
    logo_top_margin: int = Form(20),
    logo_width: int = Form(100),
    logo_height: int = Form(50),
    page_num_right: int = Form(50),
    page_num_bottom: int = Form(30),
):
    """Apply branding overlays to the PDF.

    Returns HTMX fragment with result and updated preview.
    """
    pdf_bytes = SessionService.get_pdf(session_id)
    if pdf_bytes is None:
        raise HTTPException(404, "Session not found")

    logo_bytes = _logo_store.get(session_id)
    parsed_targets = BrandingService.parse_page_ranges(target_pages)

    new_bytes = BrandingService.apply_branding(
        pdf_bytes=pdf_bytes,
        logo_bytes=logo_bytes,
        target_pages=parsed_targets,
        enable_logo=enable_logo,
        enable_page_num=enable_page_num,
        skip_first_logo=skip_first_logo,
        skip_first_num=skip_first_num,
        logo_right_margin=logo_right_margin,
        logo_top_margin=logo_top_margin,
        logo_width=logo_width,
        logo_height=logo_height,
        page_num_right=page_num_right,
        page_num_bottom=page_num_bottom,
    )

    page_count = PDFService.get_page_count(new_bytes)
    SessionService.update_pdf(session_id, new_bytes, operation="branding")

    return templates.TemplateResponse(
        request,
        "fragments/branding_result.html",
        {
            "session_id": session_id,
            "page_count": page_count,
            "pages": list(range(1, page_count + 1)),
            "success": True,
            "target_pages": target_pages or "all",
            "enable_logo": enable_logo,
            "enable_page_num": enable_page_num,
        },
    )
