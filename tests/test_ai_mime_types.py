"""Test MIME type validation for AI vision-analyze endpoint."""
import struct
import zlib

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Minimal valid image bytes for each format
# ---------------------------------------------------------------------------

def _make_tiny_png() -> bytes:
    """Create a minimal valid 1x1 white PNG."""
    # IHDR
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr_crc = struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF)
    ihdr = struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + ihdr_crc

    # IDAT - single white pixel (filter byte 0 + RGB 0xFF 0xFF 0xFF)
    raw = zlib.compress(b"\x00\xff\xff\xff")
    idat_crc = struct.pack(">I", zlib.crc32(b"IDAT" + raw) & 0xFFFFFFFF)
    idat = struct.pack(">I", len(raw)) + b"IDAT" + raw + idat_crc

    # IEND
    iend_crc = struct.pack(">I", zlib.crc32(b"IEND") & 0xFFFFFFFF)
    iend = struct.pack(">I", 0) + b"IEND" + iend_crc

    return b"\x89PNG\r\n\x1a\n" + ihdr + idat + iend


TINY_PNG = _make_tiny_png()

# Minimal valid JPEG: SOI + APP0 marker + EOI
TINY_JPEG = bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"\x00" * 100 + bytes([0xFF, 0xD9])

# Minimal valid WebP container (RIFF + WEBP + VP8 chunk)
TINY_WEBP = b"RIFF" + struct.pack("<I", 100) + b"WEBP" + b"VP8 " + b"\x00" * 88

# GIF89a header
TINY_GIF = b"GIF89a" + b"\x00" * 100

# BMP header
TINY_BMP = b"BM" + b"\x00" * 100


# ---------------------------------------------------------------------------
# Tests: accepted MIME types (expect NOT 400)
# ---------------------------------------------------------------------------

async def test_vision_analyze_accepts_png(client: AsyncClient):
    """PNG (image/png) should be accepted -- not rejected with 400."""
    resp = await client.post(
        "/api/ai/vision-analyze",
        files={"image": ("test.png", TINY_PNG, "image/png")},
        data={"api_key": "test-key", "page_num": "1"},
    )
    # 500 is expected (no real Gemini key), but 400 means the format was rejected
    assert resp.status_code != 400, f"PNG should be accepted, got {resp.status_code}"


async def test_vision_analyze_accepts_jpeg(client: AsyncClient):
    """JPEG (image/jpeg) should be accepted -- not rejected with 400."""
    resp = await client.post(
        "/api/ai/vision-analyze",
        files={"image": ("test.jpg", TINY_JPEG, "image/jpeg")},
        data={"api_key": "test-key", "page_num": "1"},
    )
    assert resp.status_code != 400, f"JPEG should be accepted, got {resp.status_code}"


async def test_vision_analyze_accepts_webp(client: AsyncClient):
    """WebP (image/webp) should be accepted -- not rejected with 400."""
    resp = await client.post(
        "/api/ai/vision-analyze",
        files={"image": ("test.webp", TINY_WEBP, "image/webp")},
        data={"api_key": "test-key", "page_num": "1"},
    )
    assert resp.status_code != 400, f"WebP should be accepted, got {resp.status_code}"


# ---------------------------------------------------------------------------
# Tests: rejected MIME types (expect 400)
# ---------------------------------------------------------------------------

async def test_vision_analyze_rejects_gif(client: AsyncClient):
    """GIF (image/gif) should be rejected with 400."""
    resp = await client.post(
        "/api/ai/vision-analyze",
        files={"image": ("test.gif", TINY_GIF, "image/gif")},
        data={"api_key": "test-key", "page_num": "1"},
    )
    assert resp.status_code == 400


async def test_vision_analyze_rejects_bmp(client: AsyncClient):
    """BMP (image/bmp) should be rejected with 400."""
    resp = await client.post(
        "/api/ai/vision-analyze",
        files={"image": ("test.bmp", TINY_BMP, "image/bmp")},
        data={"api_key": "test-key", "page_num": "1"},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Tests: size limits
# ---------------------------------------------------------------------------

async def test_vision_analyze_size_limit_10mb(client: AsyncClient):
    """File larger than 10 MB should be rejected with 413."""
    oversized = TINY_PNG + b"\x00" * (10 * 1024 * 1024 + 1)
    resp = await client.post(
        "/api/ai/vision-analyze",
        files={"image": ("big.png", oversized, "image/png")},
        data={"api_key": "test-key", "page_num": "1"},
    )
    assert resp.status_code == 413


async def test_vision_analyze_under_limit(client: AsyncClient):
    """File under 10 MB should not be rejected with 413."""
    under_limit = TINY_PNG + b"\x00" * (1 * 1024 * 1024)
    resp = await client.post(
        "/api/ai/vision-analyze",
        files={"image": ("ok.png", under_limit, "image/png")},
        data={"api_key": "test-key", "page_num": "1"},
    )
    assert resp.status_code != 413, f"1MB file should not be rejected, got {resp.status_code}"
