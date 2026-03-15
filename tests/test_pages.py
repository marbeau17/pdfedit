"""Test page routes serve HTML correctly."""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_home_page(client: AsyncClient):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "PDF Workshop Pro" in resp.text


async def test_editor_page(client: AsyncClient):
    resp = await client.get("/editor")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


async def test_merge_page(client: AsyncClient):
    resp = await client.get("/merge")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


async def test_ai_workshop_page(client: AsyncClient):
    resp = await client.get("/ai-workshop")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


async def test_area_replace_page(client: AsyncClient):
    resp = await client.get("/area-replace")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


async def test_404_page(client: AsyncClient):
    resp = await client.get("/nonexistent")
    assert resp.status_code == 404
    assert "text/html" in resp.headers["content-type"]
