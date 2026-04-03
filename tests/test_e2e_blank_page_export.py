"""
E2E Tests - Blank Page Addition and PDF Export
Tests that blank pages can be added at various positions and the resulting
PDF can be exported as valid bytes, then re-loaded and validated.

Run:
    python -m pytest tests/test_e2e_blank_page_export.py -v
    # or standalone:
    python tests/test_e2e_blank_page_export.py

Requires: playwright install chromium
Server must be running at BASE_URL.
"""
import asyncio
import sys

from playwright.async_api import async_playwright

BASE_URL = "http://127.0.0.1:8765"
RESULTS = []


def log(name, status, detail=""):
    icon = "OK" if status == "PASS" else "NG"
    RESULTS.append((name, status, detail))
    print(f"  [{icon}] {name}: {status} {detail}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_browser_and_page(playwright):
    """Launch headless Chromium and return (browser, page)."""
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context(
        viewport={"width": 1400, "height": 900},
        locale="ja-JP",
    )
    page = await context.new_page()
    return browser, page


async def _upload_sample_pdf(page):
    """Upload a tiny 2-page PDF via the home page and wait for the editor.

    Returns the fileId extracted from the URL.
    """
    await page.goto(BASE_URL, wait_until="networkidle")

    # Create a 2-page PDF in-browser using pdf-lib, save to IndexedDB,
    # then navigate to the editor.
    file_id = await page.evaluate("""
        (async () => {
            const pdfDoc = await PDFLib.PDFDocument.create();
            pdfDoc.addPage([595, 842]);
            pdfDoc.addPage([595, 842]);
            const bytes = await pdfDoc.save();
            const fileId = await PdfStorage.saveFile('test.pdf', bytes);
            return fileId;
        })()
    """)

    await page.goto(f"{BASE_URL}/editor?fileId={file_id}", wait_until="networkidle")
    # Wait for PdfEngine to finish loading
    await page.wait_for_function("PdfEngine.isLoaded()", timeout=10000)
    return file_id


async def _wait_loaded(page, timeout=10000):
    """Wait until PdfEngine reports loaded."""
    await page.wait_for_function("PdfEngine.isLoaded()", timeout=timeout)


async def _get_page_count(page):
    return await page.evaluate("PdfEngine.getPageCount()")


async def _export_bytes(page):
    """Export current PDF bytes as a base64 string and return its length."""
    info = await page.evaluate("""
        (() => {
            const bytes = PdfEngine.getCurrentBytes();
            if (!bytes || bytes.length === 0) return null;
            return { length: bytes.length };
        })()
    """)
    return info


async def _export_and_reload(page):
    """Export the current PDF bytes, reload them into PdfEngine, and return
    the new page count.  This validates the bytes form a parseable PDF."""
    count = await page.evaluate("""
        (async () => {
            const bytes = PdfEngine.getCurrentBytes();
            if (!bytes || bytes.length === 0) throw new Error('no bytes');
            // Re-load into the engine to prove validity
            await PdfEngine.loadFromBytes(bytes, 'reloaded.pdf');
            return PdfEngine.getPageCount();
        })()
    """)
    return count


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_add_blank_page_at_end_then_export(page):
    """Load 2-page PDF, add blank at end, verify 3 pages, export, re-load."""
    await _upload_sample_pdf(page)
    initial = await _get_page_count(page)
    assert initial == 2, f"Expected 2 pages initially, got {initial}"

    new_count = await page.evaluate("PdfEngine.addBlankPage(2)")  # after last page
    assert new_count == 3, f"Expected 3 after addBlankPage, got {new_count}"

    count_check = await _get_page_count(page)
    assert count_check == 3

    exported = await _export_bytes(page)
    assert exported is not None and exported["length"] > 0, "Export produced empty bytes"

    reloaded_count = await _export_and_reload(page)
    assert reloaded_count == 3, f"Reloaded PDF has {reloaded_count} pages, expected 3"


async def test_add_blank_page_at_beginning_then_export(page):
    """Add blank page at position 0 (beginning), export, validate."""
    await _upload_sample_pdf(page)

    new_count = await page.evaluate("PdfEngine.addBlankPage(0)")  # before first page
    assert new_count == 3, f"Expected 3, got {new_count}"

    reloaded_count = await _export_and_reload(page)
    assert reloaded_count == 3


async def test_add_blank_page_in_middle_then_export(page):
    """Add blank page after page 1, export, validate."""
    await _upload_sample_pdf(page)

    new_count = await page.evaluate("PdfEngine.addBlankPage(1)")  # after page 1
    assert new_count == 3, f"Expected 3, got {new_count}"

    reloaded_count = await _export_and_reload(page)
    assert reloaded_count == 3


async def test_add_multiple_blank_pages_then_export(page):
    """Add 3 blank pages to a 2-page PDF, verify 5 pages, export."""
    await _upload_sample_pdf(page)

    await page.evaluate("PdfEngine.addBlankPage(2)")   # end -> 3 pages
    await page.evaluate("PdfEngine.addBlankPage(0)")   # beginning -> 4 pages
    await page.evaluate("PdfEngine.addBlankPage(2)")   # middle -> 5 pages

    count = await _get_page_count(page)
    assert count == 5, f"Expected 5 pages, got {count}"

    reloaded_count = await _export_and_reload(page)
    assert reloaded_count == 5


async def test_add_blank_page_custom_size_then_export(page):
    """Add blank page with custom 400x600 dimensions, export, re-load,
    verify the page has the correct size."""
    await _upload_sample_pdf(page)

    new_count = await page.evaluate("PdfEngine.addBlankPage(2, 400, 600)")
    assert new_count == 3, f"Expected 3, got {new_count}"

    # The custom-size page is now page 3 (appended at end)
    size = await page.evaluate("PdfEngine.getPageSize(3)")
    assert abs(size["width"] - 400) < 2, f"Width {size['width']} != 400"
    assert abs(size["height"] - 600) < 2, f"Height {size['height']} != 600"

    # Export and re-load to confirm dimensions survive round-trip
    reloaded_count = await _export_and_reload(page)
    assert reloaded_count == 3

    size_after = await page.evaluate("PdfEngine.getPageSize(3)")
    assert abs(size_after["width"] - 400) < 2, f"After reload width {size_after['width']} != 400"
    assert abs(size_after["height"] - 600) < 2, f"After reload height {size_after['height']} != 600"


async def test_add_blank_to_empty_and_export(page):
    """Create a brand-new empty PDF with just one blank page, export, validate."""
    await page.goto(BASE_URL, wait_until="networkidle")

    # Create an empty PDF in-browser, store it, navigate to editor
    file_id = await page.evaluate("""
        (async () => {
            const pdfDoc = await PDFLib.PDFDocument.create();
            const bytes = await pdfDoc.save();
            const fileId = await PdfStorage.saveFile('empty.pdf', bytes);
            return fileId;
        })()
    """)

    await page.goto(f"{BASE_URL}/editor?fileId={file_id}", wait_until="networkidle")
    await _wait_loaded(page)

    initial = await _get_page_count(page)
    # PDFLib.PDFDocument.create() may serialize with 0 or 1 page
    assert initial <= 1, f"Expected 0 or 1 pages in empty PDF, got {initial}"

    new_count = await page.evaluate("PdfEngine.addBlankPage(0, 595, 842)")
    expected = initial + 1
    assert new_count == expected, f"Expected {expected} after addBlankPage, got {new_count}"

    exported = await _export_bytes(page)
    assert exported is not None and exported["length"] > 0

    reloaded_count = await _export_and_reload(page)
    assert reloaded_count == expected


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

ALL_TESTS = [
    ("T01: Add blank at end + export", test_add_blank_page_at_end_then_export),
    ("T02: Add blank at beginning + export", test_add_blank_page_at_beginning_then_export),
    ("T03: Add blank in middle + export", test_add_blank_page_in_middle_then_export),
    ("T04: Add multiple blanks + export", test_add_multiple_blank_pages_then_export),
    ("T05: Add blank custom size + export", test_add_blank_page_custom_size_then_export),
    ("T06: Add blank to empty PDF + export", test_add_blank_to_empty_and_export),
]


async def run_tests():
    async with async_playwright() as p:
        browser, page = await _create_browser_and_page(p)

        for name, test_fn in ALL_TESTS:
            try:
                await test_fn(page)
                log(name, "PASS")
            except Exception as e:
                log(name, "FAIL", str(e))

        await browser.close()

    # Summary
    print("\n" + "=" * 60)
    passed = sum(1 for _, s, _ in RESULTS if s == "PASS")
    failed = sum(1 for _, s, _ in RESULTS if s == "FAIL")
    print(f"Result: {passed} PASS / {failed} FAIL / {len(RESULTS)} TOTAL")
    if failed > 0:
        print("\nFailed:")
        for test_name, status, detail in RESULTS:
            if status == "FAIL":
                print(f"  [NG] {test_name}: {detail}")
    print("=" * 60)
    return failed


if __name__ == "__main__":
    print("=" * 60)
    print("E2E Tests - Blank Page Addition & Export (6 scenarios)")
    print("=" * 60)
    failed = asyncio.run(run_tests())
    sys.exit(1 if failed > 0 else 0)
