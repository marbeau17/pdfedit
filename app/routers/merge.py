"""Merge router - handles merging multiple PDF files."""
from fastapi import APIRouter, UploadFile, File, HTTPException, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import List

from app.services.session_service import SessionService
from app.services.pdf_service import PDFService

router = APIRouter(prefix="/api/merge", tags=["merge"])
templates = Jinja2Templates(directory="app/templates")

ALLOWED_MIME_TYPES = {"application/pdf"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
PDF_MAGIC_BYTES = b"%PDF-"


@router.post("/upload")
async def upload_for_merge(
    request: Request, pdfs: List[UploadFile] = File(...)
):
    """Upload multiple PDF files for merging.

    Validates each file (MIME type, magic bytes), stores each in a
    separate session, and returns an HTMX fragment showing the list
    of uploaded files.
    """
    files_info: list[dict] = []

    for pdf in pdfs:
        # Validate MIME type
        if pdf.content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                400,
                f"File '{pdf.filename}' is not a PDF (got {pdf.content_type})",
            )

        # Read content
        content = await pdf.read()

        # Validate size
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                413, f"File '{pdf.filename}' is too large (max 50MB)"
            )

        # Validate magic bytes
        if not content.startswith(PDF_MAGIC_BYTES):
            raise HTTPException(
                400, f"File '{pdf.filename}' is not a valid PDF"
            )

        # Create a session for this file
        filename = pdf.filename or "document.pdf"
        session_id = SessionService.create(content, filename)
        page_count = PDFService.get_page_count(content)

        files_info.append(
            {
                "session_id": session_id,
                "filename": filename,
                "page_count": page_count,
            }
        )

    return templates.TemplateResponse(
        request,
        "fragments/merge_list.html",
        {"files": files_info},
    )


@router.post("/execute")
async def execute_merge(
    request: Request,
    target_session_id: str = Form(...),
    merge_session_ids: str = Form(...),
):
    """Merge multiple PDFs into a single document.

    Accepts the target session ID and a comma-separated list of session
    IDs to merge (in order). Collects PDF bytes from all sessions,
    merges them, creates a new session with the result, and returns
    an HX-Redirect to the editor.
    """
    # Parse the comma-separated session IDs
    session_ids = [
        sid.strip()
        for sid in merge_session_ids.split(",")
        if sid.strip()
    ]

    if not session_ids:
        raise HTTPException(400, "No session IDs provided for merging")

    # Collect PDF bytes from all sessions in order
    pdf_bytes_list: list[bytes] = []

    # Include the target session first
    target_bytes = SessionService.get_pdf(target_session_id)
    if target_bytes is None:
        raise HTTPException(404, f"Target session '{target_session_id}' not found")
    pdf_bytes_list.append(target_bytes)

    # Then add the merge sessions in order
    for sid in session_ids:
        pdf_bytes = SessionService.get_pdf(sid)
        if pdf_bytes is None:
            raise HTTPException(404, f"Session '{sid}' not found or expired")
        pdf_bytes_list.append(pdf_bytes)

    # Merge all PDFs
    merged_bytes = PDFService.merge_pdfs(pdf_bytes_list)

    # Build a merged filename from the target
    target_filename = SessionService.get_filename(target_session_id)
    merged_filename = target_filename.replace(".pdf", "_merged.pdf")

    # Create a new session with the merged result
    new_session_id = SessionService.create(merged_bytes, merged_filename)

    # Return HX-Redirect to the editor with the new session
    response = HTMLResponse(content="", status_code=200)
    response.headers["HX-Redirect"] = f"/editor/{new_session_id}"
    return response


@router.post("/reorder")
async def reorder_merge_list(request: Request):
    """Reorder the merge list based on drag-drop.

    Accepts JSON with a ``session_ids`` list in the new desired order
    and returns an updated merge list fragment.
    """
    body = await request.json()
    session_ids: list[str] = body.get("session_ids", [])

    if not session_ids:
        raise HTTPException(400, "No session IDs provided")

    files_info: list[dict] = []
    for sid in session_ids:
        pdf_bytes = SessionService.get_pdf(sid)
        if pdf_bytes is None:
            raise HTTPException(404, f"Session '{sid}' not found or expired")

        filename = SessionService.get_filename(sid)
        page_count = PDFService.get_page_count(pdf_bytes)

        files_info.append(
            {
                "session_id": sid,
                "filename": filename,
                "page_count": page_count,
            }
        )

    return templates.TemplateResponse(
        request,
        "fragments/merge_list.html",
        {"files": files_info},
    )
