"""Area replace router - replace a selected area of a page with an image."""
import fitz

from fastapi import APIRouter, HTTPException, Request, Form, UploadFile, File
from fastapi.templating import Jinja2Templates

from app.services.session_service import SessionService
from app.services.pdf_service import PDFService

router = APIRouter(prefix="/api/area", tags=["area"])
templates = Jinja2Templates(directory="app/templates")

# In-memory store for replacement images
_replace_images: dict[str, bytes] = {}


@router.post("/upload-image")
async def upload_replacement_image(
    request: Request,
    session_id: str = Form(...),
    image: UploadFile = File(...),
):
    """Upload an image to use for area replacement.

    Returns HTMX fragment confirming upload.
    """
    if not SessionService.exists(session_id):
        raise HTTPException(404, "Session not found")

    content = await image.read()
    if not content:
        raise HTTPException(400, "Empty file")

    _replace_images[session_id] = content

    return templates.TemplateResponse(
        request,
        "fragments/area_image_preview.html",
        {
            "session_id": session_id,
            "image_filename": image.filename,
            "image_size": len(content),
        },
    )


@router.post("/replace")
async def replace_area(
    request: Request,
    session_id: str = Form(...),
    page: int = Form(...),
    x: int = Form(...),
    y: int = Form(...),
    width: int = Form(...),
    height: int = Form(...),
    keep_aspect: bool = Form(False),
):
    """Replace a rectangular area on a page with the uploaded image.

    Steps:
    1. Sample color adjacent to the target area
    2. Fill the target area with the sampled color (using redact annotation)
    3. Insert the replacement image into the area

    Returns updated preview grid.
    """
    pdf_bytes = SessionService.get_pdf(session_id)
    if pdf_bytes is None:
        raise HTTPException(404, "Session not found")

    image_data = _replace_images.get(session_id)
    if not image_data:
        raise HTTPException(400, "No replacement image uploaded. Please upload an image first.")

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    if page < 1 or page > len(doc):
        doc.close()
        raise HTTPException(400, f"Page {page} out of range (1-{len(doc)})")

    target_page = doc[page - 1]
    rect = fitz.Rect(x, y, x + width, y + height)

    # Sample adjacent color for fill
    probe_x = max(0, rect.x0 - 5)
    probe_y = max(0, rect.y0 - 5)
    probe_rect = fitz.Rect(probe_x, probe_y, probe_x + 1, probe_y + 1)
    pix = target_page.get_pixmap(clip=probe_rect, alpha=False)
    fill_color = (1, 1, 1)
    if pix.width > 0 and pix.height > 0:
        try:
            rgb = pix.pixel(0, 0)
            fill_color = (rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)
        except Exception:
            pass

    # Redact the area
    target_page.add_redact_annot(rect, fill=fill_color)
    target_page.apply_redactions()

    # Insert replacement image
    target_page.insert_image(rect, stream=image_data, keep_proportion=keep_aspect)

    new_bytes = doc.tobytes(garbage=4, deflate=True)
    doc.close()

    SessionService.update_pdf(session_id, new_bytes, operation="area_replace")
    page_count = PDFService.get_page_count(new_bytes)

    return templates.TemplateResponse(
        request,
        "fragments/area_replace_result.html",
        {
            "session_id": session_id,
            "page_num": page,
            "page_count": page_count,
            "pages": list(range(1, page_count + 1)),
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "success": True,
        },
    )


@router.get("/page-image/{session_id}/{page_num}")
async def get_page_image_for_selection(session_id: str, page_num: int):
    """Get a page image at 72 DPI for area selection UI.

    Returns PNG image for use in the canvas-based area selector.
    """
    from fastapi.responses import Response

    pdf_bytes = SessionService.get_pdf(session_id)
    if pdf_bytes is None:
        raise HTTPException(404, "Session not found")

    img_bytes = PDFService.get_page_thumbnail(pdf_bytes, page_num, dpi=72)
    return Response(content=img_bytes, media_type="image/png")
