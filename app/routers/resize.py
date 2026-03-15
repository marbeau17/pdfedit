"""Resize router - unify page sizes."""
from fastapi import APIRouter, HTTPException, Request, Form
from fastapi.templating import Jinja2Templates

from app.services.session_service import SessionService
from app.services.pdf_service import PDFService

router = APIRouter(prefix="/api/resize", tags=["resize"])
templates = Jinja2Templates(directory="app/templates")


@router.post("/to-first-page")
async def resize_to_first_page(
    request: Request,
    session_id: str = Form(...),
):
    """Resize all pages to match the first page dimensions.

    Returns HTMX fragment with result and updated preview grid.
    """
    pdf_bytes = SessionService.get_pdf(session_id)
    if pdf_bytes is None:
        raise HTTPException(404, "Session not found")

    page_info_before = PDFService.get_page_info(pdf_bytes)
    if not page_info_before:
        raise HTTPException(400, "PDF has no pages")

    first_page = page_info_before[0]
    new_bytes = PDFService.resize_to_first_page(pdf_bytes)
    page_count = PDFService.get_page_count(new_bytes)

    SessionService.update_pdf(session_id, new_bytes, operation="resize")

    return templates.TemplateResponse(
        request,
        "fragments/resize_result.html",
        {
            "session_id": session_id,
            "page_count": page_count,
            "pages": list(range(1, page_count + 1)),
            "target_width": first_page["width"],
            "target_height": first_page["height"],
            "success": True,
        },
    )
