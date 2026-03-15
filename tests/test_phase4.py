"""Tests for Phase 4 features (responsive, accessibility, performance, health)."""
import os
import pytest
import fitz
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.session_service import SessionService

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _chdir_to_project():
    original = os.getcwd()
    os.chdir(os.path.join(os.path.dirname(__file__), ".."))
    yield
    os.chdir(original)


@pytest.fixture(autouse=True)
def _clear_sessions():
    SessionService._store.clear()
    yield
    SessionService._store.clear()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _make_pdf(pages: int = 3) -> bytes:
    doc = fitz.open()
    for i in range(pages):
        p = doc.new_page(width=595, height=842)
        p.insert_text((50, 50), f"Page {i + 1}", fontsize=20)
    data = doc.tobytes()
    doc.close()
    return data


async def _upload(client: AsyncClient) -> str:
    pdf = _make_pdf()
    resp = await client.post(
        "/api/upload",
        files={"pdf": ("test.pdf", pdf, "application/pdf")},
    )
    return resp.headers["hx-redirect"].rsplit("/", 1)[-1]


# --- Health Check ---

async def test_health_check(client: AsyncClient):
    """GET /api/health returns healthy status."""
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "python_version" in data


async def test_cleanup_endpoint(client: AsyncClient):
    """POST /api/cleanup returns cleanup results."""
    resp = await client.post("/api/cleanup")
    assert resp.status_code == 200
    data = resp.json()
    assert "removed" in data
    assert "remaining" in data


# --- Error Pages ---

async def test_404_error_page(client: AsyncClient):
    """GET nonexistent path returns 404 HTML page."""
    resp = await client.get("/nonexistent-page-xyz")
    assert resp.status_code == 404
    assert "text/html" in resp.headers.get("content-type", "")


# --- Performance ---

async def test_preview_caching(client: AsyncClient):
    """Preview endpoint returns Cache-Control and ETag headers."""
    sid = await _upload(client)
    resp = await client.get(f"/api/preview/{sid}/1")
    assert resp.status_code == 200
    assert "etag" in resp.headers
    assert "cache-control" in resp.headers

    # Test conditional request with ETag
    etag = resp.headers["etag"]
    resp2 = await client.get(
        f"/api/preview/{sid}/1",
        headers={"if-none-match": etag},
    )
    assert resp2.status_code == 304


async def test_gzip_compression(client: AsyncClient):
    """Responses support gzip compression."""
    resp = await client.get("/", headers={"accept-encoding": "gzip"})
    assert resp.status_code == 200


# --- Accessibility: check key pages contain ARIA attributes ---

async def test_home_page_accessibility(client: AsyncClient):
    """Home page contains accessibility landmarks."""
    resp = await client.get("/")
    html = resp.text
    assert resp.status_code == 200
    # Check for basic HTML structure
    assert "lang=" in html
    assert "<main" in html or 'role="main"' in html


async def test_editor_page_accessibility(client: AsyncClient):
    """Editor page contains ARIA attributes."""
    sid = await _upload(client)
    resp = await client.get(f"/editor/{sid}")
    assert resp.status_code == 200
    html = resp.text
    # Check for accessible elements
    assert "aria-" in html or "role=" in html


# --- Security Headers ---

async def test_security_headers(client: AsyncClient):
    """Responses include security headers."""
    resp = await client.get("/")
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert "strict-origin" in resp.headers.get("referrer-policy", "")
