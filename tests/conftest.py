"""Shared test fixtures."""
import pytest
import fitz  # PyMuPDF
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.session_service import SessionService


@pytest.fixture
def sample_pdf() -> bytes:
    """Create a simple 3-page test PDF."""
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page(width=595, height=842)  # A4
        page.insert_text((50, 50), f"Test Page {i + 1}", fontsize=24)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture
def sample_pdf_5pages() -> bytes:
    """Create a 5-page test PDF."""
    doc = fitz.open()
    for i in range(5):
        page = doc.new_page(width=595, height=842)
        page.insert_text((50, 50), f"Page {i + 1}", fontsize=20)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture(autouse=True)
def clear_sessions():
    """Clear all sessions before each test."""
    SessionService._store.clear()
    yield
    SessionService._store.clear()


@pytest.fixture
async def client():
    """Async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
