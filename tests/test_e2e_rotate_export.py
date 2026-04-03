"""
E2E Test - Rotate Pages and Export PDF
Tests that after rotating pages, the PDF can be exported correctly.
Uses Playwright to drive a browser-based PDF editor.
"""
import asyncio
import json
import os
import sys
import tempfile

from playwright.async_api import async_playwright

BASE_URL = "http://127.0.0.1:8765"
RESULTS = []


def log(name, status, detail=""):
    icon = "OK" if status == "PASS" else "NG"
    RESULTS.append((name, status, detail))
    print(f"  [{icon}] {name}: {status} {detail}")


async def create_test_pdf(page, num_pages=1, width=612, height=792):
    """Create a test PDF with the given number of pages using pdf-lib in the browser.

    Default dimensions are US Letter (612x792 points).
    Returns the PDF bytes as a list of integers.
    """
    pdf_bytes = await page.evaluate(f"""
        (async () => {{
            const pdfDoc = await PDFLib.PDFDocument.create();
            for (let i = 0; i < {num_pages}; i++) {{
                const p = pdfDoc.addPage([{width}, {height}]);
                const font = await pdfDoc.embedFont(PDFLib.StandardFonts.Helvetica);
                p.drawText('Page ' + (i + 1), {{
                    x: 50,
                    y: {height} - 50,
                    size: 24,
                    font: font,
                }});
            }}
            const bytes = await pdfDoc.save();
            return Array.from(bytes);
        }})()
    """)
    return pdf_bytes


async def load_pdf_in_editor(page, pdf_bytes):
    """Load the given PDF bytes into PdfEngine via loadFromBytes."""
    page_count = await page.evaluate("""
        async (bytesArr) => {
            const bytes = new Uint8Array(bytesArr);
            return await PdfEngine.loadFromBytes(bytes, 'test.pdf');
        }
    """, pdf_bytes)
    return page_count


async def export_and_reload(page, pdf_bytes_before=None):
    """Export the current PDF bytes, then reload them into PdfEngine.

    Returns (exported_bytes_list, new_page_count).
    """
    exported = await page.evaluate("""
        (() => {
            const bytes = PdfEngine.getCurrentBytes();
            return Array.from(bytes);
        })()
    """)
    # Reload the exported PDF to verify it is valid
    new_count = await page.evaluate("""
        async (bytesArr) => {
            const bytes = new Uint8Array(bytesArr);
            return await PdfEngine.loadFromBytes(bytes, 'exported.pdf');
        }
    """, exported)
    return exported, new_count


async def get_page_size(page, page_num):
    """Get page dimensions from PdfEngine."""
    size = await page.evaluate(f"""
        (async () => {{
            const s = await PdfEngine.getPageSize({page_num});
            return {{ width: s.width, height: s.height }};
        }})()
    """)
    return size["width"], size["height"]


async def wait_for_engine(page, timeout=10000):
    """Wait until PdfEngine and PDF libraries are available."""
    await page.wait_for_function(
        "typeof PdfEngine !== 'undefined' && typeof PDFLib !== 'undefined' && typeof pdfjsLib !== 'undefined'",
        timeout=timeout,
    )


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

        # Navigate to editor page so PDF libraries are loaded
        try:
            await page.goto(f"{BASE_URL}/editor?fileId=0", wait_until="networkidle", timeout=15000)
            await wait_for_engine(page)
        except Exception as e:
            print(f"FATAL: Could not load editor page: {e}")
            await browser.close()
            return 1

        # ============================================================
        # T01: test_rotate_single_page_then_export
        # Load PDF -> rotate page 1 by 90 -> export -> valid PDF with
        # same page count -> re-load and verify dimensions swapped.
        # ============================================================
        try:
            pdf_bytes = await create_test_pdf(page, num_pages=1, width=612, height=792)
            await load_pdf_in_editor(page, pdf_bytes)

            orig_w, orig_h = await get_page_size(page, 1)

            # Rotate page 1 by 90 degrees
            await page.evaluate("PdfEngine.rotatePage(1, 90)")
            await page.wait_for_timeout(300)

            # Export and reload
            exported, new_count = await export_and_reload(page)

            assert new_count == 1, f"Expected 1 page, got {new_count}"
            assert len(exported) > 0, "Exported PDF is empty"

            # Verify dimensions are swapped (width/height flipped)
            new_w, new_h = await get_page_size(page, 1)

            # After 90-degree rotation, width and height should be swapped
            assert abs(new_w - orig_h) < 2, f"Expected width ~{orig_h}, got {new_w}"
            assert abs(new_h - orig_w) < 2, f"Expected height ~{orig_w}, got {new_h}"

            log("T01: rotate_single_page_then_export", "PASS")
        except Exception as e:
            log("T01: rotate_single_page_then_export", "FAIL", str(e))

        # ============================================================
        # T02: test_rotate_all_pages_then_export
        # Load 3-page PDF -> rotate all pages -> export -> valid.
        # ============================================================
        try:
            pdf_bytes = await create_test_pdf(page, num_pages=3, width=612, height=792)
            count = await load_pdf_in_editor(page, pdf_bytes)
            assert count == 3, f"Expected 3 pages, got {count}"

            orig_w, orig_h = await get_page_size(page, 1)

            # Rotate all 3 pages
            for i in range(1, 4):
                await page.evaluate(f"PdfEngine.rotatePage({i}, 90)")
                await page.wait_for_timeout(200)

            # Export and reload
            exported, new_count = await export_and_reload(page)

            assert new_count == 3, f"Expected 3 pages after export, got {new_count}"
            assert len(exported) > 0, "Exported PDF is empty"

            # Verify all pages have swapped dimensions
            for i in range(1, 4):
                w, h = await get_page_size(page, i)
                assert abs(w - orig_h) < 2, f"Page {i}: expected width ~{orig_h}, got {w}"
                assert abs(h - orig_w) < 2, f"Page {i}: expected height ~{orig_w}, got {h}"

            log("T02: rotate_all_pages_then_export", "PASS")
        except Exception as e:
            log("T02: rotate_all_pages_then_export", "FAIL", str(e))

        # ============================================================
        # T03: test_rotate_180_then_export
        # Rotate 180 -> export -> dimensions should be same (not swapped).
        # ============================================================
        try:
            pdf_bytes = await create_test_pdf(page, num_pages=1, width=612, height=792)
            await load_pdf_in_editor(page, pdf_bytes)

            orig_w, orig_h = await get_page_size(page, 1)

            # Rotate page 1 by 180 degrees
            await page.evaluate("PdfEngine.rotatePage(1, 180)")
            await page.wait_for_timeout(300)

            # Export and reload
            exported, new_count = await export_and_reload(page)

            assert new_count == 1, f"Expected 1 page, got {new_count}"
            assert len(exported) > 0, "Exported PDF is empty"

            # After 180-degree rotation, dimensions should remain the same
            new_w, new_h = await get_page_size(page, 1)
            assert abs(new_w - orig_w) < 2, f"Expected width ~{orig_w}, got {new_w}"
            assert abs(new_h - orig_h) < 2, f"Expected height ~{orig_h}, got {new_h}"

            log("T03: rotate_180_then_export", "PASS")
        except Exception as e:
            log("T03: rotate_180_then_export", "FAIL", str(e))

        # ============================================================
        # T04: test_rotate_then_undo_then_export
        # Rotate page -> undo -> export -> should match original dimensions.
        # ============================================================
        try:
            pdf_bytes = await create_test_pdf(page, num_pages=1, width=612, height=792)
            await load_pdf_in_editor(page, pdf_bytes)

            orig_w, orig_h = await get_page_size(page, 1)

            # Rotate page 1 by 90 degrees
            await page.evaluate("PdfEngine.rotatePage(1, 90)")
            await page.wait_for_timeout(300)

            # Verify rotation took effect
            rot_w, rot_h = await get_page_size(page, 1)
            assert abs(rot_w - orig_h) < 2, f"Rotation did not swap: width {rot_w} vs expected ~{orig_h}"

            # Undo the rotation
            undo_result = await page.evaluate("PdfEngine.undo()")
            await page.wait_for_timeout(300)
            assert undo_result, "Undo returned false (no history)"

            # Export and reload
            exported, new_count = await export_and_reload(page)

            assert new_count == 1, f"Expected 1 page, got {new_count}"

            # After undo, dimensions should match original
            new_w, new_h = await get_page_size(page, 1)
            assert abs(new_w - orig_w) < 2, f"Expected width ~{orig_w} after undo, got {new_w}"
            assert abs(new_h - orig_h) < 2, f"Expected height ~{orig_h} after undo, got {new_h}"

            log("T04: rotate_then_undo_then_export", "PASS")
        except Exception as e:
            log("T04: rotate_then_undo_then_export", "FAIL", str(e))

        # ============================================================
        # T05: test_multiple_rotations_then_export
        # Rotate page 1 by 90 three times (=270) -> export -> verify
        # dimensions swapped (270 is equivalent to -90).
        # ============================================================
        try:
            pdf_bytes = await create_test_pdf(page, num_pages=1, width=612, height=792)
            await load_pdf_in_editor(page, pdf_bytes)

            orig_w, orig_h = await get_page_size(page, 1)

            # Rotate page 1 by 90 degrees three times (total 270)
            for _ in range(3):
                await page.evaluate("PdfEngine.rotatePage(1, 90)")
                await page.wait_for_timeout(200)

            # Export and reload
            exported, new_count = await export_and_reload(page)

            assert new_count == 1, f"Expected 1 page, got {new_count}"
            assert len(exported) > 0, "Exported PDF is empty"

            # After 270-degree rotation, dimensions should be swapped
            # (same as 90-degree rotation: width<->height)
            new_w, new_h = await get_page_size(page, 1)
            assert abs(new_w - orig_h) < 2, f"Expected width ~{orig_h}, got {new_w}"
            assert abs(new_h - orig_w) < 2, f"Expected height ~{orig_w}, got {new_h}"

            log("T05: multiple_rotations_then_export", "PASS")
        except Exception as e:
            log("T05: multiple_rotations_then_export", "FAIL", str(e))

        # ============================================================
        # Summary: console errors
        # ============================================================
        critical = [e for e in console_errors if "is not a function" in e or "Cannot read" in e or "Unexpected token" in e]
        if critical:
            log("T06: console_errors_check", "FAIL", f"{len(critical)} critical: {critical[0][:100]}")
        else:
            log("T06: console_errors_check", "PASS", f"No critical errors ({len(console_errors)} total)")

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
    print("E2E Test - Rotate Pages and Export PDF (6 scenarios)")
    print("=" * 60)
    failed = asyncio.run(run_tests())
    sys.exit(1 if failed > 0 else 0)
