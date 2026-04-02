"""PDF Workshop Pro - FastAPI Application (Local-First Architecture).

All PDF processing happens client-side in the browser.
Server only serves HTML pages and proxies AI API calls.
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.gzip import GZipMiddleware

from app.middleware.rate_limit import RateLimitMiddleware
from app.routers import ai, health

# --- CORS allowed origins ---
_DEFAULT_ORIGINS = [
    "https://pdfedit-livid.vercel.app",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

_env_origins = os.environ.get("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS: list[str] = (
    [o.strip() for o in _env_origins.split(",") if o.strip()]
    if _env_origins
    else _DEFAULT_ORIGINS
)

# --- Content-Security-Policy ---
CSP_POLICY = "; ".join([
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://unpkg.com https://cdn.jsdelivr.net blob:",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    "connect-src 'self' https://cdn.tailwindcss.com https://unpkg.com https://cdn.jsdelivr.net",
    "worker-src 'self' blob:",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])


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
app.add_middleware(RateLimitMiddleware, ai_limit=30, api_limit=100)
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
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
    response.headers["Content-Security-Policy"] = CSP_POLICY
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=()"
    )
    return response


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return templates.TemplateResponse(
        request, "error.html",
        {"status_code": 404, "title": "ページが見つかりません",
         "message": "お探しのページは移動または削除された可能性があります。"},
        status_code=404,
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    return templates.TemplateResponse(
        request, "error.html",
        {"status_code": 500, "title": "サーバーエラーが発生しました",
         "message": "しばらくしてからもう一度お試しください。"},
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
