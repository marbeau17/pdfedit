"""E2E Tests - Undo operations produce exportable PDFs

Tests that undo correctly restores state and that the resulting PDF
can be exported as a valid file.

Run with: python tests/test_e2e_undo_export.py
Requires: playwright (pip install playwright && playwright install chromium)
Server must be running at http://127.0.0.1:8765
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


def create_test_pdf(page_count=3, filepath=None):
    """Generate a minimal valid PDF with N pages using raw PDF construction."""
    if filepath is None:
        fd, filepath = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)

    objects = []
    obj_num = 1

    catalog_num = obj_num
    obj_num += 1
    pages_num = obj_num
    obj_num += 1
    font_num = obj_num
    obj_num += 1

    page_obj_nums = []
    content_obj_nums = []
    for i in range(page_count):
        page_obj_nums.append(obj_num)
        obj_num += 1
        content_obj_nums.append(obj_num)
        obj_num += 1

    body_parts = []
    offsets = {}

    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    current_offset = len(header)

    def add_object(num, content):
        nonlocal current_offset
        data = f"{num} 0 obj\n{content}\nendobj\n".encode("latin-1")
        offsets[num] = current_offset
        current_offset += len(data)
        body_parts.append(data)

    add_object(catalog_num, f"<< /Type /Catalog /Pages {pages_num} 0 R >>")

    kids = " ".join(f"{p} 0 R" for p in page_obj_nums)
    add_object(pages_num, f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>")

    add_object(font_num, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for i in range(page_count):
        text = f"BT /F1 24 Tf 100 700 Td (Page {i + 1} of {page_count}) Tj ET"
        stream_bytes = text.encode("latin-1")
        add_object(
            content_obj_nums[i],
            f"<< /Length {len(stream_bytes)} >>\nstream\n".rstrip("\n")
            + "\n"
            + text
            + "\nendstream",
        )
        add_object(
            page_obj_nums[i],
            f"<< /Type /Page /Parent {pages_num} 0 R "
            f"/MediaBox [0 0 612 792] "
            f"/Contents {content_obj_nums[i]} 0 R "
            f"/Resources << /Font << /F1 {font_num} 0 R >> >> >>",
        )

    xref_offset = current_offset
    total_objects = obj_num

    xref_lines = [b"xref\n"]
    xref_lines.append(f"0 {total_objects}\n".encode("latin-1"))
    xref_lines.append(b"0000000000 65535 f \n")
    for n in range(1, obj_num):
        xref_lines.append(f"{offsets[n]:010d} 00000 n \n".encode("latin-1"))

    trailer = (
        f"trailer\n"
        f"<< /Size {total_objects} /Root {catalog_num} 0 R >>\n"
        f"startxref\n"
        f"{xref_offset}\n"
        f"%%EOF\n"
    )

    with open(filepath, "wb") as f:
        f.write(header)
        for part in body_parts:
            f.write(part)
        for line in xref_lines:
            f.write(line)
        f.write(trailer.encode("latin-1"))

    return filepath


async def load_pdf_in_editor(page, pdf_path):
    """Navigate to home, upload PDF via file input, wait for editor to load."""
    await page.goto(BASE_URL, wait_until="networkidle")
    file_input = page.locator('input[type="file"][accept=".pdf"]')
    await file_input.set_input_files(pdf_path)
    await page.wait_for_url("**/editor**", timeout=15000)
    await page.wait_for_function(
        "() => typeof PdfEngine !== 'undefined' && PdfEngine.isLoaded()",
        timeout=10000,
    )
    await page.wait_for_timeout(1000)


async def get_engine_state(page):
    """Get PdfEngine state via page.evaluate."""
    return await page.evaluate("""() => ({
        loaded: PdfEngine.isLoaded(),
        pageCount: PdfEngine.getPageCount(),
        fileSize: PdfEngine.getCurrentBytes()?.length || 0,
        hasUndo: PdfEngine.hasUndo(),
    })""")


async def export_and_validate(page, download_dir, filename):
    """Trigger PdfEngine.download(), save the file, and validate the PDF header.

    Returns (path, size) of the downloaded file.
    """
    async with page.expect_download(timeout=10000) as download_info:
        await page.evaluate("(name) => PdfEngine.download(name)", filename)
    download = await download_info.value
    downloaded_path = os.path.join(download_dir, filename)
    await download.save_as(downloaded_path)

    with open(downloaded_path, "rb") as f:
        header = f.read(5)
    assert header == b"%PDF-", f"Invalid PDF header: {header!r}"

    size = os.path.getsize(downloaded_path)
    assert size > 100, f"Downloaded file too small: {size} bytes"
    return downloaded_path, size


async def run_tests():
    test_pdf_path = create_test_pdf(page_count=3)
    original_size = os.path.getsize(test_pdf_path)
    print(f"  Test PDF created: {test_pdf_path} ({original_size} bytes, 3 pages)")

    download_dir = tempfile.mkdtemp(prefix="pdfedit_test_undo_")
    print(f"  Download dir: {download_dir}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1400, "height": 900},
            locale="ja-JP",
            accept_downloads=True,
        )
        console_errors = []

        page = await context.new_page()
        page.on(
            "console",
            lambda msg: console_errors.append(msg.text)
            if msg.type == "error"
            else None,
        )
        page.on("pageerror", lambda err: console_errors.append(str(err)))

        # ==================================================================
        # T01: test_undo_delete_then_export
        # Load 3-page PDF -> delete page 2 -> undo -> verify 3 pages
        # restored -> export -> valid PDF.
        # ==================================================================
        try:
            await load_pdf_in_editor(page, test_pdf_path)

            state = await get_engine_state(page)
            assert state["pageCount"] == 3, f"Expected 3 pages, got {state['pageCount']}"

            # Delete page 2
            new_count = await page.evaluate("() => PdfEngine.removePages([2])")
            assert new_count == 2, f"After delete expected 2 pages, got {new_count}"

            # Undo
            undo_ok = await page.evaluate("() => PdfEngine.undo()")
            assert undo_ok is True, "undo() should return true"

            state = await get_engine_state(page)
            assert state["pageCount"] == 3, (
                f"After undo expected 3 pages, got {state['pageCount']}"
            )

            # Export and validate
            path, size = await export_and_validate(page, download_dir, "t01_undo_delete.pdf")

            log(
                "T01: Undo delete then export",
                "PASS",
                f"pages=3, exported={size}B",
            )
        except Exception as e:
            log("T01: Undo delete then export", "FAIL", str(e))

        # ==================================================================
        # T02: test_undo_rotate_then_export
        # Rotate page 1 -> undo -> export -> verify dimensions match
        # original (no rotation applied).
        # ==================================================================
        try:
            await load_pdf_in_editor(page, test_pdf_path)

            # Capture original dimensions of page 1
            orig_dims = await page.evaluate("() => PdfEngine.getPageSize(1)")

            # Rotate page 1 by 90 degrees
            await page.evaluate("() => PdfEngine.rotatePage(1, 90)")

            # Undo the rotation
            undo_ok = await page.evaluate("() => PdfEngine.undo()")
            assert undo_ok is True, "undo() should return true"

            # Verify dimensions match original (no rotation)
            after_dims = await page.evaluate("() => PdfEngine.getPageSize(1)")
            assert abs(after_dims["width"] - orig_dims["width"]) < 1, (
                f"Width mismatch: {after_dims['width']} vs {orig_dims['width']}"
            )
            assert abs(after_dims["height"] - orig_dims["height"]) < 1, (
                f"Height mismatch: {after_dims['height']} vs {orig_dims['height']}"
            )

            # Export and validate
            path, size = await export_and_validate(
                page, download_dir, "t02_undo_rotate.pdf"
            )

            log(
                "T02: Undo rotate then export",
                "PASS",
                f"dims={orig_dims['width']:.0f}x{orig_dims['height']:.0f}, exported={size}B",
            )
        except Exception as e:
            log("T02: Undo rotate then export", "FAIL", str(e))

        # ==================================================================
        # T03: test_undo_add_blank_then_export
        # Add blank page -> undo -> verify original page count -> export
        # -> valid PDF.
        # ==================================================================
        try:
            await load_pdf_in_editor(page, test_pdf_path)

            state_before = await get_engine_state(page)
            original_count = state_before["pageCount"]
            assert original_count == 3, f"Expected 3 pages, got {original_count}"

            # Add a blank page after page 1
            new_count = await page.evaluate("() => PdfEngine.addBlankPage(1)")
            assert new_count == 4, f"After addBlankPage expected 4 pages, got {new_count}"

            # Undo
            undo_ok = await page.evaluate("() => PdfEngine.undo()")
            assert undo_ok is True, "undo() should return true"

            state_after = await get_engine_state(page)
            assert state_after["pageCount"] == original_count, (
                f"After undo expected {original_count} pages, got {state_after['pageCount']}"
            )

            # Export and validate
            path, size = await export_and_validate(
                page, download_dir, "t03_undo_blank.pdf"
            )

            log(
                "T03: Undo add blank then export",
                "PASS",
                f"pages={state_after['pageCount']}, exported={size}B",
            )
        except Exception as e:
            log("T03: Undo add blank then export", "FAIL", str(e))

        # ==================================================================
        # T04: test_multiple_undo_then_export
        # Do 3 operations -> undo all 3 -> export -> should match original
        # page count and file size.
        # ==================================================================
        try:
            await load_pdf_in_editor(page, test_pdf_path)

            state_original = await get_engine_state(page)
            original_count = state_original["pageCount"]
            original_size_bytes = state_original["fileSize"]

            # Operation 1: delete page 3
            await page.evaluate("() => PdfEngine.removePages([3])")
            # Operation 2: add blank page at end
            await page.evaluate("() => PdfEngine.addBlankPage()")
            # Operation 3: rotate page 1
            await page.evaluate("() => PdfEngine.rotatePage(1, 90)")

            # Undo all 3 operations (reverse order)
            for i in range(3):
                undo_ok = await page.evaluate("() => PdfEngine.undo()")
                assert undo_ok is True, f"undo() #{i+1} should return true"

            state_restored = await get_engine_state(page)
            assert state_restored["pageCount"] == original_count, (
                f"After 3 undos expected {original_count} pages, "
                f"got {state_restored['pageCount']}"
            )

            # File size should match original (byte-identical undo)
            assert state_restored["fileSize"] == original_size_bytes, (
                f"File size mismatch: {state_restored['fileSize']} vs {original_size_bytes}"
            )

            # No more undo available
            assert state_restored["hasUndo"] is False, (
                "hasUndo should be false after undoing all operations"
            )

            # Export and validate
            path, size = await export_and_validate(
                page, download_dir, "t04_multi_undo.pdf"
            )

            log(
                "T04: Multiple undo then export",
                "PASS",
                f"pages={state_restored['pageCount']}, "
                f"size={state_restored['fileSize']}B, exported={size}B",
            )
        except Exception as e:
            log("T04: Multiple undo then export", "FAIL", str(e))

        # ==================================================================
        # T05: test_undo_when_nothing_to_undo
        # Verify undo() returns false on fresh load -> export still works.
        # ==================================================================
        try:
            await load_pdf_in_editor(page, test_pdf_path)

            state = await get_engine_state(page)
            assert state["hasUndo"] is False, (
                "hasUndo should be false on fresh load"
            )

            # Calling undo on fresh load should return false
            undo_ok = await page.evaluate("() => PdfEngine.undo()")
            assert undo_ok is False, "undo() on fresh load should return false"

            # Engine state should be unchanged
            state_after = await get_engine_state(page)
            assert state_after["pageCount"] == state["pageCount"], (
                "Page count changed after no-op undo"
            )
            assert state_after["fileSize"] == state["fileSize"], (
                "File size changed after no-op undo"
            )

            # Export should still work fine
            path, size = await export_and_validate(
                page, download_dir, "t05_noop_undo.pdf"
            )

            log(
                "T05: Undo when nothing to undo",
                "PASS",
                f"undo returned false, exported={size}B",
            )
        except Exception as e:
            log("T05: Undo when nothing to undo", "FAIL", str(e))

        # ==================================================================
        # T06: test_partial_undo_then_export
        # Do 3 operations -> undo only 1 -> export -> verify intermediate
        # state is correct (2 operations still applied).
        # ==================================================================
        try:
            await load_pdf_in_editor(page, test_pdf_path)

            state_original = await get_engine_state(page)
            original_count = state_original["pageCount"]
            assert original_count == 3, f"Expected 3 pages, got {original_count}"

            # Operation 1: delete page 3 -> 2 pages
            await page.evaluate("() => PdfEngine.removePages([3])")
            # Operation 2: add blank at end -> 3 pages
            await page.evaluate("() => PdfEngine.addBlankPage()")
            # Operation 3: add another blank at end -> 4 pages
            await page.evaluate("() => PdfEngine.addBlankPage()")

            state_after_ops = await get_engine_state(page)
            assert state_after_ops["pageCount"] == 4, (
                f"After 3 ops expected 4 pages, got {state_after_ops['pageCount']}"
            )

            # Undo only the last operation (remove the second blank)
            undo_ok = await page.evaluate("() => PdfEngine.undo()")
            assert undo_ok is True, "undo() should return true"

            state_partial = await get_engine_state(page)
            assert state_partial["pageCount"] == 3, (
                f"After partial undo expected 3 pages, got {state_partial['pageCount']}"
            )

            # Should still have undo available (2 ops remain in history)
            assert state_partial["hasUndo"] is True, (
                "hasUndo should be true (2 operations remain)"
            )

            # Export and validate the intermediate state
            path, size = await export_and_validate(
                page, download_dir, "t06_partial_undo.pdf"
            )

            # Re-load the exported file to verify it has the right page count
            await load_pdf_in_editor(page, path)
            reloaded_state = await get_engine_state(page)
            assert reloaded_state["pageCount"] == 3, (
                f"Re-loaded exported PDF expected 3 pages, "
                f"got {reloaded_state['pageCount']}"
            )

            log(
                "T06: Partial undo then export",
                "PASS",
                f"pages after partial undo=3, re-loaded=3, exported={size}B",
            )
        except Exception as e:
            log("T06: Partial undo then export", "FAIL", str(e))

        # ==================================================================
        # T07: Console errors check
        # ==================================================================
        critical = [
            e
            for e in console_errors
            if "is not a function" in e
            or "Cannot read" in e
            or "Unexpected token" in e
        ]
        if critical:
            log(
                "T07: No critical console errors",
                "FAIL",
                f"{len(critical)} errors: {critical[0][:100]}",
            )
        else:
            log(
                "T07: No critical console errors",
                "PASS",
                f"0 critical ({len(console_errors)} total console messages)",
            )

        await browser.close()

    # Cleanup
    try:
        os.unlink(test_pdf_path)
        for f in os.listdir(download_dir):
            os.unlink(os.path.join(download_dir, f))
        os.rmdir(download_dir)
    except OSError:
        pass

    # Summary
    print()
    print("=" * 60)
    passed = sum(1 for _, s, _ in RESULTS if s == "PASS")
    failed = sum(1 for _, s, _ in RESULTS if s == "FAIL")
    print(f"Result: {passed} PASS / {failed} FAIL / {len(RESULTS)} TOTAL")
    if failed > 0:
        print()
        print("Failed:")
        for name, status, detail in RESULTS:
            if status == "FAIL":
                print(f"  [NG] {name}: {detail}")
    print("=" * 60)
    return failed


if __name__ == "__main__":
    print("=" * 60)
    print("E2E Tests - Undo Operations Produce Exportable PDFs (7 scenarios)")
    print("=" * 60)
    failed = asyncio.run(run_tests())
    sys.exit(1 if failed > 0 else 0)
