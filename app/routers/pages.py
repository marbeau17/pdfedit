"""Pages API router for page operations, preview, and download."""

import hashlib

from fastapi import APIRouter, HTTPException, Request, Form, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.services.session_service import SessionService
from app.services.pdf_service import PDFService

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def parse_page_ranges(s: str) -> set[int]:
    """Parse a page range string like '1,3-5' into a set of ints {1,3,4,5}."""
    result: set[int] = set()
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_str, end_str = part.split("-", 1)
            start = int(start_str.strip())
            end = int(end_str.strip())
            result.update(range(start, end + 1))
        else:
            result.add(int(part))
    return result


def _preview_grid_response(request: Request, session_id: str):
    """Build an HTMX preview grid fragment after a page mutation."""
    pdf_bytes = SessionService.get_pdf(session_id)
    if pdf_bytes is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    page_count = PDFService.get_page_count(pdf_bytes)
    return templates.TemplateResponse(
        request,
        "fragments/preview_grid.html",
        {
            "session_id": session_id,
            "page_count": page_count,
            "pages": list(range(1, page_count + 1)),
        },
    )


@router.post("/api/pages/remove")
async def remove_pages(
    request: Request,
    session_id: str = Form(...),
    pages: str = Form(...),
):
    """Remove specified pages from the PDF.

    Accepts form data with session_id and a pages string like "1,3-5".
    Returns an HTMX HTML fragment with the updated preview grid.
    """
    pdf_bytes = SessionService.get_pdf(session_id)
    if pdf_bytes is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    try:
        pages_to_remove = parse_page_ranges(pages)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid page range format")

    if not pages_to_remove:
        raise HTTPException(status_code=400, detail="No pages specified")

    new_bytes = PDFService.remove_pages(pdf_bytes, pages_to_remove)
    SessionService.update_pdf(session_id, new_bytes, operation="remove_pages")

    return _preview_grid_response(request, session_id)


class ReorderRequest(BaseModel):
    session_id: str
    order: list[int]


@router.post("/api/pages/reorder")
async def reorder_pages(request: Request, body: ReorderRequest):
    """Reorder pages in the PDF.

    Accepts JSON with session_id and an order list of page numbers.
    Returns an HTMX HTML fragment with the updated preview grid.
    """
    pdf_bytes = SessionService.get_pdf(body.session_id)
    if pdf_bytes is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    if not body.order:
        raise HTTPException(status_code=400, detail="No page order specified")

    new_bytes = PDFService.reorder_pages(pdf_bytes, body.order)
    SessionService.update_pdf(body.session_id, new_bytes, operation="reorder_pages")

    return _preview_grid_response(request, body.session_id)


@router.post("/api/undo")
async def undo(request: Request, session_id: str = Form(...)):
    """Undo the last operation on the PDF.

    Returns an HTMX HTML fragment with the restored preview grid.
    """
    if not SessionService.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found or expired")

    success = SessionService.undo(session_id)
    if not success:
        raise HTTPException(status_code=400, detail="Nothing to undo")

    return _preview_grid_response(request, session_id)


@router.get("/api/preview/{session_id}/{page_num}")
async def preview_page(session_id: str, page_num: int, request: Request):
    """Get a page thumbnail as a PNG image."""
    pdf_bytes = SessionService.get_pdf(session_id)
    if pdf_bytes is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    page_count = PDFService.get_page_count(pdf_bytes)
    if page_num < 1 or page_num > page_count:
        raise HTTPException(status_code=404, detail="Page number out of range")

    img_bytes = PDFService.get_page_thumbnail(pdf_bytes, page_num)

    # Generate ETag from content hash
    etag = hashlib.md5(img_bytes).hexdigest()

    # Check If-None-Match
    if_none_match = request.headers.get("if-none-match")
    if if_none_match and if_none_match == etag:
        return Response(status_code=304)

    return Response(
        content=img_bytes,
        media_type="image/png",
        headers={
            "Cache-Control": "private, max-age=30",
            "ETag": etag,
        },
    )


@router.get("/api/download/{session_id}")
async def download_pdf(session_id: str):
    """Download the processed PDF file."""
    pdf_bytes = SessionService.get_pdf(session_id)
    if pdf_bytes is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    filename = SessionService.get_filename(session_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
