"""
Playwright Monkey Test - PDF Workshop Pro
Tests all pages and core interactions with a real browser.
15 test scenarios covering the full user journey.
"""
import asyncio
import sys
from playwright.async_api import async_playwright

BASE_URL = "http://127.0.0.1:8765"
TEST_PDF = "/tmp/monkey_test.pdf"
RESULTS = []


def log(name, status, detail=""):
    icon = "OK" if status == "PASS" else "NG"
    RESULTS.append((name, status, detail))
    print(f"  [{icon}] {name}: {status} {detail}")


async def run_tests():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="ja-JP",
        )
        # Collect console errors
        console_errors = []

        page = await context.new_page()
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: console_errors.append(str(err)))

        # ===== Test 1: Home page loads =====
        try:
            resp = await page.goto(BASE_URL, wait_until="networkidle")
            assert resp.status == 200
            title = await page.title()
            assert "PDF Workshop Pro" in title
            log("T01: ホームページ読み込み", "PASS")
        except Exception as e:
            log("T01: ホームページ読み込み", "FAIL", str(e))

        # ===== Test 2: Home page is in Japanese =====
        try:
            content = await page.content()
            assert "ファイルを開く" in content or "PDFファイルを開く" in content
            assert "ブラウザ" in content
            log("T02: ホーム日本語UI", "PASS")
        except Exception as e:
            log("T02: ホーム日本語UI", "FAIL", str(e))

        # ===== Test 3: Privacy badge visible =====
        try:
            badge = page.locator("text=Local Processing")
            assert await badge.count() > 0
            log("T03: プライバシーバッジ", "PASS")
        except Exception as e:
            log("T03: プライバシーバッジ", "FAIL", str(e))

        # ===== Test 4: PDF file open =====
        try:
            file_input = page.locator('input[type="file"][accept=".pdf"]')
            await file_input.set_input_files(TEST_PDF)
            # Wait for navigation to editor
            await page.wait_for_url("**/editor**", timeout=15000)
            log("T04: PDFファイル読み込み", "PASS")
        except Exception as e:
            log("T04: PDFファイル読み込み", "FAIL", str(e))

        # ===== Test 5: Editor page loads with thumbnails =====
        try:
            await page.wait_for_timeout(3000)  # Wait for thumbnails to render
            grid = page.locator("#preview-grid")
            assert await grid.count() > 0
            # Check for page cards (img elements inside grid)
            images = page.locator("#preview-grid img")
            img_count = await images.count()
            assert img_count > 0, f"No thumbnails rendered, got {img_count}"
            log("T05: サムネイル表示", "PASS", f"{img_count}枚")
        except Exception as e:
            log("T05: サムネイル表示", "FAIL", str(e))

        # ===== Test 6: Editor UI is in Japanese =====
        try:
            content = await page.content()
            has_jp = any(w in content for w in ["ページ操作", "PDFエディタ", "最適化", "ダウンロード"])
            assert has_jp, "Japanese text not found in editor"
            log("T06: エディタ日本語UI", "PASS")
        except Exception as e:
            log("T06: エディタ日本語UI", "FAIL", str(e))

        # ===== Test 7: File info displayed =====
        try:
            file_info = page.locator("#file-info")
            info_text = await file_info.inner_text()
            assert "monkey_test.pdf" in info_text or "ページ" in info_text
            log("T07: ファイル情報表示", "PASS")
        except Exception as e:
            log("T07: ファイル情報表示", "FAIL", str(e))

        # ===== Test 8: Download button works =====
        try:
            download_btn = page.locator("button", has_text="ダウンロード")
            assert await download_btn.count() > 0
            log("T08: ダウンロードボタン", "PASS")
        except Exception as e:
            log("T08: ダウンロードボタン", "FAIL", str(e))

        # ===== Test 9: Merge page loads =====
        try:
            await page.goto(f"{BASE_URL}/merge", wait_until="networkidle")
            content = await page.content()
            assert "PDF結合" in content or "結合" in content
            log("T09: 結合ページ読み込み", "PASS")
        except Exception as e:
            log("T09: 結合ページ読み込み", "FAIL", str(e))

        # ===== Test 10: Merge page Japanese UI =====
        try:
            content = await page.content()
            has_jp = any(w in content for w in ["PDFファイルを選択", "結合", "ホームに戻る"])
            assert has_jp
            log("T10: 結合ページ日本語UI", "PASS")
        except Exception as e:
            log("T10: 結合ページ日本語UI", "FAIL", str(e))

        # ===== Test 11: AI Workshop page loads =====
        try:
            await page.goto(f"{BASE_URL}/ai-workshop?fileId=1", wait_until="networkidle")
            content = await page.content()
            assert "AIワークショップ" in content or "AIスライド" in content
            log("T11: AIワークショップ読み込み", "PASS")
        except Exception as e:
            log("T11: AIワークショップ読み込み", "FAIL", str(e))

        # ===== Test 12: AI Workshop Japanese UI =====
        try:
            content = await page.content()
            has_jp = any(w in content for w in ["Gemini APIキー", "対象ページ", "スライドを解析", "ブラウザ内"])
            assert has_jp
            log("T12: AI Workshop日本語UI", "PASS")
        except Exception as e:
            log("T12: AI Workshop日本語UI", "FAIL", str(e))

        # ===== Test 13: Area Replace page loads =====
        try:
            await page.goto(f"{BASE_URL}/area-replace?fileId=1", wait_until="networkidle")
            content = await page.content()
            assert "エリア" in content or "画像置換" in content
            log("T13: エリア置換ページ読み込み", "PASS")
        except Exception as e:
            log("T13: エリア置換ページ読み込み", "FAIL", str(e))

        # ===== Test 14: Health endpoint =====
        try:
            resp = await page.goto(f"{BASE_URL}/api/health")
            body = await page.inner_text("body")
            assert "healthy" in body
            assert "local-first" in body
            log("T14: ヘルスチェック", "PASS")
        except Exception as e:
            log("T14: ヘルスチェック", "FAIL", str(e))

        # ===== Test 15: 404 error page =====
        try:
            resp = await page.goto(f"{BASE_URL}/nonexistent-xyz")
            assert resp.status == 404
            content = await page.content()
            assert "404" in content
            log("T15: 404エラーページ", "PASS")
        except Exception as e:
            log("T15: 404エラーページ", "FAIL", str(e))

        # ===== Console errors check =====
        critical_errors = [e for e in console_errors if "renderPageToBlob" in e or "is not a function" in e or "WorkerMessageHandler" in e or "Cannot read properties" in e]
        if critical_errors:
            log("T00: コンソールエラー", "FAIL", f"{len(critical_errors)}件: {critical_errors[0][:100]}")
        else:
            log("T00: コンソールエラー", "PASS", f"重大エラーなし (通知{len(console_errors)}件)")

        await browser.close()

    # Summary
    print("\n" + "=" * 60)
    passed = sum(1 for _, s, _ in RESULTS if s == "PASS")
    failed = sum(1 for _, s, _ in RESULTS if s == "FAIL")
    print(f"結果: {passed} PASS / {failed} FAIL / {len(RESULTS)} TOTAL")
    if failed > 0:
        print("\n失敗テスト:")
        for name, status, detail in RESULTS:
            if status == "FAIL":
                print(f"  ✗ {name}: {detail}")
    print("=" * 60)
    return failed


if __name__ == "__main__":
    print("=" * 60)
    print("PDF Workshop Pro - Playwright Monkey Test (15 scenarios)")
    print("=" * 60)
    failed = asyncio.run(run_tests())
    sys.exit(1 if failed > 0 else 0)
