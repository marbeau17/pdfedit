"""Tests for PDFService."""
import fitz
from app.services.pdf_service import PDFService


def test_get_page_count(sample_pdf: bytes):
    """PDFService.get_page_count returns 3 for a 3-page PDF."""
    assert PDFService.get_page_count(sample_pdf) == 3


def test_get_page_thumbnail(sample_pdf: bytes):
    """PDFService.get_page_thumbnail returns PNG bytes."""
    img = PDFService.get_page_thumbnail(sample_pdf, page_num=1)
    assert isinstance(img, bytes)
    # PNG magic bytes: \x89PNG\r\n\x1a\n
    assert img[:4] == b"\x89PNG"


def test_remove_single_page(sample_pdf: bytes):
    """Removing page 2 leaves 2 pages."""
    result = PDFService.remove_pages(sample_pdf, {2})
    assert PDFService.get_page_count(result) == 2


def test_remove_multiple_pages(sample_pdf: bytes):
    """Removing pages 1 and 3 leaves 1 page."""
    result = PDFService.remove_pages(sample_pdf, {1, 3})
    assert PDFService.get_page_count(result) == 1


def test_remove_invalid_page(sample_pdf: bytes):
    """Removing an out-of-range page leaves the PDF unchanged."""
    result = PDFService.remove_pages(sample_pdf, {99})
    assert PDFService.get_page_count(result) == 3


def test_reorder_pages(sample_pdf: bytes):
    """Reversing page order [3,2,1] keeps 3 pages."""
    result = PDFService.reorder_pages(sample_pdf, [3, 2, 1])
    assert PDFService.get_page_count(result) == 3


def test_reorder_partial(sample_pdf: bytes):
    """Selecting a subset [1,3] produces a 2-page PDF."""
    result = PDFService.reorder_pages(sample_pdf, [1, 3])
    assert PDFService.get_page_count(result) == 2


def test_merge_pdfs(sample_pdf: bytes):
    """Merging two 3-page PDFs produces a 6-page PDF."""
    result = PDFService.merge_pdfs([sample_pdf, sample_pdf])
    assert PDFService.get_page_count(result) == 6


def test_optimize(sample_pdf: bytes):
    """Optimized PDF size is <= original size."""
    optimized_bytes, original_size, optimized_size = PDFService.optimize(sample_pdf)
    assert optimized_size <= original_size
    assert isinstance(optimized_bytes, bytes)
    assert len(optimized_bytes) == optimized_size


def test_get_page_info(sample_pdf: bytes):
    """get_page_info returns a list of 3 dicts with page_num, width, height."""
    info = PDFService.get_page_info(sample_pdf)
    assert isinstance(info, list)
    assert len(info) == 3
    for i, page_info in enumerate(info):
        assert page_info["page_num"] == i + 1
        assert "width" in page_info
        assert "height" in page_info
        assert page_info["width"] > 0
        assert page_info["height"] > 0
