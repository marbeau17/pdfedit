"""Tests for Phase 3 API endpoints (AI + Area Replace)."""
import os
import pytest
import fitz
from PIL import Image
import io
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


def _make_png(width=100, height=100, color=(255, 0, 0)) -> bytes:
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def _upload(client: AsyncClient) -> str:
    pdf = _make_pdf()
    resp = await client.post(
        "/api/upload",
        files={"pdf": ("test.pdf", pdf, "application/pdf")},
    )
    return resp.headers["hx-redirect"].rsplit("/", 1)[-1]


# --- AI Workshop Page Tests ---

async def test_ai_workshop_page(client: AsyncClient):
    """GET /ai-workshop/{sid} returns 200."""
    sid = await _upload(client)
    resp = await client.get(f"/ai-workshop/{sid}")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "AI" in resp.text


async def test_ai_workshop_invalid_session(client: AsyncClient):
    """GET /ai-workshop/invalid returns 404."""
    resp = await client.get("/ai-workshop/nonexistent123")
    assert resp.status_code == 404


# --- Area Replace Page Tests ---

async def test_area_replace_page(client: AsyncClient):
    """GET /area-replace/{sid} returns 200."""
    sid = await _upload(client)
    resp = await client.get(f"/area-replace/{sid}")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


async def test_area_replace_invalid_session(client: AsyncClient):
    """GET /area-replace/invalid returns 404."""
    resp = await client.get("/area-replace/nonexistent123")
    assert resp.status_code == 404


# --- Area Replace API Tests ---

async def test_area_upload_image(client: AsyncClient):
    """POST /api/area/upload-image accepts an image."""
    sid = await _upload(client)
    png = _make_png()
    resp = await client.post(
        "/api/area/upload-image",
        data={"session_id": sid},
        files={"image": ("replace.png", png, "image/png")},
    )
    assert resp.status_code == 200


async def test_area_replace_execution(client: AsyncClient):
    """POST /api/area/replace replaces an area successfully."""
    sid = await _upload(client)
    # First upload the replacement image
    png = _make_png(50, 50, (0, 255, 0))
    await client.post(
        "/api/area/upload-image",
        data={"session_id": sid},
        files={"image": ("replace.png", png, "image/png")},
    )
    # Then execute replacement
    resp = await client.post(
        "/api/area/replace",
        data={
            "session_id": sid,
            "page": "1",
            "x": "100",
            "y": "100",
            "width": "200",
            "height": "100",
            "keep_aspect": "false",
        },
    )
    assert resp.status_code == 200
    assert "Replaced" in resp.text


async def test_area_replace_no_image(client: AsyncClient):
    """POST /api/area/replace without uploaded image returns 400."""
    sid = await _upload(client)
    resp = await client.post(
        "/api/area/replace",
        data={
            "session_id": sid,
            "page": "1",
            "x": "10",
            "y": "10",
            "width": "50",
            "height": "50",
            "keep_aspect": "false",
        },
    )
    assert resp.status_code == 400


async def test_area_page_image(client: AsyncClient):
    """GET /api/area/page-image/{sid}/{page} returns PNG."""
    sid = await _upload(client)
    resp = await client.get(f"/api/area/page-image/{sid}/1")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content[:4] == b"\x89PNG"


# --- AI API Tests (without real Gemini key) ---

async def test_ai_analyze_no_key(client: AsyncClient):
    """POST /api/ai/analyze without API key returns 400."""
    sid = await _upload(client)
    resp = await client.post(
        "/api/ai/analyze",
        data={"session_id": sid, "pages": "1", "api_key": ""},
    )
    assert resp.status_code == 400


async def test_ai_generate_no_key(client: AsyncClient):
    """POST /api/ai/generate without API key returns 400."""
    sid = await _upload(client)
    resp = await client.post(
        "/api/ai/generate",
        data={
            "session_id": sid,
            "page_num": "1",
            "xml_content": "<slide><title>Test</title></slide>",
            "api_key": "",
        },
    )
    assert resp.status_code == 400


async def test_ai_save_xml(client: AsyncClient):
    """POST /api/ai/save-xml saves XML content."""
    sid = await _upload(client)
    resp = await client.post(
        "/api/ai/save-xml",
        data={
            "session_id": sid,
            "page_num": "1",
            "xml_content": "<slide><title>Hello</title></slide>",
        },
    )
    assert resp.status_code == 200


async def test_ai_status_sse(client: AsyncClient):
    """GET /api/ai/status/nonexistent returns SSE with not_found."""
    resp = await client.get("/api/ai/status/nonexistent")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
