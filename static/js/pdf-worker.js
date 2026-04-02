/**
 * PDF Workshop Pro - PDF Processing Web Worker
 * Offloads heavy PDF rendering and text extraction to a background thread.
 *
 * Communication protocol:
 *   Main -> Worker:  { id, type, payload }
 *   Worker -> Main:  { id, type, result? , error? }
 *
 * Supported message types:
 *   - "init"               : Load PDF bytes into the worker
 *   - "renderPage"         : Render a single page to ImageBitmap (requires OffscreenCanvas)
 *   - "extractAllText"     : Extract text from every page
 *   - "generateThumbnails" : Render all pages as small ImageBitmaps
 *   - "ping"               : Health check
 */

/* global importScripts, pdfjsLib */

// Import PDF.js inside the worker
importScripts('/static/js/pdf.worker.min.js');
importScripts('/static/js/pdf.min.js');

// Disable the nested worker that PDF.js would otherwise try to spawn
if (typeof pdfjsLib !== 'undefined') {
    pdfjsLib.GlobalWorkerOptions.workerSrc = '';
    // Tell PDF.js to use the fake worker (inline) since we ARE the worker
    pdfjsLib.GlobalWorkerOptions.workerPort = null;
}

let _renderDoc = null;

/**
 * Load a PDF document from bytes.
 */
async function initDocument(pdfBytes) {
    if (_renderDoc) {
        _renderDoc.destroy();
        _renderDoc = null;
    }
    const loadingTask = pdfjsLib.getDocument({ data: pdfBytes });
    _renderDoc = await loadingTask.promise;
    return { pageCount: _renderDoc.numPages };
}

/**
 * Check whether OffscreenCanvas is available in this worker context.
 */
const _hasOffscreenCanvas = (typeof OffscreenCanvas !== 'undefined');

/**
 * Render a single page to an ImageBitmap via OffscreenCanvas.
 * Returns { bitmap: ImageBitmap, width, height }.
 */
async function renderPage(pageNum, scale) {
    if (!_renderDoc) throw new Error('No document loaded in worker');
    if (!_hasOffscreenCanvas) throw new Error('OffscreenCanvas not supported');

    const page = await _renderDoc.getPage(pageNum);
    const viewport = page.getViewport({ scale: scale || 1.0 });

    const canvas = new OffscreenCanvas(
        Math.floor(viewport.width),
        Math.floor(viewport.height)
    );
    const ctx = canvas.getContext('2d');

    await page.render({ canvasContext: ctx, viewport }).promise;

    const bitmap = canvas.transferToImageBitmap();
    return { bitmap, width: canvas.width, height: canvas.height };
}

/**
 * Extract text from every page. Returns an array of { pageNum, text }.
 */
async function extractAllText() {
    if (!_renderDoc) throw new Error('No document loaded in worker');

    const results = [];
    const count = _renderDoc.numPages;
    for (let i = 1; i <= count; i++) {
        const page = await _renderDoc.getPage(i);
        const content = await page.getTextContent();
        const text = content.items.map(item => item.str).join(' ');
        results.push({ pageNum: i, text });
    }
    return results;
}

/**
 * Generate thumbnail ImageBitmaps for all pages.
 * Returns an array of { pageNum, bitmap, width, height }.
 */
async function generateThumbnails(scale) {
    if (!_renderDoc) throw new Error('No document loaded in worker');
    if (!_hasOffscreenCanvas) throw new Error('OffscreenCanvas not supported');

    const thumbScale = scale || 0.3;
    const results = [];
    const count = _renderDoc.numPages;

    for (let i = 1; i <= count; i++) {
        const page = await _renderDoc.getPage(i);
        const viewport = page.getViewport({ scale: thumbScale });

        const canvas = new OffscreenCanvas(
            Math.floor(viewport.width),
            Math.floor(viewport.height)
        );
        const ctx = canvas.getContext('2d');
        await page.render({ canvasContext: ctx, viewport }).promise;

        const bitmap = canvas.transferToImageBitmap();
        results.push({
            pageNum: i,
            bitmap,
            width: canvas.width,
            height: canvas.height,
        });
    }
    return results;
}

// --- Message handler ---

self.onmessage = async function (e) {
    const { id, type, payload } = e.data;

    try {
        let result;
        let transfer = [];

        switch (type) {
            case 'ping':
                result = { ok: true, offscreenCanvas: _hasOffscreenCanvas };
                break;

            case 'init':
                result = await initDocument(payload.pdfBytes);
                break;

            case 'renderPage':
                result = await renderPage(payload.pageNum, payload.scale);
                transfer = [result.bitmap];
                break;

            case 'extractAllText':
                result = await extractAllText();
                break;

            case 'generateThumbnails':
                result = await generateThumbnails(payload && payload.scale);
                // Collect all bitmaps for transfer
                transfer = result.map(r => r.bitmap);
                break;

            default:
                throw new Error('Unknown message type: ' + type);
        }

        self.postMessage({ id, type, result }, transfer);
    } catch (err) {
        self.postMessage({
            id,
            type,
            error: { message: err.message, stack: err.stack },
        });
    }
};

// Signal that the worker is ready
self.postMessage({ id: '__ready', type: 'ready', result: { offscreenCanvas: _hasOffscreenCanvas } });
