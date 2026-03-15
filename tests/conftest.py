"""Test fixtures for Local-First architecture."""
import os
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture(autouse=True)
def _chdir_to_project():
    original = os.getcwd()
    os.chdir(os.path.join(os.path.dirname(__file__), ".."))
    yield
    os.chdir(original)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
