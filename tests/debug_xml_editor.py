"""Debug test for XmlEditor rendering."""
import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('http://127.0.0.1:8765/ai-workshop?fileId=1', wait_until='networkidle')

        result = await page.evaluate("""
            (() => {
                const rawXml = '<slide><title font-size="28">Smart Delivery</title><subtitle font-size="18">PROJECT KICKOFF</subtitle><content><section name="Info"><bullet font-size="14">Line 1</bullet><bullet font-size="14">Line 2</bullet></section></content><charts font-size="12">KPI chart</charts><images>Truck image</images><layout>2 columns</layout><color_scheme>Navy, Green</color_scheme><notes font-size="10">Notes here</notes></slide>';

                try {
                    const clean = XmlEditor.extractXmlFromResponse(rawXml);
                    const data = XmlEditor.parseXml(clean);

                    const container = document.createElement('div');
                    container.id = 'debug-test';
                    document.body.appendChild(container);
                    XmlEditor.renderEditor(data, 'debug-test', 99);

                    const titleInput = container.querySelector('[data-field="title"]');
                    const subtitleInput = container.querySelector('[data-field="subtitle"]');
                    const bulletInputs = container.querySelectorAll('[data-field="bulletText"]');
                    const chartsInput = container.querySelector('[data-field="charts"]');

                    const result = {
                        parseOk: true,
                        title: data.title,
                        subtitle: data.subtitle,
                        sections: data.sections.length,
                        titleInputValue: titleInput ? titleInput.value : 'NOT_FOUND',
                        subtitleInputValue: subtitleInput ? subtitleInput.value : 'NOT_FOUND',
                        bulletCount: bulletInputs.length,
                        bulletValues: Array.from(bulletInputs).map(i => i.value),
                        chartsValue: chartsInput ? chartsInput.value : 'NOT_FOUND',
                        totalInputs: container.querySelectorAll('input, textarea, select').length,
                        containerHTML: container.innerHTML.substring(0, 500),
                    };

                    document.body.removeChild(container);
                    return JSON.stringify(result, null, 2);
                } catch (e) {
                    return JSON.stringify({error: e.message, stack: e.stack});
                }
            })()
        """)
        print(result)
        await browser.close()

asyncio.run(test())
