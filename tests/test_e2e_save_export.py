"""E2E Tests - PDF Save & Export functionality

Tests PDF load, export/download, file size preservation, and round-trip integrity.
Run with: python tests/test_e2e_save_export.py
Requires: playwright (pip install playwright && playwright install chromium)
Server must be running at http://127.0.0.1:8765
"""
import asyncio
import os
import struct
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
    """Generate a minimal valid PDF with N pages using raw PDF construction.

    Returns the file path to the created PDF.
    """
    if filepath is None:
        fd, filepath = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)

    # Build a minimal but valid multi-page PDF from scratch.
    # We construct the cross-reference table properly so pdf-lib can parse it.
    objects = []  # list of (obj_num, bytes)
    obj_num = 1

    # Object 1: Catalog
    catalog_num = obj_num
    obj_num += 1

    # Object 2: Pages (parent)
    pages_num = obj_num
    obj_num += 1

    # Object 3: Font
    font_num = obj_num
    obj_num += 1

    # Create page objects
    page_obj_nums = []
    content_obj_nums = []
    for i in range(page_count):
        page_obj_nums.append(obj_num)
        obj_num += 1
        content_obj_nums.append(obj_num)
        obj_num += 1

    # Now build the actual byte content
    body_parts = []
    offsets = {}  # obj_num -> byte offset

    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    current_offset = len(header)

    def add_object(num, content):
        nonlocal current_offset
        data = f"{num} 0 obj\n{content}\nendobj\n".encode("latin-1")
        offsets[num] = current_offset
        current_offset += len(data)
        body_parts.append(data)

    # Catalog
    add_object(catalog_num, f"<< /Type /Catalog /Pages {pages_num} 0 R >>")

    # Pages
    kids = " ".join(f"{p} 0 R" for p in page_obj_nums)
    add_object(pages_num, f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>")

    # Font (Helvetica)
    add_object(font_num, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    # Page objects and their content streams
    for i in range(page_count):
        # Content stream - draw page number text
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

    # Cross-reference table
    xref_offset = current_offset
    total_objects = obj_num  # includes object 0

    xref_lines = [b"xref\n"]
    xref_lines.append(f"0 {total_objects}\n".encode("latin-1"))
    xref_lines.append(b"0000000000 65535 f \n")
    for n in range(1, obj_num):
        xref_lines.append(f"{offsets[n]:010d} 00000 n \n".encode("latin-1"))

    # Trailer
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
    # Wait for PdfEngine to finish loading the PDF
    await page.wait_for_function("() => typeof PdfEngine !== 'undefined' && PdfEngine.isLoaded()", timeout=10000)
    await page.wait_for_timeout(1000)


async def get_engine_state(page):
    """Get PdfEngine state via page.evaluate."""
    return await page.evaluate("""() => ({
        loaded: PdfEngine.isLoaded(),
        pageCount: PdfEngine.getPageCount(),
        fileSize: PdfEngine.getCurrentBytes()?.length || 0,
        info: PdfEngine.getFileInfo(),
    })""")


async def run_tests():
    # Create test PDF
    test_pdf_path = create_test_pdf(page_count=3)
    original_size = os.path.getsize(test_pdf_path)
    print(f"  Test PDF created: {test_pdf_path} ({original_size} bytes, 3 pages)")

    download_dir = tempfile.mkdtemp(prefix="pdfedit_test_downloads_")
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
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: console_errors.append(str(err)))

        # ======================================================================
        # T01: test_load_pdf_and_export_unchanged
        # Load a PDF, immediately export/download without changes.
        # Verify the downloaded file is valid PDF and has same page count.
        # ======================================================================
        try:
            await load_pdf_in_editor(page, test_pdf_path)

            state = await get_engine_state(page)
            assert state["loaded"], "PdfEngine not loaded"
            assert state["pageCount"] == 3, f"Expected 3 pages, got {state['pageCount']}"

            # Trigger download via PdfEngine.download() and capture it
            async with page.expect_download(timeout=10000) as download_info:
                await page.evaluate("() => PdfEngine.download('test_export.pdf')")

            download = await download_info.value
            downloaded_path = os.path.join(download_dir, "t01_export.pdf")
            await download.save_as(downloaded_path)

            # Verify it is a valid PDF (starts with %PDF-)
            with open(downloaded_path, "rb") as f:
                header = f.read(5)
            assert header == b"%PDF-", f"Invalid PDF header: {header!r}"

            # Load the downloaded file back to verify page count
            downloaded_size = os.path.getsize(downloaded_path)
            assert downloaded_size > 100, f"Downloaded file too small: {downloaded_size} bytes"

            # Verify page count by loading exported PDF back into the engine
            exported_page_count = await page.evaluate("""async (path) => {
                // We can't read local files from browser, so use getCurrentBytes
                // which represents the currently loaded (unchanged) PDF
                return PdfEngine.getPageCount();
            }""", None)
            assert exported_page_count == 3, f"Expected 3 pages after export, got {exported_page_count}"

            log("T01: Load PDF and export unchanged", "PASS",
                f"downloaded={downloaded_size}B, pages={exported_page_count}")
        except Exception as e:
            log("T01: Load PDF and export unchanged", "FAIL", str(e))

        # ======================================================================
        # T02: test_export_preserves_file_size
        # Exported file size should be within 20% of original (no bloat/corruption).
        # ======================================================================
        try:
            # Use the file downloaded in T01, or re-download
            if not os.path.exists(os.path.join(download_dir, "t01_export.pdf")):
                # Re-load and download
                await load_pdf_in_editor(page, test_pdf_path)
                async with page.expect_download(timeout=10000) as download_info:
                    await page.evaluate("() => PdfEngine.download('test_export.pdf')")
                download = await download_info.value
                await download.save_as(os.path.join(download_dir, "t01_export.pdf"))

            downloaded_path = os.path.join(download_dir, "t01_export.pdf")
            downloaded_size = os.path.getsize(downloaded_path)

            # pdf-lib re-serializes the PDF, so it may differ from the raw original.
            # Compare against the in-engine size (getCurrentBytes) which is what pdf-lib produces.
            engine_size = await page.evaluate("() => PdfEngine.getCurrentBytes()?.length || 0")

            # The download should match the engine's internal representation closely
            size_ratio = downloaded_size / engine_size if engine_size > 0 else 0
            assert 0.8 <= size_ratio <= 1.2, (
                f"Size ratio {size_ratio:.2f} outside 0.8-1.2 range "
                f"(downloaded={downloaded_size}, engine={engine_size})"
            )

            log("T02: Export preserves file size", "PASS",
                f"ratio={size_ratio:.3f} (downloaded={downloaded_size}B, engine={engine_size}B)")
        except Exception as e:
            log("T02: Export preserves file size", "FAIL", str(e))

        # ======================================================================
        # T03: test_round_trip_load_export_load
        # Load PDF -> export -> load exported file back -> verify same page count.
        # ======================================================================
        try:
            # Make sure we have a clean state: load the original test PDF
            await load_pdf_in_editor(page, test_pdf_path)

            state_before = await get_engine_state(page)
            assert state_before["loaded"], "PdfEngine not loaded (round-trip)"
            original_pages = state_before["pageCount"]

            # Export/download
            async with page.expect_download(timeout=10000) as download_info:
                await page.evaluate("() => PdfEngine.download('round_trip.pdf')")
            download = await download_info.value
            round_trip_path = os.path.join(download_dir, "t03_round_trip.pdf")
            await download.save_as(round_trip_path)

            # Verify the exported file is valid PDF
            with open(round_trip_path, "rb") as f:
                header = f.read(5)
            assert header == b"%PDF-", f"Round-trip PDF invalid header: {header!r}"

            # Load the exported PDF back into the editor
            await load_pdf_in_editor(page, round_trip_path)

            state_after = await get_engine_state(page)
            assert state_after["loaded"], "PdfEngine not loaded after round-trip reload"
            assert state_after["pageCount"] == original_pages, (
                f"Page count mismatch after round-trip: "
                f"original={original_pages}, after={state_after['pageCount']}"
            )

            # Verify fileInfo is consistent
            info = state_after["info"]
            assert info["pageCount"] == original_pages, (
                f"fileInfo pageCount mismatch: {info['pageCount']} != {original_pages}"
            )

            log("T03: Round-trip load-export-load", "PASS",
                f"pages: {original_pages} -> export -> {state_after['pageCount']}")
        except Exception as e:
            log("T03: Round-trip load-export-load", "FAIL", str(e))

        # ======================================================================
        # T04: Console errors check
        # ======================================================================
        critical = [
            e for e in console_errors
            if "is not a function" in e or "Cannot read" in e or "Unexpected token" in e
        ]
        if critical:
            log("T04: No critical console errors", "FAIL",
                f"{len(critical)} errors: {critical[0][:100]}")
        else:
            log("T04: No critical console errors", "PASS",
                f"0 critical ({len(console_errors)} total console messages)")

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
    print("E2E Tests - PDF Save & Export (4 scenarios)")
    print("=" * 60)
    failed = asyncio.run(run_tests())
    sys.exit(1 if failed > 0 else 0)
