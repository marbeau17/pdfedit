/**
 * PDF Workshop Pro - Client-Side PDF Engine
 * Uses PDF.js for rendering and pdf-lib for editing.
 * All processing happens in the browser. No files are sent to the server.
 */

// PDF.js is loaded via CDN: pdfjsLib global
// pdf-lib is loaded via CDN: PDFLib global

const PdfEngine = (() => {
    // Set PDF.js worker
    if (typeof pdfjsLib !== 'undefined') {
        pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.9.155/pdf.worker.min.mjs';
    }

    let _currentDoc = null;       // PDFLib.PDFDocument (for editing)
    let _currentBytes = null;     // Uint8Array of current PDF
    let _renderDoc = null;        // pdfjsLib document (for rendering)
    let _fileName = '';
    let _history = [];            // Undo stack
    const MAX_HISTORY = 15;

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
     * Add a blank page
     */
    async function addBlankPage(width = 595, height = 842) {
        const pdfDoc = await PDFLib.PDFDocument.load(_currentBytes);
        pdfDoc.addPage([width, height]);
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
            footerText = 'Strictly Private & Confidential',
            copyrightText = '\u00a92026 Meets Consulting Inc.',
            pageNumRight = 50,
            pageNumBottom = 30,
            targetPages = null, // null = all pages
        } = options;

        const pdfDoc = await PDFLib.PDFDocument.load(_currentBytes);
        const font = await pdfDoc.embedFont(PDFLib.StandardFonts.Helvetica);
        const pages = pdfDoc.getPages();

        for (let i = 0; i < pages.length; i++) {
            const pageNum = i + 1;
            if (targetPages && !targetPages.includes(pageNum)) continue;

            const page = pages[i];
            const { width, height } = page.getSize();

            // Footer
            page.drawText(footerText, {
                x: 40, y: 20, size: 8, font,
                color: PDFLib.rgb(0.5, 0.5, 0.5),
            });
            page.drawText(copyrightText, {
                x: width - 180, y: 20, size: 8, font,
                color: PDFLib.rgb(0.5, 0.5, 0.5),
            });

            // Page number
            if (!(pageNum === 1 && skipFirstPageNum)) {
                page.drawText(String(pageNum), {
                    x: width - pageNumRight,
                    y: pageNumBottom,
                    size: 12, font,
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
        const blob = new Blob([_currentBytes], { type: 'application/pdf' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename || _fileName || 'edited.pdf';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
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

        // Embed and draw image
        let img;
        if (imageType === 'png') {
            img = await pdfDoc.embedPng(imageBytes);
        } else {
            img = await pdfDoc.embedJpg(imageBytes);
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
    };
})();
