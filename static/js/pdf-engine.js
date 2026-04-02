/**
 * PDF Workshop Pro - Client-Side PDF Engine
 * Uses PDF.js for rendering and pdf-lib for editing.
 * All processing happens in the browser. No files are sent to the server.
 */

// PDF.js is loaded via CDN: pdfjsLib global
// pdf-lib is loaded via CDN: PDFLib global

const PdfEngine = (() => {
    // PDF.js worker is configured in base.html (v3 legacy build, synchronous load)

    let _currentDoc = null;       // PDFLib.PDFDocument (for editing)
    let _currentBytes = null;     // Uint8Array of current PDF
    let _renderDoc = null;        // pdfjsLib document (for rendering)
    let _fileName = '';
    let _history = [];            // Undo stack
    const MAX_HISTORY = 15;

    // --- Web Worker infrastructure ---
    let _worker = null;
    let _workerReady = false;
    let _workerHasOffscreen = false;
    let _workerMsgId = 0;
    const _workerCallbacks = new Map();  // id -> { resolve, reject }

    /**
     * Initialize the background Web Worker (best-effort, non-blocking).
     * If Workers or OffscreenCanvas are unavailable, all async methods
     * silently fall back to the main thread.
     */
    function _initWorker() {
        if (typeof Worker === 'undefined') {
            console.log('[PdfEngine] Web Workers not supported; using main thread');
            return;
        }
        try {
            _worker = new Worker('/static/js/pdf-worker.js');
            _worker.onmessage = _onWorkerMessage;
            _worker.onerror = (err) => {
                console.warn('[PdfEngine] Worker error, falling back to main thread:', err.message);
                _destroyWorker();
            };
        } catch (e) {
            console.warn('[PdfEngine] Failed to create worker:', e.message);
            _worker = null;
        }
    }

    function _destroyWorker() {
        if (_worker) {
            _worker.terminate();
            _worker = null;
        }
        _workerReady = false;
        // Reject all pending callbacks
        for (const [, cb] of _workerCallbacks) {
            cb.reject(new Error('Worker terminated'));
        }
        _workerCallbacks.clear();
    }

    function _onWorkerMessage(e) {
        const { id, type, result, error } = e.data;

        // Handle the initial "ready" signal
        if (id === '__ready' && type === 'ready') {
            _workerReady = true;
            _workerHasOffscreen = !!(result && result.offscreenCanvas);
            console.log('[PdfEngine] Worker ready (OffscreenCanvas:', _workerHasOffscreen, ')');
            return;
        }

        const cb = _workerCallbacks.get(id);
        if (!cb) return;
        _workerCallbacks.delete(id);

        if (error) {
            cb.reject(new Error(error.message));
        } else {
            cb.resolve(result);
        }
    }

    /**
     * Post a message to the worker and return a Promise for the response.
     * transfer is an optional array of Transferable objects.
     */
    function _postToWorker(type, payload, transfer) {
        return new Promise((resolve, reject) => {
            if (!_worker || !_workerReady) {
                return reject(new Error('Worker not available'));
            }
            const id = ++_workerMsgId;
            _workerCallbacks.set(id, { resolve, reject });
            _worker.postMessage({ id, type, payload }, transfer || []);
        });
    }

    /**
     * Send the current PDF bytes to the worker so it has its own copy.
     */
    async function _syncBytesToWorker() {
        if (!_worker || !_workerReady || !_currentBytes) return;
        try {
            const copy = _currentBytes.slice();
            await _postToWorker('init', { pdfBytes: copy }, [copy.buffer]);
        } catch (e) {
            console.warn('[PdfEngine] Failed to sync bytes to worker:', e.message);
        }
    }

    // Kick off worker initialization immediately
    _initWorker();

    /**
     * Load a PDF from a File object or ArrayBuffer
     */
    async function loadFromFile(file) {
        const arrayBuffer = await file.arrayBuffer();
        _currentBytes = new Uint8Array(arrayBuffer);
        _fileName = file.name || 'document.pdf';
        _history = [];
        await _rebuildRenderDoc();
        return getPageCount();
    }

    /**
     * Load a PDF from Uint8Array bytes
     */
    async function loadFromBytes(bytes, fileName = 'document.pdf') {
        _currentBytes = new Uint8Array(bytes);
        _fileName = fileName;
        _history = [];
        await _rebuildRenderDoc();
        return getPageCount();
    }

    /**
     * Rebuild the PDF.js render document from current bytes
     */
    async function _rebuildRenderDoc() {
        if (_renderDoc) {
            _renderDoc.destroy();
        }
        const loadingTask = pdfjsLib.getDocument({ data: _currentBytes.slice() });
        _renderDoc = await loadingTask.promise;
        // Keep the worker in sync whenever the document changes
        _syncBytesToWorker();
    }

    /**
     * Save current state to history (for undo)
     */
    function _pushHistory() {
        _history.push(_currentBytes.slice());
        if (_history.length > MAX_HISTORY) {
            _history.shift();
        }
    }

    /**
     * Apply changes: save PDFLib doc back to bytes and rebuild render doc
     */
    async function _applyChanges(pdfDoc) {
        _pushHistory();
        _currentBytes = await pdfDoc.save();
        await _rebuildRenderDoc();
    }

    // --- Query methods ---

    function getPageCount() {
        return _renderDoc ? _renderDoc.numPages : 0;
    }

    function getFileName() {
        return _fileName;
    }

    function getCurrentBytes() {
        return _currentBytes;
    }

    function hasUndo() {
        return _history.length > 0;
    }

    function isLoaded() {
        return _currentBytes !== null && _currentBytes.length > 0;
    }

    // --- Render methods ---

    /**
     * Render a page to a canvas element
     * @param {number} pageNum - 1-based page number
     * @param {HTMLCanvasElement} canvas
     * @param {number} scale - render scale (default 1.0)
     */
    async function renderPage(pageNum, canvas, scale = 1.0) {
        if (!_renderDoc) return;
        const page = await _renderDoc.getPage(pageNum);
        const viewport = page.getViewport({ scale });
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        const ctx = canvas.getContext('2d');
        await page.render({ canvasContext: ctx, viewport }).promise;
    }

    /**
     * Get page thumbnail as data URL
     */
    async function getPageThumbnail(pageNum, scale = 0.3) {
        const canvas = document.createElement('canvas');
        await renderPage(pageNum, canvas, scale);
        return canvas.toDataURL('image/png');
    }

    /**
     * Get page dimensions
     */
    async function getPageSize(pageNum) {
        if (!_renderDoc) return { width: 0, height: 0 };
        const page = await _renderDoc.getPage(pageNum);
        const viewport = page.getViewport({ scale: 1.0 });
        return { width: viewport.width, height: viewport.height };
    }

    /**
     * Extract text from a page
     */
    async function extractText(pageNum) {
        if (!_renderDoc) return '';
        const page = await _renderDoc.getPage(pageNum);
        const textContent = await page.getTextContent();
        return textContent.items.map(item => item.str).join(' ');
    }

    /**
     * Extract text from all pages
     */
    async function extractAllText() {
        const texts = [];
        const count = getPageCount();
        for (let i = 1; i <= count; i++) {
            const text = await extractText(i);
            texts.push(`--- Page ${i} ---\n${text}`);
        }
        return texts.join('\n\n');
    }

    // --- Edit methods ---

    /**
     * Remove pages
     * @param {number[]} pageNums - 1-based page numbers to remove
     */
    async function removePages(pageNums) {
        const pdfDoc = await PDFLib.PDFDocument.load(_currentBytes);
        // Sort descending to avoid index shift
        const sorted = [...pageNums].sort((a, b) => b - a);
        for (const p of sorted) {
            if (p >= 1 && p <= pdfDoc.getPageCount()) {
                pdfDoc.removePage(p - 1);
            }
        }
        await _applyChanges(pdfDoc);
        return getPageCount();
    }

    /**
     * Reorder pages
     * @param {number[]} newOrder - 1-based page numbers in new order
     */
    async function reorderPages(newOrder) {
        const srcDoc = await PDFLib.PDFDocument.load(_currentBytes);
        const dstDoc = await PDFLib.PDFDocument.create();
        for (const p of newOrder) {
            if (p >= 1 && p <= srcDoc.getPageCount()) {
                const [copied] = await dstDoc.copyPages(srcDoc, [p - 1]);
                dstDoc.addPage(copied);
            }
        }
        await _applyChanges(dstDoc);
        return getPageCount();
    }

    /**
     * Merge another PDF into the current document
     * @param {Uint8Array} otherBytes - bytes of the PDF to merge
     */
    async function mergePdf(otherBytes) {
        const dstDoc = await PDFLib.PDFDocument.load(_currentBytes);
        const srcDoc = await PDFLib.PDFDocument.load(otherBytes);
        const indices = srcDoc.getPageIndices();
        const copiedPages = await dstDoc.copyPages(srcDoc, indices);
        for (const page of copiedPages) {
            dstDoc.addPage(page);
        }
        await _applyChanges(dstDoc);
        return getPageCount();
    }

    /**
     * Merge multiple PDFs
     * @param {Uint8Array[]} pdfBytesList - array of PDF bytes to merge
     */
    async function mergeMultiple(pdfBytesList) {
        const dstDoc = await PDFLib.PDFDocument.create();
        for (const bytes of pdfBytesList) {
            const srcDoc = await PDFLib.PDFDocument.load(bytes);
            const indices = srcDoc.getPageIndices();
            const copiedPages = await dstDoc.copyPages(srcDoc, indices);
            for (const page of copiedPages) {
                dstDoc.addPage(page);
            }
        }
        await _applyChanges(dstDoc);
        return getPageCount();
    }

    /**
     * Add a blank page at a specific position
     * @param {number} afterPageNum - 1-based page number to insert after (0 = beginning, pageCount = end)
     * @param {number} [width] - page width in points (default: match first page or A4)
     * @param {number} [height] - page height in points (default: match first page or A4)
     * @returns {Promise<number>} new page count
     */
    async function addBlankPage(afterPageNum, width, height) {
        const pdfDoc = await PDFLib.PDFDocument.load(_currentBytes);
        const pageCount = pdfDoc.getPageCount();

        // Default dimensions: match first page, or A4 if no pages
        if (width == null || height == null) {
            if (pageCount > 0) {
                const firstPage = pdfDoc.getPage(0);
                const size = firstPage.getSize();
                width = width ?? size.width;
                height = height ?? size.height;
            } else {
                width = width ?? 595;
                height = height ?? 842;
            }
        }

        // Default position: append at end
        if (afterPageNum == null) {
            afterPageNum = pageCount;
        }

        // Clamp to valid range
        const insertIndex = Math.max(0, Math.min(afterPageNum, pageCount));

        pdfDoc.insertPage(insertIndex, [width, height]);
        await _applyChanges(pdfDoc);
        return getPageCount();
    }

    /**
     * Rotate a page
     * @param {number} pageNum - 1-based
     * @param {number} degrees - 90, 180, 270
     */
    async function rotatePage(pageNum, degrees = 90) {
        const pdfDoc = await PDFLib.PDFDocument.load(_currentBytes);
        const page = pdfDoc.getPage(pageNum - 1);
        const current = page.getRotation().angle;
        page.setRotation(PDFLib.degrees((current + degrees) % 360));
        await _applyChanges(pdfDoc);
    }

    /**
     * Add text overlay to a page
     */
    async function addText(pageNum, text, x, y, fontSize = 12, color = { r: 0, g: 0, b: 0 }) {
        const pdfDoc = await PDFLib.PDFDocument.load(_currentBytes);
        const page = pdfDoc.getPage(pageNum - 1);
        const font = await pdfDoc.embedFont(PDFLib.StandardFonts.Helvetica);
        page.drawText(text, {
            x, y,
            size: fontSize,
            font,
            color: PDFLib.rgb(color.r, color.g, color.b),
        });
        await _applyChanges(pdfDoc);
    }

    /**
     * Add image to a page
     * @param {number} pageNum - 1-based
     * @param {Uint8Array} imageBytes - PNG or JPG bytes
     * @param {string} type - 'png' or 'jpg'
     * @param {object} rect - { x, y, width, height }
     */
    async function addImage(pageNum, imageBytes, type, rect) {
        const pdfDoc = await PDFLib.PDFDocument.load(_currentBytes);
        const page = pdfDoc.getPage(pageNum - 1);
        let img;
        if (type === 'png') {
            img = await pdfDoc.embedPng(imageBytes);
        } else {
            img = await pdfDoc.embedJpg(imageBytes);
        }
        page.drawImage(img, {
            x: rect.x,
            y: rect.y,
            width: rect.width,
            height: rect.height,
        });
        await _applyChanges(pdfDoc);
    }

    /**
     * Add branding overlay (page number + footer text)
     */
    async function addBranding(options = {}) {
        const {
            skipFirstPageNum = true,
            skipFirstLogo = true,
            enableLogo = true,
            enablePageNum = true,
            footerText = 'Strictly Private & Confidential',
            copyrightText = '\u00a92026 Meets Consulting Inc.',
            pageNumRight = 50,
            pageNumBottom = 30,
            logoMarginX = 20,
            logoMarginY = 12,
            logoWidth = 50,
            logoHeight = 50,
            logoBytes = null,  // Uint8Array of PNG logo
            targetPages = null,
        } = options;

        const pdfDoc = await PDFLib.PDFDocument.load(_currentBytes);
        const font = await pdfDoc.embedFont(PDFLib.StandardFonts.Helvetica);
        const pages = pdfDoc.getPages();

        // Embed logo if provided
        let logoImage = null;
        if (enableLogo && logoBytes && logoBytes.length > 0) {
            console.log('[addBranding] Embedding logo:', logoBytes.length, 'bytes');
            try {
                logoImage = await pdfDoc.embedPng(logoBytes);
                console.log('[addBranding] PNG embed success:', logoImage.width, 'x', logoImage.height);
            } catch (e) {
                console.warn('[addBranding] PNG embed failed, trying JPG:', e.message);
                try {
                    logoImage = await pdfDoc.embedJpg(logoBytes);
                    console.log('[addBranding] JPG embed success');
                } catch (e2) {
                    console.error('[addBranding] Logo embed failed completely:', e2.message);
                }
            }
        } else {
            console.log('[addBranding] No logo:', { enableLogo, hasBytes: !!logoBytes, bytesLen: logoBytes?.length });
        }

        for (let i = 0; i < pages.length; i++) {
            const pageNum = i + 1;
            if (targetPages && !targetPages.includes(pageNum)) continue;

            const page = pages[i];
            const { width, height } = page.getSize();

            // Logo (top-right corner, aspect ratio preserved)
            if (enableLogo && logoImage && !(pageNum === 1 && skipFirstLogo)) {
                // Calculate dimensions preserving aspect ratio
                const imgRatio = logoImage.width / logoImage.height;
                let drawW = logoWidth;
                let drawH = logoWidth / imgRatio;
                // If too tall, constrain by height
                if (drawH > logoHeight) {
                    drawH = logoHeight;
                    drawW = logoHeight * imgRatio;
                }
                const lx = width - logoMarginX - drawW;
                const ly = height - logoMarginY - drawH;
                page.drawImage(logoImage, {
                    x: lx, y: ly,
                    width: drawW, height: drawH,
                });
            }

            // Footer text
            if (enableLogo) {
                page.drawText(footerText, {
                    x: 40, y: 20, size: 8, font,
                    color: PDFLib.rgb(0.5, 0.5, 0.5),
                });
                page.drawText('Internal Use Only', {
                    x: 40 + font.widthOfTextAtSize(footerText + ' ', 8), y: 20, size: 8, font,
                    color: PDFLib.rgb(0.81, 0.68, 0.44),
                });
                page.drawText(copyrightText, {
                    x: width - 180, y: 20, size: 8, font,
                    color: PDFLib.rgb(0.5, 0.5, 0.5),
                });
            }

            // Page number with bar
            if (enablePageNum && !(pageNum === 1 && skipFirstPageNum)) {
                const pgX = width - pageNumRight;
                const pgY = pageNumBottom;
                page.drawText(String(pageNum), {
                    x: pgX, y: pgY, size: 12, font,
                    color: PDFLib.rgb(0.11, 0.19, 0.36),
                });
                // Vertical bar before number
                page.drawRectangle({
                    x: pgX - 15, y: pgY - 2,
                    width: 2, height: 17,
                    color: PDFLib.rgb(0.11, 0.19, 0.36),
                });
            }
        }
        await _applyChanges(pdfDoc);
    }

    /**
     * Undo last operation
     */
    async function undo() {
        if (_history.length === 0) return false;
        _currentBytes = _history.pop();
        await _rebuildRenderDoc();
        return true;
    }

    /**
     * Download the current PDF
     */
    function download(filename) {
        if (!_currentBytes || _currentBytes.length === 0) {
            console.error('[PdfEngine] No PDF data to download');
            return;
        }
        const name = filename || _fileName || 'edited.pdf';
        const blob = new Blob([_currentBytes], { type: 'application/pdf' });
        const url = URL.createObjectURL(blob);

        // Detect if running inside a sandboxed iframe (e.g. Vercel toolbar)
        const inSandboxedIframe = window.self !== window.top;

        if (inSandboxedIframe) {
            // Sandboxed iframes block anchor downloads; open in new tab instead
            const newTab = window.open(url, '_blank');
            if (!newTab) {
                // Popup blocked — fallback: navigate top frame directly
                window.top.location.href = url;
            }
            setTimeout(() => URL.revokeObjectURL(url), 10000);
        } else {
            const a = document.createElement('a');
            a.href = url;
            a.download = name;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            setTimeout(() => URL.revokeObjectURL(url), 1000);
        }
    }

    /**
     * Get file size info
     */
    function getFileInfo() {
        return {
            fileName: _fileName,
            fileSize: _currentBytes ? _currentBytes.length : 0,
            fileSizeMB: _currentBytes ? (_currentBytes.length / 1024 / 1024).toFixed(2) : '0',
            pageCount: getPageCount(),
            hasUndo: hasUndo(),
        };
    }

    /**
     * Parse page range string like "1,3-5" into array [1,3,4,5]
     */
    function parsePageRange(rangeStr) {
        const result = [];
        if (!rangeStr) return result;
        for (const part of rangeStr.split(',')) {
            const trimmed = part.trim();
            if (trimmed.includes('-')) {
                const [start, end] = trimmed.split('-').map(Number);
                if (!isNaN(start) && !isNaN(end)) {
                    for (let i = start; i <= end; i++) result.push(i);
                }
            } else {
                const num = parseInt(trimmed);
                if (!isNaN(num)) result.push(num);
            }
        }
        return result;
    }

    /**
     * Render a page to a Blob (PNG)
     * @param {number} pageNum - 1-based
     * @param {number} scale - render scale (default 1.5 for good quality)
     * @returns {Promise<Blob>}
     */
    async function renderPageToBlob(pageNum, scale = 1.5) {
        const canvas = document.createElement('canvas');
        await renderPage(pageNum, canvas, scale);
        return new Promise((resolve) => {
            canvas.toBlob(resolve, 'image/png');
        });
    }

    /**
     * Render a page to base64 data URL
     */
    async function renderPageToBase64(pageNum, scale = 1.5) {
        const canvas = document.createElement('canvas');
        await renderPage(pageNum, canvas, scale);
        return canvas.toDataURL('image/png');
    }

    /**
     * Replace a page with an image (for AI-generated slides)
     * @param {number} pageNum - 1-based page number to replace
     * @param {Uint8Array} imageBytes - PNG or JPG image bytes
     * @param {string} imageType - 'png' or 'jpg'
     */
    async function replacePageWithImage(pageNum, imageBytes, imageType = 'png') {
        const pdfDoc = await PDFLib.PDFDocument.load(_currentBytes);
        const pageCount = pdfDoc.getPageCount();
        if (pageNum < 1 || pageNum > pageCount) return;

        // Get original page dimensions
        const origPage = pdfDoc.getPage(pageNum - 1);
        const { width, height } = origPage.getSize();

        // Remove original page
        pdfDoc.removePage(pageNum - 1);

        // Create new page with same dimensions
        const newPage = pdfDoc.insertPage(pageNum - 1, [width, height]);

        // Embed image (try requested format, fallback to other)
        let img;
        try {
            if (imageType === 'png') {
                img = await pdfDoc.embedPng(imageBytes);
            } else {
                img = await pdfDoc.embedJpg(imageBytes);
            }
        } catch (e) {
            // Format mismatch (e.g. webp data labeled as png) — try the other
            try {
                img = imageType === 'png'
                    ? await pdfDoc.embedJpg(imageBytes)
                    : await pdfDoc.embedPng(imageBytes);
            } catch (e2) {
                throw new Error('画像の埋め込みに失敗しました。形式を確認してください。');
            }
        }

        // Scale image to fit page while maintaining aspect ratio
        const imgAspect = img.width / img.height;
        const pageAspect = width / height;
        let drawWidth, drawHeight, drawX, drawY;

        if (imgAspect > pageAspect) {
            drawWidth = width;
            drawHeight = width / imgAspect;
            drawX = 0;
            drawY = (height - drawHeight) / 2;
        } else {
            drawHeight = height;
            drawWidth = height * imgAspect;
            drawX = (width - drawWidth) / 2;
            drawY = 0;
        }

        newPage.drawImage(img, {
            x: drawX,
            y: drawY,
            width: drawWidth,
            height: drawHeight,
        });

        await _applyChanges(pdfDoc);
    }

    /**
     * Resize all pages to match the first page's dimensions.
     * Each page's content is embedded as a form XObject and drawn scaled
     * onto a new page, preserving aspect ratio with letterboxing.
     * @returns {{ targetWidth: number, targetHeight: number, resizedCount: number }}
     */
    async function resizePages() {
        const pdfDoc = await PDFLib.PDFDocument.load(_currentBytes);
        const pageCount = pdfDoc.getPageCount();
        if (pageCount < 2) {
            return { targetWidth: 0, targetHeight: 0, resizedCount: 0 };
        }

        const firstPage = pdfDoc.getPage(0);
        const { width: targetW, height: targetH } = firstPage.getSize();

        // Build a new document: copy page 1 as-is, then embed+scale the rest
        const newDoc = await PDFLib.PDFDocument.create();

        // Copy page 1 directly
        const [p1] = await newDoc.copyPages(pdfDoc, [0]);
        newDoc.addPage(p1);

        let resizedCount = 0;

        for (let i = 1; i < pageCount; i++) {
            const srcPage = pdfDoc.getPage(i);
            const { width: srcW, height: srcH } = srcPage.getSize();

            // If dimensions already match (within 1pt tolerance), just copy
            if (Math.abs(srcW - targetW) < 1 && Math.abs(srcH - targetH) < 1) {
                const [copied] = await newDoc.copyPages(pdfDoc, [i]);
                newDoc.addPage(copied);
                continue;
            }

            resizedCount++;

            // Embed the source page as a form XObject
            const [embedded] = await newDoc.embedPages(pdfDoc, [i]);

            // Create a new page with target dimensions
            const newPage = newDoc.addPage([targetW, targetH]);

            // Calculate scale to fit, preserving aspect ratio
            const scaleX = targetW / srcW;
            const scaleY = targetH / srcH;
            const scale = Math.min(scaleX, scaleY);

            const drawW = srcW * scale;
            const drawH = srcH * scale;

            // Center (letterbox)
            const drawX = (targetW - drawW) / 2;
            const drawY = (targetH - drawH) / 2;

            newPage.drawPage(embedded, {
                x: drawX,
                y: drawY,
                width: drawW,
                height: drawH,
            });
        }

        await _applyChanges(newDoc);
        return { targetWidth: targetW, targetHeight: targetH, resizedCount };
    }

    // --- Worker-backed async methods (with main-thread fallback) ---

    /**
     * Check if the worker is operational for rendering tasks.
     * Rendering requires both the worker AND OffscreenCanvas support.
     */
    function isWorkerAvailable() {
        return _worker !== null && _workerReady;
    }

    function isOffscreenCanvasAvailable() {
        return isWorkerAvailable() && _workerHasOffscreen;
    }

    /**
     * Render a page off the main thread, returning an ImageBitmap.
     * Falls back to main-thread canvas rendering if the worker is unavailable.
     *
     * @param {number} pageNum - 1-based page number
     * @param {number} [scale=1.0] - render scale
     * @returns {Promise<{bitmap?: ImageBitmap, dataUrl?: string, width: number, height: number}>}
     *   Returns bitmap when worker is used, dataUrl when falling back to main thread.
     */
    async function renderPageAsync(pageNum, scale = 1.0) {
        // Try worker path first
        if (isOffscreenCanvasAvailable()) {
            try {
                const res = await _postToWorker('renderPage', { pageNum, scale });
                return { bitmap: res.bitmap, width: res.width, height: res.height };
            } catch (e) {
                console.warn('[PdfEngine] renderPageAsync worker failed, falling back:', e.message);
            }
        }
        // Main-thread fallback: render to an off-screen canvas and return dataUrl
        const canvas = document.createElement('canvas');
        await renderPage(pageNum, canvas, scale);
        return {
            dataUrl: canvas.toDataURL('image/png'),
            width: canvas.width,
            height: canvas.height,
        };
    }

    /**
     * Extract text from all pages using the worker.
     * Falls back to the existing main-thread extractAllText().
     *
     * @returns {Promise<string>} Combined text of all pages.
     */
    async function extractAllTextAsync() {
        if (isWorkerAvailable()) {
            try {
                const pages = await _postToWorker('extractAllText', {});
                return pages
                    .map(p => `--- Page ${p.pageNum} ---\n${p.text}`)
                    .join('\n\n');
            } catch (e) {
                console.warn('[PdfEngine] extractAllTextAsync worker failed, falling back:', e.message);
            }
        }
        return extractAllText();
    }

    /**
     * Generate thumbnails for all pages using the worker.
     * Falls back to main-thread rendering when OffscreenCanvas is unavailable.
     *
     * @param {number} [scale=0.3] - thumbnail scale
     * @returns {Promise<Array<{pageNum: number, bitmap?: ImageBitmap, dataUrl?: string, width: number, height: number}>>}
     */
    async function generateThumbnailsAsync(scale = 0.3) {
        // Try worker path
        if (isOffscreenCanvasAvailable()) {
            try {
                const results = await _postToWorker('generateThumbnails', { scale });
                return results;  // Array of { pageNum, bitmap, width, height }
            } catch (e) {
                console.warn('[PdfEngine] generateThumbnailsAsync worker failed, falling back:', e.message);
            }
        }
        // Main-thread fallback
        const count = getPageCount();
        const results = [];
        for (let i = 1; i <= count; i++) {
            const dataUrl = await getPageThumbnail(i, scale);
            results.push({ pageNum: i, dataUrl });
        }
        return results;
    }

    /**
     * Export a single page as an image Blob
     * @param {number} pageNum - 1-based page number
     * @param {string} format - 'png' or 'jpeg'
     * @param {number} scale - render scale (default 2 for retina quality)
     * @returns {Promise<Blob>}
     */
    async function exportPageAsImage(pageNum, format = 'png', scale = 2) {
        const canvas = document.createElement('canvas');
        await renderPage(pageNum, canvas, scale);
        const mimeType = format === 'jpeg' ? 'image/jpeg' : 'image/png';
        const quality = format === 'jpeg' ? 0.92 : undefined;
        return new Promise((resolve) => {
            canvas.toBlob(resolve, mimeType, quality);
        });
    }

    /**
     * Export all pages as image Blobs (one at a time to avoid OOM)
     * @param {string} format - 'png' or 'jpeg'
     * @param {number} scale - render scale
     * @param {function} onProgress - callback(current, total) for progress updates
     * @returns {Promise<Blob[]>}
     */
    async function exportAllPagesAsImages(format = 'png', scale = 2, onProgress = null) {
        const count = getPageCount();
        const blobs = [];
        for (let i = 1; i <= count; i++) {
            const blob = await exportPageAsImage(i, format, scale);
            blobs.push(blob);
            if (onProgress) onProgress(i, count);
        }
        return blobs;
    }

    /**
     * Download a single page as an image file
     * @param {number} pageNum - 1-based page number
     * @param {string} format - 'png' or 'jpeg'
     * @param {number} scale - render scale
     */
    async function downloadPageAsImage(pageNum, format = 'png', scale = 2) {
        const blob = await exportPageAsImage(pageNum, format, scale);
        const ext = format === 'jpeg' ? 'jpg' : 'png';
        const baseName = _fileName.replace(/\.pdf$/i, '');
        const name = `${baseName}_page${pageNum}.${ext}`;
        _triggerBlobDownload(blob, name);
    }

    /**
     * Download all pages as a ZIP file containing images
     * @param {string} format - 'png' or 'jpeg'
     * @param {number} scale - render scale
     * @param {function} onProgress - callback(current, total) for progress updates
     */
    async function downloadAllPagesAsZip(format = 'png', scale = 2, onProgress = null) {
        if (typeof JSZip === 'undefined') {
            throw new Error('JSZip is not loaded');
        }
        const zip = new JSZip();
        const count = getPageCount();
        const ext = format === 'jpeg' ? 'jpg' : 'png';
        const baseName = _fileName.replace(/\.pdf$/i, '');

        for (let i = 1; i <= count; i++) {
            const blob = await exportPageAsImage(i, format, scale);
            const fileName = `${baseName}_page${String(i).padStart(3, '0')}.${ext}`;
            zip.file(fileName, blob);
            if (onProgress) onProgress(i, count);
        }

        const zipBlob = await zip.generateAsync({ type: 'blob' });
        _triggerBlobDownload(zipBlob, `${baseName}_images.zip`);
    }

    /**
     * Extract specified pages into a new PDF document (non-destructive).
     * @param {number[]} pageNumbers - 1-based page numbers to extract
     * @returns {Promise<Uint8Array>} bytes of the new PDF containing only the specified pages
     */
    async function extractPages(pageNumbers) {
        if (!_currentBytes || _currentBytes.length === 0) {
            throw new Error('PDFが読み込まれていません');
        }
        const srcDoc = await PDFLib.PDFDocument.load(_currentBytes);
        const srcPageCount = srcDoc.getPageCount();
        const dstDoc = await PDFLib.PDFDocument.create();

        // Filter to valid page numbers and deduplicate while preserving order
        const seen = new Set();
        const validPages = [];
        for (const p of pageNumbers) {
            if (p >= 1 && p <= srcPageCount && !seen.has(p)) {
                seen.add(p);
                validPages.push(p);
            }
        }

        if (validPages.length === 0) {
            throw new Error('有効なページ番号がありません');
        }

        // Copy pages (convert to 0-based indices)
        const indices = validPages.map(p => p - 1);
        const copiedPages = await dstDoc.copyPages(srcDoc, indices);
        for (const page of copiedPages) {
            dstDoc.addPage(page);
        }

        return await dstDoc.save();
    }

    /**
     * Extract specified pages and trigger a browser download.
     * @param {number[]} pageNumbers - 1-based page numbers to extract
     * @param {string} [filename] - optional filename; auto-generated if omitted
     */
    async function downloadExtractedPages(pageNumbers, filename) {
        const bytes = await extractPages(pageNumbers);

        if (!filename) {
            const baseName = _fileName.replace(/\.pdf$/i, '');
            // Build a compact range description
            const sorted = [...pageNumbers].sort((a, b) => a - b);
            let rangeStr = '';
            if (sorted.length <= 5) {
                rangeStr = sorted.join('-');
            } else {
                rangeStr = `${sorted[0]}-${sorted[sorted.length - 1]}`;
            }
            filename = `${baseName}_pages_${rangeStr}.pdf`;
        }

        const blob = new Blob([bytes], { type: 'application/pdf' });
        _triggerBlobDownload(blob, filename);
    }

    /**
     * Trigger a browser download from a Blob
     */
    function _triggerBlobDownload(blob, filename) {
        const url = URL.createObjectURL(blob);
        const inSandboxedIframe = window.self !== window.top;

        if (inSandboxedIframe) {
            const newTab = window.open(url, '_blank');
            if (!newTab) {
                window.top.location.href = url;
            }
            setTimeout(() => URL.revokeObjectURL(url), 10000);
        } else {
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            setTimeout(() => URL.revokeObjectURL(url), 1000);
        }
    }

    // Public API
    return {
        loadFromFile,
        loadFromBytes,
        getPageCount,
        getFileName,
        getCurrentBytes,
        getFileInfo,
        isLoaded,
        hasUndo,
        renderPage,
        getPageThumbnail,
        getPageSize,
        extractText,
        extractAllText,
        removePages,
        reorderPages,
        mergePdf,
        mergeMultiple,
        addBlankPage,
        rotatePage,
        addText,
        addImage,
        addBranding,
        undo,
        download,
        parsePageRange,
        renderPageToBlob,
        renderPageToBase64,
        replacePageWithImage,
        resizePages,
        exportPageAsImage,
        exportAllPagesAsImages,
        downloadPageAsImage,
        downloadAllPagesAsZip,
        extractPages,
        downloadExtractedPages,
        // Worker-backed async methods
        renderPageAsync,
        extractAllTextAsync,
        generateThumbnailsAsync,
        isWorkerAvailable,
        isOffscreenCanvasAvailable,
    };
})();
