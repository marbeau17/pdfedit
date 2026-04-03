"""
E2E Test - Extract Pages & Export Images
Tests PdfEngine.extractPages() and PdfEngine.exportPageAsImage() via Playwright.
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


async def create_test_pdf_bytes(page):
    """Create a 5-page test PDF in-browser using pdf-lib and return base64 string."""
    b64 = await page.evaluate("""
        (async () => {
            const doc = await PDFLib.PDFDocument.create();
            for (let i = 1; i <= 5; i++) {
                const p = doc.addPage([612, 792]);
                p.drawText('Page ' + i, { x: 50, y: 700, size: 30 });
            }
            const bytes = await doc.save();
            // Convert to base64 for transport
            let binary = '';
            for (let i = 0; i < bytes.length; i++) {
                binary += String.fromCharCode(bytes[i]);
            }
            return btoa(binary);
        })()
    """)
    return b64


async def load_test_pdf(page, b64):
    """Load a base64 PDF into PdfEngine via loadFromBytes."""
    await page.evaluate("""
        async (b64) => {
            const binary = atob(b64);
            const bytes = new Uint8Array(binary.length);
            for (let i = 0; i < binary.length; i++) {
                bytes[i] = binary.charCodeAt(i);
            }
            await PdfEngine.loadFromBytes(bytes, 'test.pdf');
        }
    """, b64)


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

        # Navigate to editor page so PdfEngine and libraries are available
        try:
            await page.goto(f"{BASE_URL}/editor", wait_until="networkidle", timeout=15000)
            await page.wait_for_function("typeof PdfEngine !== 'undefined' && typeof PDFLib !== 'undefined'", timeout=10000)
        except Exception as e:
            print(f"  [NG] Setup: Could not load editor page: {e}")
            await browser.close()
            return 1

        # Create and load the 5-page test PDF
        try:
            b64 = await create_test_pdf_bytes(page)
            await load_test_pdf(page, b64)
            count = await page.evaluate("PdfEngine.getPageCount()")
            assert count == 5, f"Expected 5 pages, got {count}"
        except Exception as e:
            print(f"  [NG] Setup: Could not create test PDF: {e}")
            await browser.close()
            return 1

        # === T01: Extract single page ===
        try:
            result = await page.evaluate("""
                (async () => {
                    const extracted = await PdfEngine.extractPages([3]);
                    const doc = await PDFLib.PDFDocument.load(extracted);
                    const extractedCount = doc.getPageCount();
                    const originalCount = PdfEngine.getPageCount();
                    return { extractedCount, originalCount };
                })()
            """)
            assert result["extractedCount"] == 1, f"Extracted should have 1 page, got {result['extractedCount']}"
            assert result["originalCount"] == 5, f"Original should still have 5 pages, got {result['originalCount']}"
            log("T01: Extract single page (page 3)", "PASS", f"extracted={result['extractedCount']}, original={result['originalCount']}")
        except Exception as e:
            log("T01: Extract single page (page 3)", "FAIL", str(e))

        # === T02: Extract multiple pages ===
        try:
            result = await page.evaluate("""
                (async () => {
                    const extracted = await PdfEngine.extractPages([1, 3, 5]);
                    const doc = await PDFLib.PDFDocument.load(extracted);
                    return doc.getPageCount();
                })()
            """)
            assert result == 3, f"Expected 3 pages, got {result}"
            log("T02: Extract multiple pages [1,3,5]", "PASS", f"pages={result}")
        except Exception as e:
            log("T02: Extract multiple pages [1,3,5]", "FAIL", str(e))

        # === T03: Extract all pages ===
        try:
            result = await page.evaluate("""
                (async () => {
                    const extracted = await PdfEngine.extractPages([1, 2, 3, 4, 5]);
                    const doc = await PDFLib.PDFDocument.load(extracted);
                    const extractedCount = doc.getPageCount();
                    const originalBytes = PdfEngine.getCurrentBytes();
                    const originalSize = originalBytes.length;
                    const extractedSize = extracted.length;
                    // Sizes should be roughly similar (within 50% tolerance)
                    const ratio = extractedSize / originalSize;
                    return { extractedCount, originalSize, extractedSize, ratio };
                })()
            """)
            assert result["extractedCount"] == 5, f"Expected 5 pages, got {result['extractedCount']}"
            assert 0.5 < result["ratio"] < 2.0, f"Size ratio {result['ratio']:.2f} out of expected range"
            log("T03: Extract all 5 pages", "PASS", f"pages={result['extractedCount']}, sizeRatio={result['ratio']:.2f}")
        except Exception as e:
            log("T03: Extract all 5 pages", "FAIL", str(e))

        # === T04: Extract after edit (delete page 1, then extract remaining) ===
        try:
            result = await page.evaluate("""
                (async () => {
                    // Delete page 1
                    await PdfEngine.removePages([1]);
                    const afterDelete = PdfEngine.getPageCount();

                    // Extract all remaining pages
                    const pageNums = [];
                    for (let i = 1; i <= afterDelete; i++) pageNums.push(i);
                    const extracted = await PdfEngine.extractPages(pageNums);
                    const doc = await PDFLib.PDFDocument.load(extracted);
                    const extractedCount = doc.getPageCount();
                    return { afterDelete, extractedCount };
                })()
            """)
            assert result["afterDelete"] == 4, f"After delete should have 4 pages, got {result['afterDelete']}"
            assert result["extractedCount"] == 4, f"Extracted should have 4 pages, got {result['extractedCount']}"
            log("T04: Extract after delete page 1", "PASS", f"remaining={result['afterDelete']}, extracted={result['extractedCount']}")
        except Exception as e:
            log("T04: Extract after delete page 1", "FAIL", str(e))

        # Reload fresh 5-page PDF for image export tests
        try:
            await load_test_pdf(page, b64)
        except Exception as e:
            print(f"  [NG] Setup: Could not reload test PDF for image tests: {e}")

        # === T05: Export page as PNG ===
        try:
            header_bytes = await page.evaluate("""
                (async () => {
                    const blob = await PdfEngine.exportPageAsImage(1, 'png', 1);
                    const buffer = await blob.arrayBuffer();
                    return Array.from(new Uint8Array(buffer).slice(0, 8));
                })()
            """)
            # PNG magic bytes: 0x89 0x50 0x4E 0x47 (137, 80, 78, 71)
            png_magic = [0x89, 0x50, 0x4E, 0x47]
            assert header_bytes[:4] == png_magic, f"Expected PNG magic {png_magic}, got {header_bytes[:4]}"
            log("T05: Export page as PNG", "PASS", f"header={header_bytes[:4]}")
        except Exception as e:
            log("T05: Export page as PNG", "FAIL", str(e))

        # === T06: Export page as JPEG ===
        try:
            header_bytes = await page.evaluate("""
                (async () => {
                    const blob = await PdfEngine.exportPageAsImage(1, 'jpeg', 1);
                    const buffer = await blob.arrayBuffer();
                    return Array.from(new Uint8Array(buffer).slice(0, 8));
                })()
            """)
            # JPEG magic bytes: 0xFF 0xD8 0xFF
            jpeg_magic = [0xFF, 0xD8, 0xFF]
            assert header_bytes[:3] == jpeg_magic, f"Expected JPEG magic {jpeg_magic}, got {header_bytes[:3]}"
            log("T06: Export page as JPEG", "PASS", f"header={header_bytes[:3]}")
        except Exception as e:
            log("T06: Export page as JPEG", "FAIL", str(e))

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
    print("E2E Test - Extract Pages & Export Images (6 scenarios)")
    print("=" * 60)
    failed = asyncio.run(run_tests())
    sys.exit(1 if failed > 0 else 0)
