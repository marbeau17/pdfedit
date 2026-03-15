"""Test static files are served."""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_css_served(client: AsyncClient):
    resp = await client.get("/static/css/style.css")
    assert resp.status_code == 200


async def test_js_pdf_engine_served(client: AsyncClient):
    resp = await client.get("/static/js/pdf-engine.js")
    assert resp.status_code == 200
    assert "PdfEngine" in resp.text


async def test_js_storage_served(client: AsyncClient):
    resp = await client.get("/static/js/storage.js")
    assert resp.status_code == 200


async def test_js_editor_served(client: AsyncClient):
    resp = await client.get("/static/js/editor.js")
    assert resp.status_code == 200
