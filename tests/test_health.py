"""Test health endpoint."""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_health_check(client: AsyncClient):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["architecture"] == "local-first"
    assert "python_version" in data


async def test_security_headers(client: AsyncClient):
    resp = await client.get("/")
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert "max-age=31536000" in resp.headers.get("strict-transport-security", "")
    assert resp.headers.get("x-xss-protection") == "1; mode=block"
    assert "camera=()" in resp.headers.get("permissions-policy", "")
    csp = resp.headers.get("content-security-policy", "")
    assert "default-src 'self'" in csp
    assert "script-src" in csp
