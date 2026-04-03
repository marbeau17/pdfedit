"""
E2E Test - Reorder Pages then Export PDF
Tests that after reordering pages, the PDF can be exported correctly.
Requires a running server at BASE_URL and Playwright installed.
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
# Helper: create a 3-page PDF with text "Page1", "Page2", "Page3" in-browser
# and load it into PdfEngine. Returns the page count.
# ---------------------------------------------------------------------------
CREATE_3PAGE_PDF_JS = """
async () => {
    const doc = await PDFLib.PDFDocument.create();
    for (let i = 0; i < 3; i++) {
        const page = doc.addPage();
        const font = await doc.embedFont(PDFLib.StandardFonts.Helvetica);
        page.drawText('Page' + (i + 1), { x: 50, y: 700, size: 30, font });
    }
    const bytes = await doc.save();
    const count = await PdfEngine.loadFromBytes(new Uint8Array(bytes), 'test.pdf');
    return count;
}
"""

# Helper: create a 1-page PDF with text "Solo"
CREATE_1PAGE_PDF_JS = """
async () => {
    const doc = await PDFLib.PDFDocument.create();
    const page = doc.addPage();
    const font = await doc.embedFont(PDFLib.StandardFonts.Helvetica);
    page.drawText('Solo', { x: 50, y: 700, size: 30, font });
    const bytes = await doc.save();
    const count = await PdfEngine.loadFromBytes(new Uint8Array(bytes), 'solo.pdf');
    return count;
}
"""


async def setup_editor_page(context):
    """Navigate to /editor and wait for PdfEngine to be available."""
    page = await context.new_page()
    await page.goto(f"{BASE_URL}/editor", wait_until="networkidle")
    # Wait for PdfEngine to be defined
    await page.wait_for_function("typeof PdfEngine !== 'undefined' && typeof PDFLib !== 'undefined'", timeout=10000)
    return page


async def test_reverse_page_order_then_export(context):
    """
    T01: Load 3-page PDF -> reorder to [3,2,1] -> export -> re-load
    -> verify page 1 text contains 'Page3'.
    """
    page = await setup_editor_page(context)
    try:
        # Create and load a 3-page PDF
        count = await page.evaluate(CREATE_3PAGE_PDF_JS)
        assert count == 3, f"Expected 3 pages, got {count}"

        # Verify initial text on page 1
        initial_text = await page.evaluate("() => PdfEngine.extractText(1)")
        assert "Page1" in initial_text, f"Initial page 1 should have 'Page1', got: {initial_text}"

        # Reorder: reverse [3, 2, 1]
        new_count = await page.evaluate("() => PdfEngine.reorderPages([3, 2, 1])")
        assert new_count == 3, f"Expected 3 pages after reorder, got {new_count}"

        # Export bytes and re-load to verify persistence
        result = await page.evaluate("""
        async () => {
            const bytes = PdfEngine.getCurrentBytes();
            // Re-load the exported bytes into a fresh PdfEngine state
            const count = await PdfEngine.loadFromBytes(new Uint8Array(bytes), 'reloaded.pdf');
            const text1 = await PdfEngine.extractText(1);
            const text2 = await PdfEngine.extractText(2);
            const text3 = await PdfEngine.extractText(3);
            return { count, text1, text2, text3 };
        }
        """)
        assert result["count"] == 3, f"Re-loaded PDF should have 3 pages, got {result['count']}"
        assert "Page3" in result["text1"], f"Page 1 should now be 'Page3', got: {result['text1']}"
        assert "Page2" in result["text2"], f"Page 2 should now be 'Page2', got: {result['text2']}"
        assert "Page1" in result["text3"], f"Page 3 should now be 'Page1', got: {result['text3']}"

        log("T01: Reverse page order then export", "PASS")
    except Exception as e:
        log("T01: Reverse page order then export", "FAIL", str(e))
    finally:
        await page.close()


async def test_swap_two_pages_then_export(context):
    """
    T02: Load 3-page PDF -> reorder to [2,1,3] (swap first two) -> export
    -> verify page count is 3 and PDF is valid (can be re-loaded).
    """
    page = await setup_editor_page(context)
    try:
        count = await page.evaluate(CREATE_3PAGE_PDF_JS)
        assert count == 3

        # Swap pages 1 and 2
        new_count = await page.evaluate("() => PdfEngine.reorderPages([2, 1, 3])")
        assert new_count == 3, f"Expected 3 pages after swap, got {new_count}"

        # Export and verify
        result = await page.evaluate("""
        async () => {
            const bytes = PdfEngine.getCurrentBytes();
            if (!bytes || bytes.length === 0) return { valid: false, reason: 'empty bytes' };

            // Verify bytes start with PDF header
            const header = String.fromCharCode(...bytes.slice(0, 5));
            if (header !== '%PDF-') return { valid: false, reason: 'invalid PDF header: ' + header };

            // Re-load to confirm it is a valid PDF
            const count = await PdfEngine.loadFromBytes(new Uint8Array(bytes), 'swapped.pdf');
            const text1 = await PdfEngine.extractText(1);
            const text2 = await PdfEngine.extractText(2);
            return { valid: true, count, text1, text2 };
        }
        """)
        assert result["valid"], f"PDF invalid: {result.get('reason', 'unknown')}"
        assert result["count"] == 3, f"Expected 3 pages, got {result['count']}"
        assert "Page2" in result["text1"], f"Page 1 should be 'Page2', got: {result['text1']}"
        assert "Page1" in result["text2"], f"Page 2 should be 'Page1', got: {result['text2']}"

        log("T02: Swap two pages then export", "PASS")
    except Exception as e:
        log("T02: Swap two pages then export", "FAIL", str(e))
    finally:
        await page.close()


async def test_reorder_single_page_pdf(context):
    """
    T03: Load 1-page PDF -> reorder [1] (no-op) -> export -> valid PDF.
    """
    page = await setup_editor_page(context)
    try:
        count = await page.evaluate(CREATE_1PAGE_PDF_JS)
        assert count == 1, f"Expected 1 page, got {count}"

        # Reorder with identity (no-op)
        new_count = await page.evaluate("() => PdfEngine.reorderPages([1])")
        assert new_count == 1, f"Expected 1 page after reorder, got {new_count}"

        # Export and verify
        result = await page.evaluate("""
        async () => {
            const bytes = PdfEngine.getCurrentBytes();
            if (!bytes || bytes.length === 0) return { valid: false, reason: 'empty bytes' };

            const header = String.fromCharCode(...bytes.slice(0, 5));
            if (header !== '%PDF-') return { valid: false, reason: 'invalid header' };

            const count = await PdfEngine.loadFromBytes(new Uint8Array(bytes), 'single.pdf');
            const text = await PdfEngine.extractText(1);
            return { valid: true, count, text };
        }
        """)
        assert result["valid"], f"PDF invalid: {result.get('reason', 'unknown')}"
        assert result["count"] == 1, f"Expected 1 page, got {result['count']}"
        assert "Solo" in result["text"], f"Page text should contain 'Solo', got: {result['text']}"

        log("T03: Reorder single page PDF (no-op)", "PASS")
    except Exception as e:
        log("T03: Reorder single page PDF (no-op)", "FAIL", str(e))
    finally:
        await page.close()


async def test_reorder_preserves_content(context):
    """
    T04: Load 3-page PDF with distinct text -> reorder [2,3,1] -> export
    -> re-load -> verify each page has the expected text.
    """
    page = await setup_editor_page(context)
    try:
        count = await page.evaluate(CREATE_3PAGE_PDF_JS)
        assert count == 3

        # Verify original text before reorder
        original = await page.evaluate("""
        async () => {
            return {
                t1: await PdfEngine.extractText(1),
                t2: await PdfEngine.extractText(2),
                t3: await PdfEngine.extractText(3)
            };
        }
        """)
        assert "Page1" in original["t1"]
        assert "Page2" in original["t2"]
        assert "Page3" in original["t3"]

        # Reorder: [2,3,1] -> page2 becomes first, page3 second, page1 third
        new_count = await page.evaluate("() => PdfEngine.reorderPages([2, 3, 1])")
        assert new_count == 3

        # Export bytes, re-load, and verify all page contents
        result = await page.evaluate("""
        async () => {
            const bytes = PdfEngine.getCurrentBytes();
            const count = await PdfEngine.loadFromBytes(new Uint8Array(bytes), 'preserved.pdf');
            const t1 = await PdfEngine.extractText(1);
            const t2 = await PdfEngine.extractText(2);
            const t3 = await PdfEngine.extractText(3);
            return { count, t1, t2, t3 };
        }
        """)
        assert result["count"] == 3, f"Expected 3 pages, got {result['count']}"
        # After [2,3,1]: new page 1 = old page 2, new page 2 = old page 3, new page 3 = old page 1
        assert "Page2" in result["t1"], f"New page 1 should have 'Page2', got: {result['t1']}"
        assert "Page3" in result["t2"], f"New page 2 should have 'Page3', got: {result['t2']}"
        assert "Page1" in result["t3"], f"New page 3 should have 'Page1', got: {result['t3']}"

        log("T04: Reorder preserves content", "PASS")
    except Exception as e:
        log("T04: Reorder preserves content", "FAIL", str(e))
    finally:
        await page.close()


async def run_tests():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1400, "height": 900},
            locale="ja-JP",
        )

        await test_reverse_page_order_then_export(context)
        await test_swap_two_pages_then_export(context)
        await test_reorder_single_page_pdf(context)
        await test_reorder_preserves_content(context)

        await browser.close()

    # Summary
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
    print("E2E Test - Reorder Pages then Export (4 scenarios)")
    print("=" * 60)
    failed = asyncio.run(run_tests())
    sys.exit(1 if failed > 0 else 0)
