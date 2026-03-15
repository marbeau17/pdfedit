"""AI router - Gemini-powered slide analysis and generation."""
import uuid
import json
import asyncio

from fastapi import APIRouter, HTTPException, Request, Form
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates

from app.services.session_service import SessionService
from app.services.pdf_service import PDFService
from app.services.gemini_service import (
    GeminiService, create_task, get_task, TaskStatus,
)

router = APIRouter(prefix="/api/ai", tags=["ai"])
templates = Jinja2Templates(directory="app/templates")

# In-memory store for analysis results per session
_analysis_store: dict[str, dict[int, dict]] = {}  # session_id -> {page_num -> {xml, orig_img}}


@router.post("/analyze")
async def analyze_slides(
    request: Request,
    session_id: str = Form(...),
    pages: str = Form(...),
    api_key: str = Form(...),
):
    """Analyze specified pages using Gemini Vision API.

    Converts each page to an image, sends to Gemini for XML analysis.
    Returns HTMX fragment with analysis results for editing.
    """
    pdf_bytes = SessionService.get_pdf(session_id)
    if pdf_bytes is None:
        raise HTTPException(404, "Session not found")

    if not api_key.strip():
        raise HTTPException(400, "API key is required")

    # Parse page numbers
    page_nums = []
    for part in pages.replace("\u3001", ",").split(","):
        part = part.strip()
        if "-" in part:
            try:
                start, end = map(int, part.split("-", 1))
                page_nums.extend(range(start, end + 1))
            except ValueError:
                pass
        elif part.isdigit():
            page_nums.append(int(part))

    if not page_nums:
        raise HTTPException(400, "No valid pages specified")

    page_count = PDFService.get_page_count(pdf_bytes)
    page_nums = [p for p in page_nums if 1 <= p <= page_count]

    # Create task for SSE tracking
    task_id = uuid.uuid4().hex[:12]
    task = create_task(task_id, "analyze")
    task.total_pages = len(page_nums)

    # Initialize session analysis store
    if session_id not in _analysis_store:
        _analysis_store[session_id] = {}

    # Perform analysis
    gemini = GeminiService(api_key.strip())
    task.status = TaskStatus.ANALYZING
    results = []

    for i, p_num in enumerate(page_nums):
        task.completed_pages = i
        task.progress = int((i / len(page_nums)) * 100)

        # Get page image
        img_bytes = PDFService.get_page_thumbnail(pdf_bytes, p_num, dpi=150)

        # Analyze with Gemini
        xml_result = gemini.analyze_slide(img_bytes)

        if xml_result:
            _analysis_store[session_id][p_num] = {
                "xml": xml_result,
                "orig_img": img_bytes,
                "gen_img": None,
            }
            results.append({"page_num": p_num, "xml": xml_result, "success": True})
        else:
            results.append({"page_num": p_num, "xml": "", "success": False})

    task.completed_pages = len(page_nums)
    task.progress = 100
    task.status = TaskStatus.COMPLETED

    return templates.TemplateResponse(
        request,
        "fragments/ai_analysis_result.html",
        {
            "session_id": session_id,
            "results": results,
            "task_id": task_id,
            "total_analyzed": sum(1 for r in results if r["success"]),
            "total_failed": sum(1 for r in results if not r["success"]),
        },
    )


@router.post("/generate")
async def generate_slide(
    request: Request,
    session_id: str = Form(...),
    page_num: int = Form(...),
    xml_content: str = Form(...),
    api_key: str = Form(...),
):
    """Generate a slide image from XML and apply it to the PDF page.

    Uses Gemini to generate an image from XML, then replaces the page content.
    Returns HTMX fragment with the generated preview.
    """
    pdf_bytes = SessionService.get_pdf(session_id)
    if pdf_bytes is None:
        raise HTTPException(404, "Session not found")

    if not api_key.strip():
        raise HTTPException(400, "API key is required")

    gemini = GeminiService(api_key.strip())
    gen_img = gemini.generate_slide_image(xml_content)

    success = False
    if gen_img:
        # Store generated image
        if session_id in _analysis_store and page_num in _analysis_store[session_id]:
            _analysis_store[session_id][page_num]["gen_img"] = gen_img
        success = True

    return templates.TemplateResponse(
        request,
        "fragments/ai_generate_result.html",
        {
            "session_id": session_id,
            "page_num": page_num,
            "success": success,
            "has_image": gen_img is not None,
        },
    )


@router.post("/apply")
async def apply_generated(
    request: Request,
    session_id: str = Form(...),
    page_num: int = Form(...),
):
    """Apply a generated slide image to the PDF, replacing the page content."""
    pdf_bytes = SessionService.get_pdf(session_id)
    if pdf_bytes is None:
        raise HTTPException(404, "Session not found")

    store = _analysis_store.get(session_id, {})
    page_data = store.get(page_num)
    if not page_data or not page_data.get("gen_img"):
        raise HTTPException(400, "No generated image for this page")

    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    if page_num < 1 or page_num > len(doc):
        doc.close()
        raise HTTPException(400, "Invalid page number")

    page = doc[page_num - 1]
    page.clean_contents()
    # White out the page
    page.draw_rect(page.rect, color=(1, 1, 1), fill=(1, 1, 1))
    # Insert generated image
    margin = 30
    img_rect = fitz.Rect(margin, margin, page.rect.width - margin, page.rect.height - margin)
    page.insert_image(img_rect, stream=page_data["gen_img"])

    new_bytes = doc.tobytes(garbage=4, deflate=True)
    doc.close()

    SessionService.update_pdf(session_id, new_bytes, operation="ai_apply")
    page_count = PDFService.get_page_count(new_bytes)

    return templates.TemplateResponse(
        request,
        "fragments/preview_grid.html",
        {
            "session_id": session_id,
            "page_count": page_count,
            "pages": list(range(1, page_count + 1)),
        },
    )


@router.post("/save-xml")
async def save_xml(
    request: Request,
    session_id: str = Form(...),
    page_num: int = Form(...),
    xml_content: str = Form(...),
):
    """Save edited XML content for a page."""
    if session_id not in _analysis_store:
        _analysis_store[session_id] = {}

    if page_num not in _analysis_store[session_id]:
        _analysis_store[session_id][page_num] = {"xml": "", "orig_img": None, "gen_img": None}

    _analysis_store[session_id][page_num]["xml"] = xml_content
    _analysis_store[session_id][page_num]["gen_img"] = None  # Reset generated image

    return templates.TemplateResponse(
        request,
        "fragments/status_bar.html",
        {"message": f"Page {page_num} XML saved", "level": "success"},
    )


@router.get("/status/{task_id}")
async def ai_status_sse(task_id: str):
    """SSE endpoint for AI task progress."""
    async def event_stream():
        while True:
            task = get_task(task_id)
            if task is None:
                yield f"data: {json.dumps({'status': 'not_found'})}\n\n"
                break

            data = {
                "status": task.status.value,
                "progress": task.progress,
                "completed_pages": task.completed_pages,
                "total_pages": task.total_pages,
            }

            if task.error:
                data["error"] = task.error

            yield f"data: {json.dumps(data)}\n\n"

            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                break

            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
