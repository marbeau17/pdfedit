"""Test AI API endpoints."""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_analyze_no_key(client: AsyncClient):
    resp = await client.post("/api/ai/analyze", json={
        "pages": [{"page": 1, "text": "Hello"}],
        "api_key": "",
    })
    assert resp.status_code == 400


async def test_analyze_invalid_json(client: AsyncClient):
    resp = await client.post("/api/ai/analyze", content="not json",
                              headers={"content-type": "application/json"})
    assert resp.status_code == 422


async def test_generate_no_key(client: AsyncClient):
    resp = await client.post("/api/ai/generate", json={
        "prompt": "test",
        "api_key": "",
    })
    assert resp.status_code == 400


async def test_home_has_local_processing(client: AsyncClient):
    """Home page mentions local processing / no server upload."""
    resp = await client.get("/")
    text = resp.text.lower()
    assert "pdf-lib" in text or "local" in text or "ブラウザ" in text


async def test_editor_has_pdf_engine(client: AsyncClient):
    """Editor page includes the PdfEngine script."""
    resp = await client.get("/editor")
    assert "pdf-engine" in resp.text or "PdfEngine" in resp.text
