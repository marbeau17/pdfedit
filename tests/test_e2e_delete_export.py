"""
E2E Test - Delete Pages and Export PDF
Tests that after deleting pages, the PDF can still be exported correctly.
Runs against a live server at http://127.0.0.1:8765.

Usage:
    python tests/test_e2e_delete_export.py
"""
import asyncio
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


def make_pdf(num_pages: int) -> str:
    """Generate a minimal valid PDF with the given number of pages and return its path."""
    # Build a minimal PDF from scratch using raw bytes.
    # Structure: header, pages tree, N page objects, catalog, xref, trailer.
    objects = []  # list of bytes for each object (1-indexed via position)

    # Object 1: Catalog
    # Object 2: Pages tree
    # Objects 3..2+N: individual Page objects

    page_obj_nums = list(range(3, 3 + num_pages))
    kids_str = " ".join(f"{n} 0 R" for n in page_obj_nums)

    obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    obj2 = (
        f"2 0 obj\n<< /Type /Pages /Kids [{kids_str}] /Count {num_pages} >>\nendobj\n"
    ).encode()

    objects.append(obj1)
    objects.append(obj2)

    for _ in range(num_pages):
        obj_num = len(objects) + 1
        page_obj = (
            f"{obj_num} 0 obj\n"
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\n"
            f"endobj\n"
        ).encode()
        objects.append(page_obj)

    # Build the file
    body = b"%PDF-1.4\n"
    offsets = []
    for obj_bytes in objects:
        offsets.append(len(body))
        body += obj_bytes

    xref_offset = len(body)
    num_entries = len(objects) + 1  # +1 for the free entry at 0
    xref = f"xref\n0 {num_entries}\n".encode()
    xref += b"0000000000 65535 f \n"
    for off in offsets:
        xref += f"{off:010d} 00000 n \n".encode()

    trailer = (
        f"trailer\n<< /Size {num_entries} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode()

    pdf_bytes = body + xref + trailer

    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.write(fd, pdf_bytes)
    os.close(fd)
    return path


async def load_pdf_in_editor(page, pdf_path: str):
    """Navigate to home, upload PDF, wait for editor to load, and wait for PdfEngine."""
    await page.goto(BASE_URL, wait_until="networkidle")
    file_input = page.locator('input[type="file"][accept=".pdf"]')
    await file_input.set_input_files(pdf_path)
    await page.wait_for_url("**/editor**", timeout=15000)
    # Wait for PdfEngine to be loaded
    await page.wait_for_function("typeof PdfEngine !== 'undefined' && PdfEngine.isLoaded()", timeout=10000)


async def verify_downloaded_pdf(page, download, expected_pages: int) -> tuple:
    """Verify a downloaded PDF file is valid and has the expected page count.

    Returns (is_valid, detail_message).
    """
    path = await download.path()
    if path is None:
        return False, "download path is None"

    size = os.path.getsize(path)
    if size == 0:
        return False, "downloaded file is empty"

    with open(path, "rb") as f:
        header = f.read(5)
    if header != b"%PDF-":
        return False, f"bad header: {header!r}"

    # Re-load the downloaded PDF in the browser via PdfEngine.loadFromBytes to check page count
    with open(path, "rb") as f:
        pdf_bytes = f.read()

    # Transfer bytes to browser and load
    byte_list = list(pdf_bytes)
    actual_pages = await page.evaluate(
        """async (byteArray) => {
            const bytes = new Uint8Array(byteArray);
            return await PdfEngine.loadFromBytes(bytes, 'verify.pdf');
        }""",
        byte_list,
    )

    if actual_pages != expected_pages:
        return False, f"expected {expected_pages} pages, got {actual_pages}"

    return True, f"valid PDF, {actual_pages} pages, {size} bytes"


async def run_tests():
    tmp_files = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                locale="ja-JP",
                accept_downloads=True,
            )

            # ===== T01: Delete single page (middle) then export =====
            try:
                pdf_path = make_pdf(3)
                tmp_files.append(pdf_path)
                page = await context.new_page()
                await load_pdf_in_editor(page, pdf_path)

                # Verify initial page count
                initial = await page.evaluate("PdfEngine.getPageCount()")
                assert initial == 3, f"initial count {initial} != 3"

                # Delete page 2
                remaining = await page.evaluate("PdfEngine.removePages([2])")
                assert remaining == 2, f"after delete got {remaining} != 2"

                # Export via download
                async with page.expect_download() as download_info:
                    await page.evaluate("PdfEngine.download('test_delete_middle.pdf')")
                download = await download_info.value

                valid, detail = await verify_downloaded_pdf(page, download, 2)
                assert valid, detail
                await page.close()
                log("T01: delete middle page then export", "PASS", detail)
            except Exception as e:
                log("T01: delete middle page then export", "FAIL", str(e))

            # ===== T02: Delete first page then export =====
            try:
                pdf_path = make_pdf(3)
                tmp_files.append(pdf_path)
                page = await context.new_page()
                await load_pdf_in_editor(page, pdf_path)

                remaining = await page.evaluate("PdfEngine.removePages([1])")
                assert remaining == 2, f"after delete got {remaining} != 2"

                async with page.expect_download() as download_info:
                    await page.evaluate("PdfEngine.download('test_delete_first.pdf')")
                download = await download_info.value

                valid, detail = await verify_downloaded_pdf(page, download, 2)
                assert valid, detail
                await page.close()
                log("T02: delete first page then export", "PASS", detail)
            except Exception as e:
                log("T02: delete first page then export", "FAIL", str(e))

            # ===== T03: Delete last page then export =====
            try:
                pdf_path = make_pdf(3)
                tmp_files.append(pdf_path)
                page = await context.new_page()
                await load_pdf_in_editor(page, pdf_path)

                remaining = await page.evaluate("PdfEngine.removePages([3])")
                assert remaining == 2, f"after delete got {remaining} != 2"

                async with page.expect_download() as download_info:
                    await page.evaluate("PdfEngine.download('test_delete_last.pdf')")
                download = await download_info.value

                valid, detail = await verify_downloaded_pdf(page, download, 2)
                assert valid, detail
                await page.close()
                log("T03: delete last page then export", "PASS", detail)
            except Exception as e:
                log("T03: delete last page then export", "FAIL", str(e))

            # ===== T04: Delete multiple non-consecutive pages then export =====
            try:
                pdf_path = make_pdf(5)
                tmp_files.append(pdf_path)
                page = await context.new_page()
                await load_pdf_in_editor(page, pdf_path)

                initial = await page.evaluate("PdfEngine.getPageCount()")
                assert initial == 5, f"initial count {initial} != 5"

                remaining = await page.evaluate("PdfEngine.removePages([1, 3, 5])")
                assert remaining == 2, f"after delete got {remaining} != 2"

                async with page.expect_download() as download_info:
                    await page.evaluate("PdfEngine.download('test_delete_multiple.pdf')")
                download = await download_info.value

                valid, detail = await verify_downloaded_pdf(page, download, 2)
                assert valid, detail
                await page.close()
                log("T04: delete multiple pages then export", "PASS", detail)
            except Exception as e:
                log("T04: delete multiple pages then export", "FAIL", str(e))

            # ===== T05: Delete all but one page then export =====
            try:
                pdf_path = make_pdf(3)
                tmp_files.append(pdf_path)
                page = await context.new_page()
                await load_pdf_in_editor(page, pdf_path)

                remaining = await page.evaluate("PdfEngine.removePages([1, 3])")
                assert remaining == 1, f"after delete got {remaining} != 1"

                async with page.expect_download() as download_info:
                    await page.evaluate("PdfEngine.download('test_delete_all_but_one.pdf')")
                download = await download_info.value

                valid, detail = await verify_downloaded_pdf(page, download, 1)
                assert valid, detail
                await page.close()
                log("T05: delete all but one then export", "PASS", detail)
            except Exception as e:
                log("T05: delete all but one then export", "FAIL", str(e))

            await browser.close()

    finally:
        # Clean up temp PDF files
        for f in tmp_files:
            try:
                os.unlink(f)
            except OSError:
                pass

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
    print("E2E Test - Delete Pages and Export PDF (5 scenarios)")
    print("=" * 60)
    failed = asyncio.run(run_tests())
    sys.exit(1 if failed > 0 else 0)
