"""
E2E Tests - PDF Merge then Export
Tests that after merging PDFs, the result can be exported correctly.
Uses Playwright with page.evaluate() to drive the client-side PdfEngine.
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


async def _create_pdf_bytes(page, num_pages):
    """Create a PDF with N blank pages using PDFLib in the browser.
    Returns a JS expression that yields Array<number> (byte array)."""
    return await page.evaluate(f"""
        (async () => {{
            const doc = await PDFLib.PDFDocument.create();
            for (let i = 0; i < {num_pages}; i++) doc.addPage();
            return Array.from(await doc.save());
        }})()
    """)


async def _load_pdf_into_engine(page, num_pages):
    """Create a PDF with N pages and load it into PdfEngine. Returns page count."""
    return await page.evaluate(f"""
        (async () => {{
            const doc = await PDFLib.PDFDocument.create();
            for (let i = 0; i < {num_pages}; i++) doc.addPage();
            const bytes = await doc.save();
            return await PdfEngine.loadFromBytes(bytes, 'test.pdf');
        }})()
    """)


async def _get_page_count(page):
    return await page.evaluate("PdfEngine.getPageCount()")


async def _is_loaded(page):
    return await page.evaluate("PdfEngine.isLoaded()")


async def _get_current_bytes(page):
    """Get current PDF bytes and return them as a list of ints."""
    return await page.evaluate("Array.from(PdfEngine.getCurrentBytes())")


async def _validate_exported_pdf(page, expected_pages):
    """Export current PDF bytes, reload them in a fresh PDFDocument, and check page count."""
    result = await page.evaluate(f"""
        (async () => {{
            const bytes = PdfEngine.getCurrentBytes();
            if (!bytes || bytes.length === 0) return {{ valid: false, error: 'No bytes' }};
            try {{
                const doc = await PDFLib.PDFDocument.load(bytes);
                return {{ valid: true, pageCount: doc.getPageCount(), size: bytes.length }};
            }} catch (e) {{
                return {{ valid: false, error: e.message }};
            }}
        }})()
    """)
    return result


async def run_tests():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1400, "height": 900},
            locale="ja-JP",
        )
        console_errors = []

        page = await context.new_page()
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: console_errors.append(str(err)))

        # Navigate to editor so PdfEngine and PDFLib are available
        try:
            await page.goto(f"{BASE_URL}/editor", wait_until="networkidle", timeout=15000)
            await page.wait_for_timeout(1000)
            # Verify PdfEngine is available
            engine_ready = await page.evaluate("typeof PdfEngine !== 'undefined' && typeof PDFLib !== 'undefined'")
            assert engine_ready, "PdfEngine or PDFLib not loaded"
        except Exception as e:
            print(f"  [NG] SETUP: Could not load editor page: {e}")
            await browser.close()
            return 1

        # ====================================================================
        # T01: Merge two PDFs then export
        # Load 2-page PDF, merge with 3-page PDF, verify 5 pages, export valid
        # ====================================================================
        try:
            # Load a 2-page PDF into PdfEngine
            count = await _load_pdf_into_engine(page, 2)
            assert count == 2, f"Expected 2 pages after load, got {count}"

            # Create a 3-page PDF and merge it
            new_count = await page.evaluate("""
                (async () => {
                    const doc = await PDFLib.PDFDocument.create();
                    for (let i = 0; i < 3; i++) doc.addPage();
                    const bytes = await doc.save();
                    return await PdfEngine.mergePdf(bytes);
                })()
            """)
            assert new_count == 5, f"Expected 5 pages after merge, got {new_count}"

            # Verify page count via getPageCount
            pc = await _get_page_count(page)
            assert pc == 5, f"getPageCount returned {pc}, expected 5"

            # Export and validate
            result = await _validate_exported_pdf(page, 5)
            assert result["valid"], f"Export invalid: {result.get('error')}"
            assert result["pageCount"] == 5, f"Exported PDF has {result['pageCount']} pages, expected 5"
            assert result["size"] > 0, "Exported PDF has zero size"

            log("T01: Merge 2+3 pages then export", "PASS", f"{result['pageCount']} pages, {result['size']} bytes")
        except Exception as e:
            log("T01: Merge 2+3 pages then export", "FAIL", str(e))

        # ====================================================================
        # T02: Merge two PDFs, delete a page, then export
        # ====================================================================
        try:
            # Load a 2-page PDF
            count = await _load_pdf_into_engine(page, 2)
            assert count == 2

            # Merge with a 3-page PDF
            new_count = await page.evaluate("""
                (async () => {
                    const doc = await PDFLib.PDFDocument.create();
                    for (let i = 0; i < 3; i++) doc.addPage();
                    const bytes = await doc.save();
                    return await PdfEngine.mergePdf(bytes);
                })()
            """)
            assert new_count == 5, f"Expected 5 pages after merge, got {new_count}"

            # Delete page 3 (1-based)
            after_delete = await page.evaluate("PdfEngine.removePages([3])")
            assert after_delete == 4, f"Expected 4 pages after delete, got {after_delete}"

            # Export and validate
            result = await _validate_exported_pdf(page, 4)
            assert result["valid"], f"Export invalid: {result.get('error')}"
            assert result["pageCount"] == 4, f"Exported PDF has {result['pageCount']} pages, expected 4"

            log("T02: Merge then delete then export", "PASS", f"{result['pageCount']} pages, {result['size']} bytes")
        except Exception as e:
            log("T02: Merge then delete then export", "FAIL", str(e))

        # ====================================================================
        # T03: Merge a PDF with itself (identical PDFs)
        # ====================================================================
        try:
            # Load a 3-page PDF
            count = await _load_pdf_into_engine(page, 3)
            assert count == 3

            # Get current bytes and merge with self
            doubled_count = await page.evaluate("""
                (async () => {
                    const selfBytes = PdfEngine.getCurrentBytes();
                    return await PdfEngine.mergePdf(selfBytes);
                })()
            """)
            assert doubled_count == 6, f"Expected 6 pages after self-merge, got {doubled_count}"

            # Verify
            pc = await _get_page_count(page)
            assert pc == 6, f"getPageCount returned {pc}, expected 6"

            # Export and validate
            result = await _validate_exported_pdf(page, 6)
            assert result["valid"], f"Export invalid: {result.get('error')}"
            assert result["pageCount"] == 6, f"Exported PDF has {result['pageCount']} pages, expected 6"

            log("T03: Merge identical PDFs then export", "PASS", f"{result['pageCount']} pages, {result['size']} bytes")
        except Exception as e:
            log("T03: Merge identical PDFs then export", "FAIL", str(e))

        # ====================================================================
        # T04: Create two 1-page PDFs, merge, verify 2 pages, export
        # ====================================================================
        try:
            # Load a 1-page PDF
            count = await _load_pdf_into_engine(page, 1)
            assert count == 1

            # Create another 1-page PDF and merge
            new_count = await page.evaluate("""
                (async () => {
                    const doc = await PDFLib.PDFDocument.create();
                    doc.addPage();
                    const bytes = await doc.save();
                    return await PdfEngine.mergePdf(bytes);
                })()
            """)
            assert new_count == 2, f"Expected 2 pages after merge, got {new_count}"

            # Verify
            pc = await _get_page_count(page)
            assert pc == 2

            # Export and validate
            result = await _validate_exported_pdf(page, 2)
            assert result["valid"], f"Export invalid: {result.get('error')}"
            assert result["pageCount"] == 2, f"Exported PDF has {result['pageCount']} pages, expected 2"
            assert result["size"] > 0

            log("T04: Merge single-page PDFs then export", "PASS", f"{result['pageCount']} pages, {result['size']} bytes")
        except Exception as e:
            log("T04: Merge single-page PDFs then export", "FAIL", str(e))

        # ====================================================================
        # Summary
        # ====================================================================
        # Check for critical console errors across all tests
        critical = [e for e in console_errors
                    if "is not a function" in e or "Cannot read" in e or "Unexpected token" in e]
        if critical:
            log("Console errors check", "FAIL", f"{len(critical)} critical: {critical[0][:120]}")
        else:
            log("Console errors check", "PASS", f"No critical errors ({len(console_errors)} total messages)")

        await browser.close()

    # Print summary
    print("\n" + "=" * 60)
    passed = sum(1 for _, s, _ in RESULTS if s == "PASS")
    failed = sum(1 for _, s, _ in RESULTS if s == "FAIL")
    print(f"Result: {passed} PASS / {failed} FAIL / {len(RESULTS)} TOTAL")
    if failed > 0:
        print("\nFailed:")
        for name, status, detail in RESULTS:
            if status == "FAIL":
                print(f"  [NG] {name}: {detail}")
    print("=" * 60)
    return failed


if __name__ == "__main__":
    print("=" * 60)
    print("E2E Test - PDF Merge then Export (4 scenarios + console check)")
    print("=" * 60)
    failed = asyncio.run(run_tests())
    sys.exit(1 if failed > 0 else 0)
