"""Tests for BrandingService."""
import fitz
import pytest
from app.services.branding_service import BrandingService


@pytest.fixture
def sample_pdf() -> bytes:
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page(width=595, height=842)
        page.insert_text((50, 50), f"Page {i + 1}", fontsize=24)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def sample_logo() -> bytes:
    """Create a small PNG logo for testing."""
    from PIL import Image
    import io
    img = Image.new("RGBA", (100, 50), (28, 48, 88, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_apply_branding_default(sample_pdf):
    """Branding with defaults produces valid PDF."""
    result = BrandingService.apply_branding(sample_pdf)
    doc = fitz.open(stream=result, filetype="pdf")
    assert len(doc) == 3
    doc.close()


def test_apply_branding_with_logo(sample_pdf, sample_logo):
    """Branding with logo produces valid PDF."""
    result = BrandingService.apply_branding(sample_pdf, logo_bytes=sample_logo)
    doc = fitz.open(stream=result, filetype="pdf")
    assert len(doc) == 3
    doc.close()


def test_apply_branding_target_pages(sample_pdf):
    """Branding with target_pages only affects specified pages."""
    result = BrandingService.apply_branding(
        sample_pdf, target_pages={1, 3}
    )
    assert len(result) > 0


def test_apply_branding_no_logo_no_pagenum(sample_pdf):
    """Branding with everything disabled still returns valid PDF."""
    result = BrandingService.apply_branding(
        sample_pdf, enable_logo=False, enable_page_num=False
    )
    doc = fitz.open(stream=result, filetype="pdf")
    assert len(doc) == 3
    doc.close()


def test_parse_page_ranges_basic():
    assert BrandingService.parse_page_ranges("1,3-5") == {1, 3, 4, 5}


def test_parse_page_ranges_empty():
    assert BrandingService.parse_page_ranges("") is None
    assert BrandingService.parse_page_ranges(None) is None


def test_parse_page_ranges_single():
    assert BrandingService.parse_page_ranges("7") == {7}
