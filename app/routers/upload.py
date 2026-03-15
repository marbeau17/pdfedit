"""Upload router - handles PDF file uploads."""
from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.services.session_service import SessionService
from app.services.pdf_service import PDFService

router = APIRouter(prefix="/api", tags=["upload"])
templates = Jinja2Templates(directory="app/templates")

ALLOWED_MIME_TYPES = {"application/pdf"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
PDF_MAGIC_BYTES = b"%PDF-"


@router.post("/upload")
async def upload_pdf(request: Request, pdf: UploadFile = File(...)):
    """Upload a PDF file and create a session.

    Returns an HTMX redirect to the editor page.
    """
    # Validate MIME type
    if pdf.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(400, "Only PDF files are allowed")

    # Read file
    content = await pdf.read()

    # Validate size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, "File too large (max 50MB)")

    # Validate magic bytes
    if not content.startswith(PDF_MAGIC_BYTES):
        raise HTTPException(400, "Invalid PDF file")

    # Create session
    filename = pdf.filename or "document.pdf"
    session_id = SessionService.create(content, filename)
    page_count = PDFService.get_page_count(content)

    # Return HTMX redirect to editor
    response = HTMLResponse(content="", status_code=200)
    response.headers["HX-Redirect"] = f"/editor/{session_id}"
    return response


@router.post("/upload/additional/{session_id}")
async def upload_additional(session_id: str, pdf: UploadFile = File(...)):
    """Upload an additional PDF for merging."""
    if not SessionService.exists(session_id):
        raise HTTPException(404, "Session not found")

    if pdf.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(400, "Only PDF files are allowed")

    content = await pdf.read()
    if not content.startswith(PDF_MAGIC_BYTES):
        raise HTTPException(400, "Invalid PDF file")

    # Create a separate session for the additional PDF
    filename = pdf.filename or "document.pdf"
    new_session_id = SessionService.create(content, filename)

    return {"session_id": new_session_id, "filename": filename}
