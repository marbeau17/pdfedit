"""PDF Workshop Pro - FastAPI Application (Local-First Architecture).

All PDF processing happens client-side in the browser.
Server only serves HTML pages and proxies AI API calls.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.gzip import GZipMiddleware

from app.routers import ai, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="PDF Workshop Pro", lifespan=lifespan)

templates = Jinja2Templates(directory="app/templates")

app.mount("/static", StaticFiles(directory="static"), name="static")

# Routers (minimal - AI proxy and health only)
app.include_router(ai.router)
app.include_router(health.router)

# Middleware
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return templates.TemplateResponse(
        request, "error.html",
        {"status_code": 404, "title": "Page Not Found",
         "message": "The page you're looking for doesn't exist."},
        status_code=404,
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    return templates.TemplateResponse(
        request, "error.html",
        {"status_code": 500, "title": "Server Error",
         "message": "Something went wrong. Please try again."},
        status_code=500,
    )


# Page routes (serve HTML only - all logic is client-side)
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request, "index.html", {
        "title": "PDF Workshop Pro",
    })


@app.get("/editor", response_class=HTMLResponse)
async def editor(request: Request):
    return templates.TemplateResponse(request, "editor.html", {
        "title": "PDF Workshop Pro - Editor",
    })


@app.get("/merge", response_class=HTMLResponse)
async def merge_page(request: Request):
    return templates.TemplateResponse(request, "merge.html", {
        "title": "PDF Workshop Pro - Merge",
    })


@app.get("/ai-workshop", response_class=HTMLResponse)
async def ai_workshop(request: Request):
    return templates.TemplateResponse(request, "ai_workshop.html", {
        "title": "PDF Workshop Pro - AI Workshop",
    })


@app.get("/area-replace", response_class=HTMLResponse)
async def area_replace_page(request: Request):
    return templates.TemplateResponse(request, "area_replace.html", {
        "title": "PDF Workshop Pro - Area Replace",
    })
