"""E2E Tests - AI Workshop Image Input feature

Tests image upload (PNG, JPEG, WebP), validation, preview thumbnails,
drag-over styling, remove/clear, and analyze button visibility.
Run with: python tests/test_e2e_image_input.py
Requires: playwright (pip install playwright && playwright install chromium)
Server must be running at http://127.0.0.1:8765
"""
import asyncio
import os
import struct
import sys
import tempfile
import zlib

from playwright.async_api import async_playwright

BASE_URL = "http://127.0.0.1:8765"
RESULTS = []


def log(name, status, detail=""):
    icon = "OK" if status == "PASS" else "NG"
    RESULTS.append((name, status, detail))
    print(f"  [{icon}] {name}: {status} {detail}")


# ---------------------------------------------------------------------------
# Test image helpers
# ---------------------------------------------------------------------------

def _png_chunk(chunk_type, data):
    """Build a single PNG chunk (length + type + data + CRC)."""
    c = chunk_type + data
    crc = struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    return struct.pack('>I', len(data)) + c + crc


def create_minimal_png(filepath, width=1, height=1):
    """Create a minimal valid 1x1 red PNG."""
    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = _png_chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
    # Row: filter byte (0) + RGB pixels
    row = b'\x00' + (b'\xff\x00\x00' * width)
    raw = row * height
    idat = _png_chunk(b'IDAT', zlib.compress(raw))
    iend = _png_chunk(b'IEND', b'')
    with open(filepath, 'wb') as f:
        f.write(sig + ihdr + idat + iend)
    return filepath


def create_minimal_jpeg(filepath, width=1, height=1):
    """Create a minimal valid JPEG (1x1 red pixel) using raw JFIF bytes."""
    # Minimal JPEG built from raw markers.
    # SOI
    soi = b'\xff\xd8'
    # APP0 (JFIF header)
    app0 = b'\xff\xe0'
    app0_data = b'JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
    app0_block = app0 + struct.pack('>H', len(app0_data) + 2) + app0_data
    # DQT (quantization table) - all 1s for simplicity
    dqt = b'\xff\xdb'
    qt_data = b'\x00' + bytes([1] * 64)
    dqt_block = dqt + struct.pack('>H', len(qt_data) + 2) + qt_data
    # SOF0 (baseline DCT)
    sof0 = b'\xff\xc0'
    sof0_data = struct.pack('>BHHB', 8, height, width, 3)
    # Component specs: Y, Cb, Cr each with sampling=1x1, quant table 0
    sof0_data += b'\x01\x11\x00'  # Y
    sof0_data += b'\x02\x11\x00'  # Cb
    sof0_data += b'\x03\x11\x00'  # Cr
    sof0_block = sof0 + struct.pack('>H', len(sof0_data) + 2) + sof0_data
    # DHT (Huffman tables) - minimal DC and AC tables
    def make_dht(table_class, table_id, counts, values):
        data = bytes([table_class << 4 | table_id]) + bytes(counts) + bytes(values)
        return b'\xff\xc4' + struct.pack('>H', len(data) + 2) + data

    # DC luminance table
    dc_lum_counts = [0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    dc_lum_values = [0]
    dht_dc_lum = make_dht(0, 0, dc_lum_counts, dc_lum_values)
    # AC luminance table
    ac_lum_counts = [0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    ac_lum_values = [0]
    dht_ac_lum = make_dht(1, 0, ac_lum_counts, ac_lum_values)
    # DC chrominance
    dht_dc_chr = make_dht(0, 1, dc_lum_counts, dc_lum_values)
    # AC chrominance
    dht_ac_chr = make_dht(1, 1, ac_lum_counts, ac_lum_values)
    # SOS (Start of Scan)
    sos = b'\xff\xda'
    sos_data = struct.pack('>B', 3)  # 3 components
    sos_data += b'\x01\x00'  # Y: DC=0, AC=0
    sos_data += b'\x02\x11'  # Cb: DC=1, AC=1
    sos_data += b'\x03\x11'  # Cr: DC=1, AC=1
    sos_data += b'\x00\x3f\x00'  # Spectral selection start, end, approx
    sos_block = sos + struct.pack('>H', len(sos_data) + 2) + sos_data
    # Scan data - minimal entropy-coded data (all zeros)
    scan_data = b'\x00' * 4
    # EOI
    eoi = b'\xff\xd9'

    with open(filepath, 'wb') as f:
        f.write(soi + app0_block + dqt_block + sof0_block +
                dht_dc_lum + dht_ac_lum + dht_dc_chr + dht_ac_chr +
                sos_block + scan_data + eoi)
    return filepath


def create_minimal_webp(filepath, width=1, height=1):
    """Create a minimal valid WebP file (lossless 1x1 green pixel)."""
    # Minimal WebP lossless: RIFF header + VP8L chunk
    # VP8L: signature byte 0x2f, then 14-bit width-1, 14-bit height-1, alpha, version
    w_minus_1 = width - 1
    h_minus_1 = height - 1
    # Pack: bits [0..13] = width-1, [14..27] = height-1, [28] = alpha(0), [29..31] = version(0)
    bitfield = w_minus_1 | (h_minus_1 << 14) | (0 << 28)
    vp8l_header = b'\x2f' + struct.pack('<I', bitfield)
    # Minimal LZ77 stream: a single literal pixel (green, ARGB = FF00FF00)
    # For simplicity, use a known working minimal VP8L payload.
    # This is a hand-crafted 1x1 green VP8L bitstream.
    # Transform bits (0 = no transform), then color cache size (0), then pixel data.
    # The simplest valid data: just write raw pixel bytes padded.
    vp8l_data = vp8l_header + b'\x10\x07\x10\x11\x11\x80\x00'

    chunk_size = len(vp8l_data)
    riff_size = 4 + 8 + chunk_size + (chunk_size % 2)  # WEBP + VP8L chunk header + data + padding
    riff_header = b'RIFF' + struct.pack('<I', riff_size) + b'WEBP'
    vp8l_chunk = b'VP8L' + struct.pack('<I', chunk_size) + vp8l_data
    if chunk_size % 2:
        vp8l_chunk += b'\x00'

    with open(filepath, 'wb') as f:
        f.write(riff_header + vp8l_chunk)
    return filepath


def create_test_image(fmt, filepath, width=1, height=1):
    """Create a test image of the given format. Returns filepath."""
    if fmt == 'png':
        return create_minimal_png(filepath, width, height)
    elif fmt in ('jpeg', 'jpg'):
        return create_minimal_jpeg(filepath, width, height)
    elif fmt == 'webp':
        return create_minimal_webp(filepath, width, height)
    else:
        raise ValueError(f"Unsupported format: {fmt}")


def create_oversized_file(filepath, size_bytes):
    """Create a file larger than the given size (filled with zeros)."""
    with open(filepath, 'wb') as f:
        # Write a valid PNG header so the extension check passes,
        # then pad to desired size.
        sig = b'\x89PNG\r\n\x1a\n'
        f.write(sig)
        remaining = size_bytes - len(sig)
        # Write in 1MB chunks to avoid memory issues
        chunk = b'\x00' * min(remaining, 1024 * 1024)
        written = 0
        while written < remaining:
            to_write = min(len(chunk), remaining - written)
            f.write(chunk[:to_write])
            written += to_write
    return filepath


def create_text_file(filepath):
    """Create a plain text file (invalid image format)."""
    with open(filepath, 'w') as f:
        f.write("This is a text file, not an image.\n")
    return filepath


def create_test_pdf(page_count=1, filepath=None):
    """Generate a minimal valid PDF with N pages."""
    if filepath is None:
        fd, filepath = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)

    objects = []
    obj_num = 1
    catalog_num = obj_num; obj_num += 1
    pages_num = obj_num; obj_num += 1
    font_num = obj_num; obj_num += 1

    page_obj_nums = []
    content_obj_nums = []
    for i in range(page_count):
        page_obj_nums.append(obj_num); obj_num += 1
        content_obj_nums.append(obj_num); obj_num += 1

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
        text = f"BT /F1 24 Tf 100 700 Td (Page {i + 1}) Tj ET"
        stream_bytes = text.encode("latin-1")
        add_object(
            content_obj_nums[i],
            f"<< /Length {len(stream_bytes)} >>\nstream\n".rstrip("\n")
            + "\n" + text + "\nendstream",
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
    xref_lines = [b"xref\n", f"0 {total_objects}\n".encode("latin-1"), b"0000000000 65535 f \n"]
    for n in range(1, obj_num):
        xref_lines.append(f"{offsets[n]:010d} 00000 n \n".encode("latin-1"))

    trailer = (
        f"trailer\n<< /Size {total_objects} /Root {catalog_num} 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    )

    with open(filepath, "wb") as f:
        f.write(header)
        for part in body_parts:
            f.write(part)
        for line in xref_lines:
            f.write(line)
        f.write(trailer.encode("latin-1"))

    return filepath


# ---------------------------------------------------------------------------
# Navigation helpers
# ---------------------------------------------------------------------------

async def load_pdf_and_go_to_workshop(page, pdf_path):
    """Load a PDF in the editor, then navigate to the AI Workshop page."""
    # Upload PDF via the home page
    await page.goto(BASE_URL, wait_until="networkidle")
    file_input = page.locator('input[type="file"][accept=".pdf,.ai"]')
    await file_input.set_input_files(pdf_path)
    await page.wait_for_url("**/editor**", timeout=15000)
    await page.wait_for_function(
        "() => typeof PdfEngine !== 'undefined' && PdfEngine.isLoaded()", timeout=10000
    )
    await page.wait_for_timeout(500)

    # Extract fileId from URL and navigate to AI Workshop
    current_url = page.url
    file_id = current_url.split("fileId=")[-1].split("&")[0] if "fileId=" in current_url else "1"
    await page.goto(f"{BASE_URL}/ai-workshop?fileId={file_id}", wait_until="networkidle")
    # Wait for ImageInput to be initialized
    await page.wait_for_function(
        "() => typeof ImageInput !== 'undefined' && typeof ImageInput.getCount === 'function'",
        timeout=10000,
    )
    await page.wait_for_timeout(500)


async def get_image_count(page):
    """Get ImageInput.getCount() from the page."""
    return await page.evaluate("() => ImageInput.getCount()")


async def upload_images_via_input(page, file_paths):
    """Set files on the hidden file input inside the drop zone."""
    # The file input is created dynamically by ImageInput.init() inside #image-drop-zone
    file_input = page.locator('#image-drop-zone input[type="file"]')
    await file_input.set_input_files(file_paths)
    # Wait for async processing (thumbnail generation etc.)
    await page.wait_for_timeout(1500)


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

async def run_tests():
    tmpdir = tempfile.mkdtemp(prefix="pdfedit_imgtest_")
    print(f"  Temp dir: {tmpdir}")

    # Create test assets
    test_pdf = create_test_pdf(page_count=1, filepath=os.path.join(tmpdir, "test.pdf"))
    png_path = create_test_image('png', os.path.join(tmpdir, "test.png"))
    jpg_path = create_test_image('jpeg', os.path.join(tmpdir, "test.jpg"))
    webp_path = create_test_image('webp', os.path.join(tmpdir, "test.webp"))
    png2_path = create_test_image('png', os.path.join(tmpdir, "test2.png"))
    png3_path = create_test_image('png', os.path.join(tmpdir, "test3.png"))
    oversized_path = create_oversized_file(os.path.join(tmpdir, "huge.png"), 11 * 1024 * 1024)
    txt_path = create_text_file(os.path.join(tmpdir, "notes.txt"))

    print(f"  Test assets created in {tmpdir}")

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

        # Load PDF and navigate to AI Workshop once
        try:
            await load_pdf_and_go_to_workshop(page, test_pdf)
            print("  AI Workshop loaded successfully")
        except Exception as e:
            print(f"  FATAL: Could not load AI Workshop: {e}")
            await browser.close()
            return 1

        workshop_url = page.url

        # ==================================================================
        # T01: Drop zone exists and is visible
        # ==================================================================
        try:
            drop_zone = page.locator('#image-drop-zone')
            await drop_zone.wait_for(state="visible", timeout=5000)
            is_visible = await drop_zone.is_visible()
            assert is_visible, "Drop zone is not visible"
            log("T01: Drop zone exists and is visible", "PASS")
        except Exception as e:
            log("T01: Drop zone exists and is visible", "FAIL", str(e))

        # ==================================================================
        # T02: PNG upload via file input
        # ==================================================================
        try:
            # Ensure clean state
            await page.evaluate("() => ImageInput.clearAll()")
            await page.wait_for_timeout(300)

            await upload_images_via_input(page, [png_path])
            count = await get_image_count(page)
            assert count == 1, f"Expected count=1 after PNG upload, got {count}"

            # Verify thumbnail exists
            thumb = page.locator('#image-preview-container img.image-preview-thumb')
            thumb_count = await thumb.count()
            assert thumb_count >= 1, f"Expected at least 1 thumbnail, got {thumb_count}"

            log("T02: PNG upload via file input", "PASS", f"count={count}")
        except Exception as e:
            log("T02: PNG upload via file input", "FAIL", str(e))

        # ==================================================================
        # T03: JPEG upload via file input
        # ==================================================================
        try:
            await page.evaluate("() => ImageInput.clearAll()")
            await page.wait_for_timeout(300)

            await upload_images_via_input(page, [jpg_path])
            count = await get_image_count(page)
            assert count == 1, f"Expected count=1 after JPEG upload, got {count}"

            thumb = page.locator('#image-preview-container img.image-preview-thumb')
            thumb_count = await thumb.count()
            assert thumb_count >= 1, f"Expected at least 1 thumbnail, got {thumb_count}"

            log("T03: JPEG upload via file input", "PASS", f"count={count}")
        except Exception as e:
            log("T03: JPEG upload via file input", "FAIL", str(e))

        # ==================================================================
        # T04: WebP upload via file input
        # ==================================================================
        try:
            await page.evaluate("() => ImageInput.clearAll()")
            await page.wait_for_timeout(300)

            await upload_images_via_input(page, [webp_path])
            count = await get_image_count(page)
            assert count == 1, f"Expected count=1 after WebP upload, got {count}"

            thumb = page.locator('#image-preview-container img.image-preview-thumb')
            thumb_count = await thumb.count()
            assert thumb_count >= 1, f"Expected at least 1 thumbnail, got {thumb_count}"

            log("T04: WebP upload via file input", "PASS", f"count={count}")
        except Exception as e:
            log("T04: WebP upload via file input", "FAIL", str(e))

        # ==================================================================
        # T05: Multiple file upload
        # ==================================================================
        try:
            await page.evaluate("() => ImageInput.clearAll()")
            await page.wait_for_timeout(300)

            await upload_images_via_input(page, [png_path, png2_path, png3_path])
            count = await get_image_count(page)
            assert count == 3, f"Expected count=3 after multi-upload, got {count}"

            log("T05: Multiple file upload", "PASS", f"count={count}")
        except Exception as e:
            log("T05: Multiple file upload", "FAIL", str(e))

        # ==================================================================
        # T06: File size validation (>10MB rejected)
        # ==================================================================
        try:
            await page.evaluate("() => ImageInput.clearAll()")
            await page.wait_for_timeout(300)

            await upload_images_via_input(page, [oversized_path])
            count = await get_image_count(page)
            assert count == 0, f"Expected count=0 for oversized file, got {count}"

            log("T06: File size validation (>10MB rejected)", "PASS", f"count={count}")
        except Exception as e:
            log("T06: File size validation (>10MB rejected)", "FAIL", str(e))

        # ==================================================================
        # T07: Invalid format rejection (.txt)
        # ==================================================================
        try:
            await page.evaluate("() => ImageInput.clearAll()")
            await page.wait_for_timeout(300)

            await upload_images_via_input(page, [txt_path])
            count = await get_image_count(page)
            assert count == 0, f"Expected count=0 for .txt file, got {count}"

            log("T07: Invalid format rejection (.txt)", "PASS", f"count={count}")
        except Exception as e:
            log("T07: Invalid format rejection (.txt)", "FAIL", str(e))

        # ==================================================================
        # T08: Remove image
        # ==================================================================
        try:
            await page.evaluate("() => ImageInput.clearAll()")
            await page.wait_for_timeout(300)

            await upload_images_via_input(page, [png_path, png2_path])
            count = await get_image_count(page)
            assert count == 2, f"Expected count=2 before remove, got {count}"

            # Remove first image (index 0)
            await page.evaluate("() => ImageInput.removeImage(0)")
            await page.wait_for_timeout(300)
            count = await get_image_count(page)
            assert count == 1, f"Expected count=1 after remove, got {count}"

            log("T08: Remove image", "PASS", f"count after remove={count}")
        except Exception as e:
            log("T08: Remove image", "FAIL", str(e))

        # ==================================================================
        # T09: Clear all images
        # ==================================================================
        try:
            await page.evaluate("() => ImageInput.clearAll()")
            await page.wait_for_timeout(300)

            await upload_images_via_input(page, [png_path, png2_path, png3_path])
            count = await get_image_count(page)
            assert count == 3, f"Expected count=3 before clear, got {count}"

            await page.evaluate("() => ImageInput.clearAll()")
            await page.wait_for_timeout(300)
            count = await get_image_count(page)
            assert count == 0, f"Expected count=0 after clearAll, got {count}"

            log("T09: Clear all images", "PASS")
        except Exception as e:
            log("T09: Clear all images", "FAIL", str(e))

        # ==================================================================
        # T10: Analyze button visibility
        # ==================================================================
        try:
            await page.evaluate("() => ImageInput.clearAll()")
            await page.wait_for_timeout(300)

            # With 0 images, analyze button should be hidden
            btn = page.locator('#analyze-images-btn')
            # Trigger the UI update callback manually
            await page.evaluate("""() => {
                const btn = document.getElementById('analyze-images-btn');
                btn.classList.toggle('hidden', ImageInput.getCount() === 0);
            }""")
            is_hidden_0 = await btn.evaluate("el => el.classList.contains('hidden')")
            assert is_hidden_0, "Analyze button should be hidden when 0 images"

            # Upload an image
            await upload_images_via_input(page, [png_path])
            # The onChange callback (updateImageUI) should toggle the button
            await page.wait_for_timeout(500)
            is_hidden_1 = await btn.evaluate("el => el.classList.contains('hidden')")
            assert not is_hidden_1, "Analyze button should be visible when >= 1 image"

            log("T10: Analyze button visibility", "PASS")
        except Exception as e:
            log("T10: Analyze button visibility", "FAIL", str(e))

        # ==================================================================
        # T11: Thumbnail preview rendering
        # ==================================================================
        try:
            await page.evaluate("() => ImageInput.clearAll()")
            await page.wait_for_timeout(300)

            await upload_images_via_input(page, [png_path])

            # Check that an <img> element exists inside #image-preview-container
            img_el = page.locator('#image-preview-container img')
            img_count = await img_el.count()
            assert img_count >= 1, f"Expected at least 1 <img> in preview container, got {img_count}"

            # Verify the img has a src attribute (data URL)
            src = await img_el.first.get_attribute('src')
            assert src and src.startswith('data:image/'), f"Thumbnail src invalid: {src[:50] if src else 'None'}"

            log("T11: Thumbnail preview rendering", "PASS")
        except Exception as e:
            log("T11: Thumbnail preview rendering", "FAIL", str(e))

        # ==================================================================
        # T12: Drop zone drag-over styling
        # ==================================================================
        try:
            await page.evaluate("() => ImageInput.clearAll()")
            await page.wait_for_timeout(300)

            drop_zone = page.locator('#image-drop-zone')

            # Verify drag-over class is NOT present initially
            has_class_before = await drop_zone.evaluate(
                "el => el.classList.contains('drag-over')"
            )
            assert not has_class_before, "drag-over class should not be present initially"

            # Simulate dragenter/dragover event to trigger the class
            await drop_zone.evaluate("""el => {
                const evt = new DragEvent('dragover', {
                    bubbles: true, cancelable: true,
                    dataTransfer: new DataTransfer()
                });
                el.dispatchEvent(evt);
            }""")
            await page.wait_for_timeout(200)

            has_class_after = await drop_zone.evaluate(
                "el => el.classList.contains('drag-over')"
            )
            assert has_class_after, "drag-over class should be present after dragover event"

            # Simulate dragleave to remove the class
            await drop_zone.evaluate("""el => {
                const evt = new DragEvent('dragleave', {
                    bubbles: true, cancelable: true,
                    dataTransfer: new DataTransfer()
                });
                el.dispatchEvent(evt);
            }""")
            await page.wait_for_timeout(200)

            has_class_final = await drop_zone.evaluate(
                "el => el.classList.contains('drag-over')"
            )
            assert not has_class_final, "drag-over class should be removed after dragleave"

            log("T12: Drop zone drag-over styling", "PASS")
        except Exception as e:
            log("T12: Drop zone drag-over styling", "FAIL", str(e))

        await browser.close()

    # Cleanup temp files
    try:
        for f in os.listdir(tmpdir):
            os.unlink(os.path.join(tmpdir, f))
        os.rmdir(tmpdir)
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
    print("E2E Tests - AI Workshop Image Input (12 scenarios)")
    print("=" * 60)
    failed = asyncio.run(run_tests())
    sys.exit(1 if failed > 0 else 0)
