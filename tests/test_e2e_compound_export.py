"""
E2E Test - Compound Operations and Export PDF
Tests that combining multiple operations in sequence always produces a valid, exportable PDF.
This is the critical test: even trivial changes should produce a valid exportable PDF.

Runs against a live server at http://127.0.0.1:8765.

Usage:
    python tests/test_e2e_compound_export.py
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
    objects = []
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

    body = b"%PDF-1.4\n"
    offsets = []
    for obj_bytes in objects:
        offsets.append(len(body))
        body += obj_bytes

    xref_offset = len(body)
    num_entries = len(objects) + 1
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
    await page.wait_for_function(
        "typeof PdfEngine !== 'undefined' && PdfEngine.isLoaded()", timeout=10000
    )


async def assert_valid_pdf(page, min_pages=1):
    """Verify PdfEngine has a valid exportable PDF."""
    result = await page.evaluate("""async () => {
        const bytes = PdfEngine.getCurrentBytes();
        if (!bytes || bytes.length === 0) return { valid: false, reason: 'no bytes' };
        // Check PDF header
        const header = String.fromCharCode(...bytes.slice(0, 5));
        if (header !== '%PDF-') return { valid: false, reason: 'bad header: ' + header };
        return { valid: true, size: bytes.length, pages: PdfEngine.getPageCount() };
    }""")
    assert result['valid'], f"Invalid PDF: {result.get('reason')}"
    assert result['pages'] >= min_pages, (
        f"Expected at least {min_pages} pages, got {result['pages']}"
    )
    return result


async def verify_downloaded_pdf(page, download, expected_pages: int) -> tuple:
    """Verify a downloaded PDF file is valid and has the expected page count."""
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

    with open(path, "rb") as f:
        pdf_bytes = f.read()

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

            # ===== T01: Rotate page 1 -> delete page 2 -> export =====
            try:
                pdf_path = make_pdf(3)
                tmp_files.append(pdf_path)
                page = await context.new_page()
                await load_pdf_in_editor(page, pdf_path)

                initial = await page.evaluate("PdfEngine.getPageCount()")
                assert initial == 3, f"initial count {initial} != 3"

                # Rotate page 1 by 90 degrees
                await page.evaluate("PdfEngine.rotatePage(1, 90)")
                count_after_rotate = await page.evaluate("PdfEngine.getPageCount()")
                assert count_after_rotate == 3, "page count changed after rotate"

                # Delete page 2
                remaining = await page.evaluate("PdfEngine.removePages([2])")
                assert remaining == 2, f"after delete got {remaining} != 2"

                # Export via download
                async with page.expect_download() as download_info:
                    await page.evaluate(
                        "PdfEngine.download('test_rotate_delete.pdf')"
                    )
                download = await download_info.value

                valid, detail = await verify_downloaded_pdf(page, download, 2)
                assert valid, detail
                await page.close()
                log("T01: rotate then delete then export", "PASS", detail)
            except Exception as e:
                log("T01: rotate then delete then export", "FAIL", str(e))

            # ===== T02: Add blank page -> add branding -> export =====
            try:
                pdf_path = make_pdf(2)
                tmp_files.append(pdf_path)
                page = await context.new_page()
                await load_pdf_in_editor(page, pdf_path)

                initial = await page.evaluate("PdfEngine.getPageCount()")
                assert initial == 2, f"initial count {initial} != 2"

                # Add a blank page after page 2
                new_count = await page.evaluate("PdfEngine.addBlankPage(2)")
                assert new_count == 3, f"after addBlankPage got {new_count} != 3"

                # Add branding (page numbers + footer) to all pages
                await page.evaluate("""PdfEngine.addBranding({
                    enableLogo: false,
                    enablePageNum: true,
                    footerText: 'Test Branding',
                    copyrightText: 'Test Copyright',
                    skipFirstPageNum: false,
                    skipFirstLogo: false
                })""")

                count_after_branding = await page.evaluate("PdfEngine.getPageCount()")
                assert count_after_branding == 3, (
                    f"page count changed after branding: {count_after_branding}"
                )

                # Export
                async with page.expect_download() as download_info:
                    await page.evaluate(
                        "PdfEngine.download('test_blank_branding.pdf')"
                    )
                download = await download_info.value

                valid, detail = await verify_downloaded_pdf(page, download, 3)
                assert valid, detail
                await page.close()
                log("T02: add blank then branding then export", "PASS", detail)
            except Exception as e:
                log("T02: add blank then branding then export", "FAIL", str(e))

            # ===== T03: Merge with another PDF -> reorder pages -> export =====
            try:
                pdf_path = make_pdf(2)
                tmp_files.append(pdf_path)
                merge_path = make_pdf(2)
                tmp_files.append(merge_path)
                page = await context.new_page()
                await load_pdf_in_editor(page, pdf_path)

                initial = await page.evaluate("PdfEngine.getPageCount()")
                assert initial == 2, f"initial count {initial} != 2"

                # Read the merge PDF bytes and merge
                with open(merge_path, "rb") as f:
                    merge_bytes = list(f.read())

                new_count = await page.evaluate(
                    """async (byteArray) => {
                        const bytes = new Uint8Array(byteArray);
                        return await PdfEngine.mergePdf(bytes);
                    }""",
                    merge_bytes,
                )
                assert new_count == 4, f"after merge got {new_count} != 4"

                # Reorder pages: reverse order [4, 3, 2, 1]
                reordered_count = await page.evaluate(
                    "PdfEngine.reorderPages([4, 3, 2, 1])"
                )
                assert reordered_count == 4, (
                    f"after reorder got {reordered_count} != 4"
                )

                # Export
                async with page.expect_download() as download_info:
                    await page.evaluate(
                        "PdfEngine.download('test_merge_reorder.pdf')"
                    )
                download = await download_info.value

                valid, detail = await verify_downloaded_pdf(page, download, 4)
                assert valid, detail
                await page.close()
                log("T03: merge then reorder then export", "PASS", detail)
            except Exception as e:
                log("T03: merge then reorder then export", "FAIL", str(e))

            # ===== T04: Delete page 1 -> add text to new page 1 -> rotate -> export =====
            try:
                pdf_path = make_pdf(3)
                tmp_files.append(pdf_path)
                page = await context.new_page()
                await load_pdf_in_editor(page, pdf_path)

                initial = await page.evaluate("PdfEngine.getPageCount()")
                assert initial == 3, f"initial count {initial} != 3"

                # Delete page 1
                remaining = await page.evaluate("PdfEngine.removePages([1])")
                assert remaining == 2, f"after delete got {remaining} != 2"

                # Add text to new page 1 (was originally page 2)
                await page.evaluate(
                    "PdfEngine.addText(1, 'Hello E2E Test', 100, 400, 24)"
                )
                count_after_text = await page.evaluate("PdfEngine.getPageCount()")
                assert count_after_text == 2, (
                    f"page count changed after addText: {count_after_text}"
                )

                # Rotate new page 1
                await page.evaluate("PdfEngine.rotatePage(1, 90)")

                # Export
                async with page.expect_download() as download_info:
                    await page.evaluate(
                        "PdfEngine.download('test_delete_text_rotate.pdf')"
                    )
                download = await download_info.value

                valid, detail = await verify_downloaded_pdf(page, download, 2)
                assert valid, detail
                await page.close()
                log("T04: delete add-text rotate then export", "PASS", detail)
            except Exception as e:
                log("T04: delete add-text rotate then export", "FAIL", str(e))

            # ===== T05: 10 small operations then export =====
            try:
                pdf_path = make_pdf(5)
                tmp_files.append(pdf_path)
                page = await context.new_page()
                await load_pdf_in_editor(page, pdf_path)

                initial = await page.evaluate("PdfEngine.getPageCount()")
                assert initial == 5, f"initial count {initial} != 5"

                # Op 1: Rotate page 1
                await page.evaluate("PdfEngine.rotatePage(1, 90)")
                # Op 2: Rotate page 3
                await page.evaluate("PdfEngine.rotatePage(3, 180)")
                # Op 3: Add text to page 2
                await page.evaluate(
                    "PdfEngine.addText(2, 'Operation 3', 50, 700, 14)"
                )
                # Op 4: Add blank page after page 5
                await page.evaluate("PdfEngine.addBlankPage(5)")
                # 6 pages now
                count = await page.evaluate("PdfEngine.getPageCount()")
                assert count == 6, f"expected 6 after addBlank, got {count}"

                # Op 5: Add text to the new blank page (page 6)
                await page.evaluate(
                    "PdfEngine.addText(6, 'New blank page text', 100, 400, 18)"
                )
                # Op 6: Rotate page 4
                await page.evaluate("PdfEngine.rotatePage(4, 270)")
                # Op 7: Delete page 5 (one of the original pages)
                await page.evaluate("PdfEngine.removePages([5])")
                # 5 pages now
                count = await page.evaluate("PdfEngine.getPageCount()")
                assert count == 5, f"expected 5 after delete, got {count}"

                # Op 8: Add text to page 1
                await page.evaluate(
                    "PdfEngine.addText(1, 'Op 8 text', 200, 300, 10)"
                )
                # Op 9: Rotate page 2
                await page.evaluate("PdfEngine.rotatePage(2, 90)")
                # Op 10: Add blank page after page 1
                await page.evaluate("PdfEngine.addBlankPage(1)")
                # 6 pages now
                count = await page.evaluate("PdfEngine.getPageCount()")
                assert count == 6, f"expected 6 after final addBlank, got {count}"

                # Export
                async with page.expect_download() as download_info:
                    await page.evaluate(
                        "PdfEngine.download('test_many_small_edits.pdf')"
                    )
                download = await download_info.value

                valid, detail = await verify_downloaded_pdf(page, download, 6)
                assert valid, detail
                await page.close()
                log("T05: many small edits then export", "PASS", detail)
            except Exception as e:
                log("T05: many small edits then export", "FAIL", str(e))

            # ===== T06: Edit -> undo -> different edit -> export =====
            try:
                pdf_path = make_pdf(3)
                tmp_files.append(pdf_path)
                page = await context.new_page()
                await load_pdf_in_editor(page, pdf_path)

                initial = await page.evaluate("PdfEngine.getPageCount()")
                assert initial == 3, f"initial count {initial} != 3"

                # Edit: rotate page 1
                await page.evaluate("PdfEngine.rotatePage(1, 90)")

                # Undo the rotation
                undo_result = await page.evaluate("PdfEngine.undo()")
                assert undo_result is not False, "undo returned false"

                count_after_undo = await page.evaluate("PdfEngine.getPageCount()")
                assert count_after_undo == 3, (
                    f"page count after undo: {count_after_undo}"
                )

                # Different edit: add text instead
                await page.evaluate(
                    "PdfEngine.addText(1, 'After undo', 150, 500, 16)"
                )

                # Export
                async with page.expect_download() as download_info:
                    await page.evaluate(
                        "PdfEngine.download('test_edit_undo_edit.pdf')"
                    )
                download = await download_info.value

                valid, detail = await verify_downloaded_pdf(page, download, 3)
                assert valid, detail
                await page.close()
                log("T06: edit undo edit then export", "PASS", detail)
            except Exception as e:
                log("T06: edit undo edit then export", "FAIL", str(e))

            # ===== T07: Resize pages -> add branding -> export =====
            try:
                # Use 3 pages; resizePages needs >= 2 pages
                pdf_path = make_pdf(3)
                tmp_files.append(pdf_path)
                page = await context.new_page()
                await load_pdf_in_editor(page, pdf_path)

                initial = await page.evaluate("PdfEngine.getPageCount()")
                assert initial == 3, f"initial count {initial} != 3"

                # Resize pages (normalizes all pages to same dimensions)
                resize_result = await page.evaluate("PdfEngine.resizePages()")
                assert resize_result is not None, "resizePages returned null"

                count_after_resize = await page.evaluate("PdfEngine.getPageCount()")
                assert count_after_resize == 3, (
                    f"page count after resize: {count_after_resize}"
                )

                # Add branding
                await page.evaluate("""PdfEngine.addBranding({
                    enableLogo: false,
                    enablePageNum: true,
                    footerText: 'Resized and Branded',
                    copyrightText: 'Test',
                    skipFirstPageNum: false,
                    skipFirstLogo: false
                })""")

                # Export
                async with page.expect_download() as download_info:
                    await page.evaluate(
                        "PdfEngine.download('test_resize_branding.pdf')"
                    )
                download = await download_info.value

                valid, detail = await verify_downloaded_pdf(page, download, 3)
                assert valid, detail
                await page.close()
                log("T07: resize then branding then export", "PASS", detail)
            except Exception as e:
                log("T07: resize then branding then export", "FAIL", str(e))

            # ===== T08: Export after every single operation type =====
            try:
                pdf_path = make_pdf(4)
                tmp_files.append(pdf_path)
                page = await context.new_page()
                await load_pdf_in_editor(page, pdf_path)

                initial = await page.evaluate("PdfEngine.getPageCount()")
                assert initial == 4, f"initial count {initial} != 4"

                operations = [
                    # (description, js_expression, expected_min_pages)
                    (
                        "rotatePage",
                        "PdfEngine.rotatePage(1, 90)",
                        4,
                    ),
                    (
                        "addText",
                        "PdfEngine.addText(1, 'Validation text', 100, 400, 12)",
                        4,
                    ),
                    (
                        "addBlankPage",
                        "PdfEngine.addBlankPage(4)",
                        5,
                    ),
                    (
                        "reorderPages",
                        "PdfEngine.reorderPages([5, 4, 3, 2, 1])",
                        5,
                    ),
                    (
                        "addBranding",
                        """PdfEngine.addBranding({
                            enableLogo: false,
                            enablePageNum: true,
                            footerText: 'Validation',
                            copyrightText: 'Test',
                            skipFirstPageNum: false,
                            skipFirstLogo: false
                        })""",
                        5,
                    ),
                    (
                        "removePages",
                        "PdfEngine.removePages([5])",
                        4,
                    ),
                ]

                for op_name, js_expr, expected_min in operations:
                    await page.evaluate(js_expr)
                    result = await assert_valid_pdf(page, min_pages=expected_min)
                    actual_pages = result['pages']
                    print(
                        f"    after {op_name}: valid PDF, "
                        f"{actual_pages} pages, {result['size']} bytes"
                    )

                await page.close()
                log(
                    "T08: export after every single operation",
                    "PASS",
                    f"all {len(operations)} operations produce valid PDF",
                )
            except Exception as e:
                log("T08: export after every single operation", "FAIL", str(e))

            await browser.close()

    finally:
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
    print("E2E Test - Compound Operations and Export PDF (8 scenarios)")
    print("=" * 60)
    failed = asyncio.run(run_tests())
    sys.exit(1 if failed > 0 else 0)
