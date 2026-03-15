"""Tests for API endpoints."""
import os
import pytest
import fitz
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.session_service import SessionService

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _chdir_to_project():
    """Ensure the working directory is the project root so templates/static resolve."""
    original = os.getcwd()
    os.chdir(os.path.join(os.path.dirname(__file__), ".."))
    yield
    os.chdir(original)


@pytest.fixture
async def client():
    """Async test client (overrides conftest to avoid duplicate)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _make_pdf_bytes(pages: int = 3) -> bytes:
    """Helper to create a valid PDF with the given number of pages."""
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text((50, 50), f"Page {i + 1}", fontsize=20)
    data = doc.tobytes()
    doc.close()
    return data


async def _upload_pdf(client: AsyncClient, pdf_bytes: bytes | None = None) -> str:
    """Upload a PDF and return the session_id extracted from the redirect."""
    if pdf_bytes is None:
        pdf_bytes = _make_pdf_bytes()
    resp = await client.post(
        "/api/upload",
        files={"pdf": ("test.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200
    redirect = resp.headers.get("hx-redirect", "")
    assert "/editor/" in redirect
    session_id = redirect.rsplit("/", 1)[-1]
    return session_id


async def test_upload_pdf(client: AsyncClient):
    """POST /api/upload with a valid PDF returns an HX-Redirect to the editor."""
    pdf_bytes = _make_pdf_bytes()
    resp = await client.post(
        "/api/upload",
        files={"pdf": ("test.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200
    assert "hx-redirect" in resp.headers
    assert "/editor/" in resp.headers["hx-redirect"]


async def test_upload_invalid_file(client: AsyncClient):
    """POST /api/upload with a non-PDF file returns 400."""
    resp = await client.post(
        "/api/upload",
        files={"pdf": ("test.txt", b"not a pdf", "text/plain")},
    )
    assert resp.status_code == 400


async def test_preview_page(client: AsyncClient):
    """GET /api/preview/{sid}/1 returns a 200 with image/png."""
    sid = await _upload_pdf(client)
    resp = await client.get(f"/api/preview/{sid}/1")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    # Verify PNG magic bytes
    assert resp.content[:4] == b"\x89PNG"


async def test_download(client: AsyncClient):
    """GET /api/download/{sid} returns a 200 with application/pdf."""
    sid = await _upload_pdf(client)
    resp = await client.get(f"/api/download/{sid}")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:5] == b"%PDF-"


async def test_remove_pages(client: AsyncClient):
    """POST /api/pages/remove removes a page and returns 200."""
    sid = await _upload_pdf(client)
    resp = await client.post(
        "/api/pages/remove",
        data={"session_id": sid, "pages": "1"},
    )
    assert resp.status_code == 200
    # Verify the session PDF now has 2 pages
    from app.services.pdf_service import PDFService

    pdf_bytes = SessionService.get_pdf(sid)
    assert PDFService.get_page_count(pdf_bytes) == 2


async def test_root_page(client: AsyncClient):
    """GET / returns 200 with HTML content."""
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
