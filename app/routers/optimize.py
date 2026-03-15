"""Optimize router - PDF file size optimization."""
from fastapi import APIRouter, HTTPException, Request, Form
from fastapi.templating import Jinja2Templates

from app.services.session_service import SessionService
from app.services.pdf_service import PDFService

router = APIRouter(prefix="/api/optimize", tags=["optimize"])
templates = Jinja2Templates(directory="app/templates")


@router.post("/execute")
async def optimize_pdf(request: Request, session_id: str = Form(...)):
    """Optimize a PDF by removing unused objects and compressing streams.

    Returns an HTMX fragment showing optimization results.
    """
    pdf_bytes = SessionService.get_pdf(session_id)
    if pdf_bytes is None:
        raise HTTPException(404, "Session not found")

    optimized_bytes, original_size, optimized_size = PDFService.optimize(pdf_bytes)

    reduction = original_size - optimized_size
    if reduction > 0:
        SessionService.update_pdf(session_id, optimized_bytes, operation="optimize")

    reduction_percent = (reduction / original_size * 100) if original_size > 0 else 0

    return templates.TemplateResponse(
        request,
        "fragments/optimize_result.html",
        {
            "session_id": session_id,
            "original_size": original_size,
            "optimized_size": optimized_size,
            "reduction": reduction,
            "reduction_percent": reduction_percent,
            "success": reduction > 0,
        },
    )
