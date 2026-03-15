"""Tests for Phase 2 API endpoints."""
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


async def test_optimize(client: AsyncClient):
    """POST /api/optimize/execute returns optimization result."""
    sid = await _upload(client)
    resp = await client.post(
        "/api/optimize/execute",
        data={"session_id": sid},
    )
    assert resp.status_code == 200
    assert "Optimiz" in resp.text


async def test_watermark_remove(client: AsyncClient):
    """POST /api/watermark/remove returns success."""
    sid = await _upload(client)
    resp = await client.post(
        "/api/watermark/remove",
        data={"session_id": sid, "margin_x": "106", "margin_y": "21", "special_pages": ""},
    )
    assert resp.status_code == 200
    assert "Watermark" in resp.text


async def test_branding_apply(client: AsyncClient):
    """POST /api/branding/apply returns success."""
    sid = await _upload(client)
    resp = await client.post(
        "/api/branding/apply",
        data={
            "session_id": sid,
            "target_pages": "",
            "enable_logo": "true",
            "enable_page_num": "true",
            "skip_first_logo": "true",
            "skip_first_num": "true",
            "logo_right_margin": "30",
            "logo_top_margin": "20",
            "logo_width": "100",
            "logo_height": "50",
            "page_num_right": "50",
            "page_num_bottom": "30",
        },
    )
    assert resp.status_code == 200
    assert "Branding" in resp.text


async def test_branding_upload_logo(client: AsyncClient):
    """POST /api/branding/upload-logo accepts a logo file."""
    sid = await _upload(client)
    from PIL import Image
    import io
    img = Image.new("RGBA", (100, 50), (255, 0, 0, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    logo_bytes = buf.getvalue()

    resp = await client.post(
        "/api/branding/upload-logo",
        data={"session_id": sid},
        files={"logo": ("logo.png", logo_bytes, "image/png")},
    )
    assert resp.status_code == 200


async def test_resize_to_first_page(client: AsyncClient):
    """POST /api/resize/to-first-page returns success."""
    sid = await _upload(client)
    resp = await client.post(
        "/api/resize/to-first-page",
        data={"session_id": sid},
    )
    assert resp.status_code == 200
    assert "Resized" in resp.text


async def test_merge_page(client: AsyncClient):
    """GET /merge returns 200."""
    resp = await client.get("/merge")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


async def test_merge_upload_and_execute(client: AsyncClient):
    """Upload multiple PDFs and merge them."""
    pdf1 = _make_pdf(2)
    pdf2 = _make_pdf(3)
    resp = await client.post(
        "/api/merge/upload",
        files=[
            ("pdfs", ("file1.pdf", pdf1, "application/pdf")),
            ("pdfs", ("file2.pdf", pdf2, "application/pdf")),
        ],
    )
    assert resp.status_code == 200
