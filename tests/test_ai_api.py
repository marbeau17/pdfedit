"""Test AI API endpoints."""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_vision_analyze_no_image(client: AsyncClient):
    """POST /api/ai/vision-analyze without image returns 422."""
    resp = await client.post("/api/ai/vision-analyze", data={"api_key": "test", "page_num": "1"})
    assert resp.status_code == 422


async def test_generate_slide_no_key(client: AsyncClient):
    """POST /api/ai/generate-slide without api_key returns 400."""
    resp = await client.post("/api/ai/generate-slide", json={
        "xml": "<slide><title>Test</title></slide>",
        "api_key": "",
    })
    assert resp.status_code == 400


async def test_generate_slide_no_xml(client: AsyncClient):
    """POST /api/ai/generate-slide with empty xml returns 400."""
    resp = await client.post("/api/ai/generate-slide", json={
        "xml": "",
        "api_key": "test-key",
    })
    assert resp.status_code == 400


async def test_analyze_text_no_key(client: AsyncClient):
    """POST /api/ai/analyze without api_key returns 400."""
    resp = await client.post("/api/ai/analyze", json={
        "prompt": "test",
        "api_key": "",
    })
    assert resp.status_code == 400


async def test_home_has_local_processing(client: AsyncClient):
    """Home page mentions local processing."""
    resp = await client.get("/")
    text = resp.text.lower()
    assert "ブラウザ" in text or "local" in text


async def test_editor_has_pdf_engine(client: AsyncClient):
    """Editor page includes the PdfEngine script."""
    resp = await client.get("/editor")
    assert "pdf-engine" in resp.text or "PdfEngine" in resp.text
