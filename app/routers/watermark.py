"""Watermark removal router."""
from fastapi import APIRouter, HTTPException, Request, Form
from fastapi.templating import Jinja2Templates

from app.services.session_service import SessionService
from app.services.pdf_service import PDFService

router = APIRouter(prefix="/api/watermark", tags=["watermark"])
templates = Jinja2Templates(directory="app/templates")


def _parse_int_list(s: str) -> list[int]:
    """Parse comma-separated integers, e.g. '1, 3, 5' -> [1, 3, 5]."""
    if not s or not s.strip():
        return []
    result = []
    for part in s.replace("\u3001", ",").split(","):
        part = part.strip()
        if part.isdigit():
            result.append(int(part))
    return result


@router.post("/remove")
async def remove_watermark(
    request: Request,
    session_id: str = Form(...),
    margin_x: int = Form(106),
    margin_y: int = Form(21),
    special_pages: str = Form(""),
):
    """Remove watermark from specified area of all pages.

    Fills the bottom-right corner area with the sampled adjacent color.
    Special pages use top-right corner color sampling instead.

    Returns HTMX fragment with result and updated preview grid.
    """
    pdf_bytes = SessionService.get_pdf(session_id)
    if pdf_bytes is None:
        raise HTTPException(404, "Session not found")

    special = _parse_int_list(special_pages)

    new_bytes = PDFService.remove_watermark(
        pdf_bytes,
        margin_x=margin_x,
        margin_y=margin_y,
        special_pages=special,
    )

    page_count = PDFService.get_page_count(new_bytes)
    SessionService.update_pdf(session_id, new_bytes, operation="watermark_remove")

    return templates.TemplateResponse(
        request,
        "fragments/watermark_result.html",
        {
            "session_id": session_id,
            "page_count": page_count,
            "margin_x": margin_x,
            "margin_y": margin_y,
            "special_pages": special,
            "success": True,
        },
    )
