import asyncio
import os
import shutil
import tempfile
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.routers import upload, pages, merge, optimize, watermark, branding, resize, ai, area_replace, health
from app.services.session_service import SessionService
from app.services.pdf_service import PDFService


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle management."""
    yield
    # Cleanup: remove expired session files on shutdown
    temp_dir = tempfile.gettempdir()
    session_dir = os.path.join(temp_dir, "pdf_workshop_sessions")
    if os.path.exists(session_dir):
        shutil.rmtree(session_dir, ignore_errors=True)


app = FastAPI(title="PDF Workshop Pro", lifespan=lifespan)

# Templates
templates = Jinja2Templates(directory="app/templates")

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(upload.router)
app.include_router(pages.router)
app.include_router(merge.router)
app.include_router(optimize.router)
app.include_router(watermark.router)
app.include_router(branding.router)
app.include_router(resize.router)
app.include_router(ai.router)
app.include_router(area_replace.router)
app.include_router(health.router)


# Security middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# GZip compression middleware
app.add_middleware(GZipMiddleware, minimum_size=500)

# CORS middleware (allow all origins in dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return templates.TemplateResponse(
        request, "error.html",
        {"status_code": 404, "title": "Page Not Found", "message": "The page you're looking for doesn't exist."},
        status_code=404,
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    return templates.TemplateResponse(
        request, "error.html",
        {"status_code": 500, "title": "Server Error", "message": "Something went wrong. Please try again."},
        status_code=500,
    )


# Routes
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Render the main upload/landing page."""
    return templates.TemplateResponse(request, "index.html", {
        "title": "PDF Workshop Pro",
    })


@app.get("/editor/{session_id}", response_class=HTMLResponse)
async def editor(request: Request, session_id: str):
    """Render the PDF editor page for a given session."""
    pdf_bytes = SessionService.get_pdf(session_id)
    if pdf_bytes is None:
        return JSONResponse(status_code=404, content={"detail": "Session not found"})
    page_count = PDFService.get_page_count(pdf_bytes)
    filename = SessionService.get_filename(session_id)
    return templates.TemplateResponse(request, "editor.html", {
        "title": "PDF Workshop Pro - Editor",
        "session_id": session_id,
        "filename": filename,
        "page_count": page_count,
        "pages": range(1, page_count + 1),
    })


@app.get("/merge", response_class=HTMLResponse)
async def merge_page(request: Request):
    """Render the PDF merge page."""
    return templates.TemplateResponse(request, "merge.html", {
        "title": "PDF Workshop Pro - Merge",
    })


@app.get("/ai-workshop/{session_id}", response_class=HTMLResponse)
async def ai_workshop(request: Request, session_id: str):
    """Render the AI Workshop page."""
    pdf_bytes = SessionService.get_pdf(session_id)
    if pdf_bytes is None:
        return JSONResponse(status_code=404, content={"detail": "Session not found"})
    page_count = PDFService.get_page_count(pdf_bytes)
    filename = SessionService.get_filename(session_id)
    return templates.TemplateResponse(request, "ai_workshop.html", {
        "title": "PDF Workshop Pro - AI Workshop",
        "session_id": session_id,
        "filename": filename,
        "page_count": page_count,
        "pages": list(range(1, page_count + 1)),
    })


@app.get("/area-replace/{session_id}", response_class=HTMLResponse)
async def area_replace_page(request: Request, session_id: str):
    """Render the Area Replace page."""
    pdf_bytes = SessionService.get_pdf(session_id)
    if pdf_bytes is None:
        return JSONResponse(status_code=404, content={"detail": "Session not found"})
    page_count = PDFService.get_page_count(pdf_bytes)
    filename = SessionService.get_filename(session_id)
    return templates.TemplateResponse(request, "area_replace.html", {
        "title": "PDF Workshop Pro - Area Replace",
        "session_id": session_id,
        "filename": filename,
        "page_count": page_count,
        "pages": list(range(1, page_count + 1)),
    })
