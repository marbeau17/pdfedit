"""
E2E Test - Branding & Export
Tests that after applying branding (page numbers, footer) and text overlays,
the PDF can be exported successfully with valid content.
"""
import asyncio
import struct
import sys
import zlib
from playwright.async_api import async_playwright

BASE_URL = "http://127.0.0.1:8765"
RESULTS = []


def log(name, status, detail=""):
    icon = "OK" if status == "PASS" else "NG"
    RESULTS.append((name, status, detail))
    print(f"  [{icon}] {name}: {status} {detail}")


def create_minimal_3page_pdf() -> bytes:
    """Create a minimal valid 3-page PDF entirely in Python (no external deps)."""
    # Build a simple PDF with 3 blank A4 pages using raw PDF syntax.
    objects = []

    # obj 1: Catalog
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj")
    # obj 2: Pages
    objects.append(
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R 4 0 R 5 0 R] /Count 3 >>\nendobj"
    )
    # obj 3,4,5: Page objects (A4: 595x842)
    for i in range(3):
        obj_num = 3 + i
        objects.append(
            f"{obj_num} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >>\nendobj".encode()
        )

    body = b"\n".join(objects)
    header = b"%PDF-1.4\n"

    # Calculate offsets
    offsets = []
    pos = len(header)
    for obj in objects:
        offsets.append(pos)
        pos += len(obj) + 1  # +1 for newline between objects

    xref_offset = len(header) + len(body) + 1
    xref = b"xref\n"
    xref += f"0 {len(objects) + 1}\n".encode()
    xref += b"0000000000 65535 f \n"
    for off in offsets:
        xref += f"{off:010d} 00000 n \n".encode()

    trailer = f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode()
    trailer += f"startxref\n{xref_offset}\n%%EOF".encode()

    return header + body + b"\n" + xref + trailer


def create_1x1_png() -> bytes:
    """Create a minimal 1x1 red PNG image for logo testing."""
    # IHDR
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr_crc = struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF)
    ihdr = struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + ihdr_crc

    # IDAT (1x1 RGB red pixel)
    raw = b"\x00\xff\x00\x00"  # filter byte + RGB
    compressed = zlib.compress(raw)
    idat_crc = struct.pack(">I", zlib.crc32(b"IDAT" + compressed) & 0xFFFFFFFF)
    idat = struct.pack(">I", len(compressed)) + b"IDAT" + compressed + idat_crc

    # IEND
    iend_crc = struct.pack(">I", zlib.crc32(b"IEND") & 0xFFFFFFFF)
    iend = struct.pack(">I", 0) + b"IEND" + iend_crc

    return b"\x89PNG\r\n\x1a\n" + ihdr + idat + iend


async def load_pdf_in_editor(page, pdf_bytes: bytes):
    """Load PDF bytes directly into PdfEngine via page.evaluate, bypassing file upload."""
    # Navigate to editor page
    await page.goto(f"{BASE_URL}/editor?fileId=0", wait_until="domcontentloaded")

    # Wait for PdfEngine to be available
    await page.wait_for_function(
        "typeof PdfEngine !== 'undefined' && typeof PdfEngine.loadFromBytes === 'function'",
        timeout=15000,
    )

    # Convert bytes to list for JSON transfer, then load into PdfEngine
    byte_list = list(pdf_bytes)
    await page.evaluate(
        """(byteArray) => {
            const bytes = new Uint8Array(byteArray);
            return PdfEngine.loadFromBytes(bytes, 'test.pdf');
        }""",
        byte_list,
    )

    # Wait for pages to be loaded
    await page.wait_for_function("PdfEngine.getPageCount() > 0", timeout=10000)


async def get_exported_bytes(page) -> dict:
    """Export PDF and return info about the exported bytes."""
    result = await page.evaluate(
        """() => {
            const bytes = PdfEngine.getCurrentBytes();
            if (!bytes || bytes.length === 0) return null;
            // Check PDF header
            const header = String.fromCharCode(bytes[0], bytes[1], bytes[2], bytes[3], bytes[4]);
            return {
                size: bytes.length,
                isPdf: header === '%PDF-',
                pageCount: PdfEngine.getPageCount()
            };
        }"""
    )
    return result


async def run_tests():
    pdf_bytes = create_minimal_3page_pdf()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="ja-JP",
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

        # ===== T01: Add branding then export =====
        try:
            await load_pdf_in_editor(page, pdf_bytes)

            # Get original size
            original = await get_exported_bytes(page)
            assert original is not None, "Failed to get original PDF info"
            original_size = original["size"]
            assert original["pageCount"] == 3, f"Expected 3 pages, got {original['pageCount']}"

            # Add branding with page numbers and footer (no logo)
            await page.evaluate(
                """() => PdfEngine.addBranding({
                    enablePageNum: true,
                    enableLogo: false,
                    skipFirstPageNum: false,
                    footerText: 'Test Footer',
                    copyrightText: 'Test Copyright'
                })"""
            )

            # Export and verify
            exported = await get_exported_bytes(page)
            assert exported is not None, "Failed to export after branding"
            assert exported["isPdf"], "Exported data is not a valid PDF"
            assert exported["pageCount"] == 3, f"Expected 3 pages after branding, got {exported['pageCount']}"
            assert exported["size"] > original_size, (
                f"File size should increase after branding: {exported['size']} <= {original_size}"
            )
            log("T01: Add branding then export", "PASS", f"size {original_size} -> {exported['size']}")
        except Exception as e:
            log("T01: Add branding then export", "FAIL", str(e))

        # ===== T02: Add text overlay then export =====
        try:
            await load_pdf_in_editor(page, pdf_bytes)

            # Add text to page 1
            await page.evaluate(
                """() => PdfEngine.addText(1, 'Hello World', 100, 400, 24, {r: 0, g: 0, b: 0})"""
            )

            exported = await get_exported_bytes(page)
            assert exported is not None, "Failed to export after addText"
            assert exported["isPdf"], "Exported data is not a valid PDF"
            assert exported["pageCount"] == 3, f"Expected 3 pages, got {exported['pageCount']}"
            log("T02: Add text overlay then export", "PASS")
        except Exception as e:
            log("T02: Add text overlay then export", "FAIL", str(e))

        # ===== T03: Add branding with skipFirstPageNum then export =====
        try:
            await load_pdf_in_editor(page, pdf_bytes)

            await page.evaluate(
                """() => PdfEngine.addBranding({
                    enablePageNum: true,
                    enableLogo: false,
                    skipFirstPageNum: true,
                    footerText: 'Confidential',
                    copyrightText: '2026 Test'
                })"""
            )

            exported = await get_exported_bytes(page)
            assert exported is not None, "Failed to export after branding with skipFirst"
            assert exported["isPdf"], "Exported data is not a valid PDF"
            assert exported["pageCount"] == 3, f"Expected 3 pages, got {exported['pageCount']}"
            log("T03: Branding skipFirstPageNum then export", "PASS")
        except Exception as e:
            log("T03: Branding skipFirstPageNum then export", "FAIL", str(e))

        # ===== T04: Add branding, delete page, then export =====
        try:
            await load_pdf_in_editor(page, pdf_bytes)

            # Add branding first
            await page.evaluate(
                """() => PdfEngine.addBranding({
                    enablePageNum: true,
                    enableLogo: false,
                    skipFirstPageNum: false,
                    footerText: 'Test Footer',
                    copyrightText: 'Test Copyright'
                })"""
            )

            # Verify 3 pages before delete
            count_before = await page.evaluate("() => PdfEngine.getPageCount()")
            assert count_before == 3, f"Expected 3 pages before delete, got {count_before}"

            # Delete page 2
            new_count = await page.evaluate("() => PdfEngine.removePages([2])")
            assert new_count == 2, f"Expected 2 pages after delete, got {new_count}"

            # Export and verify
            exported = await get_exported_bytes(page)
            assert exported is not None, "Failed to export after branding + delete"
            assert exported["isPdf"], "Exported data is not a valid PDF"
            assert exported["pageCount"] == 2, f"Expected 2 pages, got {exported['pageCount']}"
            log("T04: Branding then delete then export", "PASS")
        except Exception as e:
            log("T04: Branding then delete then export", "FAIL", str(e))

        # ===== T05: Multiple text overlays then export =====
        try:
            await load_pdf_in_editor(page, pdf_bytes)

            original = await get_exported_bytes(page)
            original_size = original["size"]

            # Add text to every page
            await page.evaluate(
                """async () => {
                    const count = PdfEngine.getPageCount();
                    for (let i = 1; i <= count; i++) {
                        await PdfEngine.addText(
                            i,
                            'Overlay on page ' + i,
                            50, 700, 18,
                            {r: 0.2, g: 0.2, b: 0.8}
                        );
                    }
                }"""
            )

            exported = await get_exported_bytes(page)
            assert exported is not None, "Failed to export after multiple text overlays"
            assert exported["isPdf"], "Exported data is not a valid PDF"
            assert exported["pageCount"] == 3, f"Expected 3 pages, got {exported['pageCount']}"
            assert exported["size"] > original_size, (
                f"File size should increase after text overlays: {exported['size']} <= {original_size}"
            )
            log(
                "T05: Multiple text overlays then export",
                "PASS",
                f"size {original_size} -> {exported['size']}",
            )
        except Exception as e:
            log("T05: Multiple text overlays then export", "FAIL", str(e))

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
    print("E2E Test - Branding & Export (5 scenarios)")
    print("=" * 60)
    failed = asyncio.run(run_tests())
    sys.exit(1 if failed > 0 else 0)
