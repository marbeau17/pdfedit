"""
E2E + Monkey Test - Structured XML Editor
Tests the AI Workshop structured editor, tab switching, and XML round-trip.
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
        context = await browser.new_context(viewport={"width": 1400, "height": 900}, locale="ja-JP")
        console_errors = []

        page = await context.new_page()
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: console_errors.append(str(err)))

        # === T01: Open PDF and navigate to editor ===
        try:
            await page.goto(BASE_URL, wait_until="networkidle")
            file_input = page.locator('input[type="file"][accept=".pdf"]')
            await file_input.set_input_files(TEST_PDF)
            await page.wait_for_url("**/editor**", timeout=15000)
            await page.wait_for_timeout(2000)
            log("T01: PDF読み込み→エディタ", "PASS")
        except Exception as e:
            log("T01: PDF読み込み→エディタ", "FAIL", str(e))

        # === T02: Navigate to AI Workshop ===
        try:
            ai_link = page.locator("a[href*='ai-workshop']")
            if await ai_link.count() > 0:
                await ai_link.first.click()
            else:
                file_id = page.url.split("fileId=")[1] if "fileId=" in page.url else "1"
                await page.goto(f"{BASE_URL}/ai-workshop?fileId={file_id}")
            await page.wait_for_load_state("networkidle")
            content = await page.content()
            assert "AIワークショップ" in content or "AIスライド" in content
            log("T02: AIワークショップ遷移", "PASS")
        except Exception as e:
            log("T02: AIワークショップ遷移", "FAIL", str(e))

        # === T03: Check Japanese UI ===
        try:
            content = await page.content()
            jp_elements = ["Gemini APIキー", "対象ページ", "スライドを解析", "構造化"]
            found = [el for el in jp_elements if el in content]
            assert len(found) >= 2, f"Found only: {found}"
            log("T03: 日本語UI確認", "PASS", f"{len(found)}/{len(jp_elements)}")
        except Exception as e:
            log("T03: 日本語UI確認", "FAIL", str(e))

        # === T04: xml-editor.js loaded ===
        try:
            result = await page.evaluate("typeof XmlEditor !== 'undefined'")
            assert result, "XmlEditor not found"
            log("T04: XmlEditor読み込み", "PASS")
        except Exception as e:
            log("T04: XmlEditor読み込み", "FAIL", str(e))

        # === T05: XmlEditor.parseXml works ===
        try:
            result = await page.evaluate("""
                (() => {
                    const xml = '<slide><title font-size="28">Test</title><subtitle font-size="18">Sub</subtitle><content><section name="S1"><bullet font-size="14">B1</bullet></section></content><charts font-size="12">Chart</charts><images>Img</images><layout>Layout</layout><color_scheme>Colors</color_scheme><notes font-size="10">Note</notes></slide>';
                    const data = XmlEditor.parseXml(xml);
                    return JSON.stringify({
                        title: data.title,
                        titleFs: data.titleFontSize,
                        subtitle: data.subtitle,
                        sectionCount: data.sections.length,
                        bulletCount: data.sections[0]?.bullets.length,
                        charts: data.charts
                    });
                })()
            """)
            import json
            parsed = json.loads(result)
            assert parsed["title"] == "Test"
            assert parsed["titleFs"] == 28
            assert parsed["sectionCount"] == 1
            assert parsed["bulletCount"] == 1
            log("T05: parseXml動作確認", "PASS")
        except Exception as e:
            log("T05: parseXml動作確認", "FAIL", str(e))

        # === T06: XmlEditor.collectToXml round-trip ===
        try:
            result = await page.evaluate("""
                (() => {
                    const xml = '<slide><title font-size="28">Hello</title><subtitle font-size="18">World</subtitle><content><section name="Sec"><bullet font-size="14">Item1</bullet><bullet font-size="12">Item2</bullet></section></content><charts font-size="12">C</charts><images>I</images><layout>L</layout><color_scheme>CS</color_scheme><notes font-size="10">N</notes></slide>';
                    const data = XmlEditor.parseXml(xml);

                    // Create temp container
                    const container = document.createElement('div');
                    container.id = 'test-editor-99';
                    document.body.appendChild(container);

                    XmlEditor.renderEditor(data, 'test-editor-99', 99);
                    const resultXml = XmlEditor.collectToXml('test-editor-99', 99);

                    document.body.removeChild(container);
                    return resultXml;
                })()
            """)
            assert "<slide>" in result
            assert "<title" in result
            assert "Hello" in result
            assert "<bullet" in result
            assert "Item1" in result
            assert "font-size" in result
            log("T06: XML往復テスト", "PASS")
        except Exception as e:
            log("T06: XML往復テスト", "FAIL", str(e))

        # === T07: XmlEditor.extractXmlFromResponse ===
        try:
            result = await page.evaluate("""
                (() => {
                    const raw = '```xml\\n<slide><title>Test</title></slide>\\n```';
                    return XmlEditor.extractXmlFromResponse(raw);
                })()
            """)
            assert "<slide>" in result
            assert "```" not in result
            log("T07: extractXml動作確認", "PASS")
        except Exception as e:
            log("T07: extractXml動作確認", "FAIL", str(e))

        # === T08: renderEditor creates form fields ===
        try:
            count = await page.evaluate("""
                (() => {
                    const xml = '<slide><title font-size="28">T</title><subtitle font-size="18">S</subtitle><content><section name="A"><bullet font-size="14">B</bullet></section></content><charts>C</charts><images>I</images><layout>L</layout><color_scheme>CS</color_scheme><notes>N</notes></slide>';
                    const data = XmlEditor.parseXml(xml);
                    const container = document.createElement('div');
                    container.id = 'test-render-check';
                    document.body.appendChild(container);
                    XmlEditor.renderEditor(data, 'test-render-check', 88);
                    const inputs = container.querySelectorAll('input, textarea, select').length;
                    document.body.removeChild(container);
                    return inputs;
                })()
            """)
            assert count >= 8, f"Expected 8+ form elements, got {count}"
            log("T08: フォーム要素生成", "PASS", f"{count}要素")
        except Exception as e:
            log("T08: フォーム要素生成", "FAIL", str(e))

        # === T09: Font size defaults ===
        try:
            result = await page.evaluate("""
                (() => {
                    const xml = '<slide><title>NoFS</title><subtitle>NoFS</subtitle><content></content><charts>C</charts><images>I</images><layout>L</layout><color_scheme>CS</color_scheme><notes>N</notes></slide>';
                    const data = XmlEditor.parseXml(xml);
                    return JSON.stringify({
                        titleFs: data.titleFontSize,
                        subtitleFs: data.subtitleFontSize,
                        chartsFs: data.chartsFontSize,
                        notesFs: data.notesFontSize
                    });
                })()
            """)
            import json
            defaults = json.loads(result)
            assert defaults["titleFs"] == 36
            assert defaults["subtitleFs"] == 24
            assert defaults["chartsFs"] == 12
            assert defaults["notesFs"] == 9
            log("T09: デフォルトフォントサイズ", "PASS")
        except Exception as e:
            log("T09: デフォルトフォントサイズ", "FAIL", str(e))

        # === T10: XSS escaping ===
        try:
            result = await page.evaluate("""
                (() => {
                    const xml = '<slide><title font-size="28">&lt;script&gt;alert(1)&lt;/script&gt;</title><subtitle>S</subtitle><content></content><charts>C</charts><images>I</images><layout>L</layout><color_scheme>CS</color_scheme><notes>N</notes></slide>';
                    const data = XmlEditor.parseXml(xml);
                    const container = document.createElement('div');
                    container.id = 'test-xss';
                    document.body.appendChild(container);
                    XmlEditor.renderEditor(data, 'test-xss', 77);
                    const resultXml = XmlEditor.collectToXml('test-xss', 77);
                    document.body.removeChild(container);
                    return resultXml;
                })()
            """)
            assert "<script>" not in result
            assert "&lt;script&gt;" in result
            log("T10: XSSエスケープ", "PASS")
        except Exception as e:
            log("T10: XSSエスケープ", "FAIL", str(e))

        # === T11: Static files served ===
        try:
            resp = await page.goto(f"{BASE_URL}/static/js/xml-editor.js")
            assert resp.status == 200
            body = await page.inner_text("body")
            assert "XmlEditor" in body
            log("T11: xml-editor.js配信", "PASS")
        except Exception as e:
            log("T11: xml-editor.js配信", "FAIL", str(e))

        # === T12: Empty content handling ===
        try:
            await page.goto(f"{BASE_URL}/ai-workshop?fileId=1", wait_until="networkidle")
            result = await page.evaluate("""
                (() => {
                    const xml = '<slide><title>Only Title</title><subtitle></subtitle><content></content><charts></charts><images></images><layout></layout><color_scheme></color_scheme><notes></notes></slide>';
                    const data = XmlEditor.parseXml(xml);
                    return data.sections.length === 0 && data.title === 'Only Title';
                })()
            """)
            assert result
            log("T12: 空コンテンツ処理", "PASS")
        except Exception as e:
            log("T12: 空コンテンツ処理", "FAIL", str(e))

        # === T13: Multiple sections ===
        try:
            result = await page.evaluate("""
                (() => {
                    const xml = '<slide><title>T</title><subtitle>S</subtitle><content><section name="A"><bullet>1</bullet></section><section name="B"><bullet>2</bullet><bullet>3</bullet></section></content><charts>C</charts><images>I</images><layout>L</layout><color_scheme>CS</color_scheme><notes>N</notes></slide>';
                    const data = XmlEditor.parseXml(xml);
                    return data.sections.length === 2 && data.sections[1].bullets.length === 2;
                })()
            """)
            assert result
            log("T13: 複数セクション", "PASS")
        except Exception as e:
            log("T13: 複数セクション", "FAIL", str(e))

        # === T14: Console errors check ===
        critical = [e for e in console_errors if "is not a function" in e or "Cannot read" in e or "Unexpected token" in e]
        if critical:
            log("T14: コンソールエラー", "FAIL", f"{len(critical)}件: {critical[0][:80]}")
        else:
            log("T14: コンソールエラー", "PASS", f"重大エラーなし (通知{len(console_errors)}件)")

        # === T15: Key pages still load ===
        try:
            pages_ok = 0
            for path in ["/", "/merge", "/editor"]:
                resp = await page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded", timeout=5000)
                if resp and resp.status == 200:
                    pages_ok += 1
            assert pages_ok == 3
            log("T15: 主要ページ正常", "PASS", f"{pages_ok}/3")
        except Exception as e:
            log("T15: 主要ページ正常", "FAIL", str(e))

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
    print("E2E + Monkey Test - Structured XML Editor (15 scenarios)")
    print("=" * 60)
    failed = asyncio.run(run_tests())
    sys.exit(1 if failed > 0 else 0)
