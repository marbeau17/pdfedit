/**
 * PDF Workshop Pro - Editor UI Controller
 * Manages the editor interface, thumbnail grid, and tool interactions.
 * All operations are client-side via PdfEngine.
 */

const EditorUI = (() => {

    /**
     * Render the thumbnail grid
     */
    async function renderThumbnails(containerId = 'preview-grid') {
        const container = document.getElementById(containerId);
        if (!container || !PdfEngine.isLoaded()) return;

        const count = PdfEngine.getPageCount();
        container.innerHTML = '';

        if (count === 0) {
            container.innerHTML = '<div class="col-span-full text-center py-12 text-gray-400"><p class="text-lg">No pages</p></div>';
            return;
        }

        for (let i = 1; i <= count; i++) {
            const card = document.createElement('div');
            card.className = 'page-card group relative rounded-lg overflow-hidden shadow-md hover:shadow-xl transition-all cursor-move border-2 border-transparent hover:border-yellow-500';
            card.setAttribute('data-page-num', i);
            card.setAttribute('role', 'listitem');
            card.setAttribute('aria-label', `Page ${i}`);

            const thumbUrl = await PdfEngine.getPageThumbnail(i, 0.3);

            card.innerHTML = `
                <div class="aspect-[3/4] bg-white">
                    <img src="${thumbUrl}" alt="Page ${i} preview" class="w-full h-full object-contain" loading="lazy" />
                </div>
                <div class="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent p-2 flex justify-between items-end">
                    <span class="text-white text-sm font-bold">P${i}</span>
                    <div class="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button onclick="EditorUI.rotatePage(${i})" class="bg-blue-500 text-white rounded p-1 text-xs hover:bg-blue-600" title="Rotate" aria-label="Rotate page ${i}">
                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
                        </button>
                        <button onclick="EditorUI.deletePage(${i})" class="bg-red-500 text-white rounded p-1 text-xs hover:bg-red-600" title="Delete" aria-label="Delete page ${i}">
                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                        </button>
                    </div>
                </div>
            `;
            container.appendChild(card);
        }

        // Initialize Sortable.js for drag-and-drop
        if (typeof Sortable !== 'undefined') {
            Sortable.create(container, {
                animation: 150,
                ghostClass: 'sortable-ghost',
                delay: 100,
                delayOnTouchOnly: true,
                onEnd: async function() {
                    const cards = container.querySelectorAll('[data-page-num]');
                    const newOrder = Array.from(cards).map(c => parseInt(c.dataset.pageNum));
                    await PdfEngine.reorderPages(newOrder);
                    await renderThumbnails(containerId);
                    updateFileInfo();
                    showToast('Pages reordered', 'success');
                }
            });
        }
    }

    /**
     * Delete a single page
     */
    async function deletePage(pageNum) {
        if (!confirm(`Delete page ${pageNum}?`)) return;
        await PdfEngine.removePages([pageNum]);
        await renderThumbnails();
        updateFileInfo();
        showToast(`Page ${pageNum} deleted`, 'success');
    }

    /**
     * Delete pages by range string
     */
    async function deletePageRange(rangeStr) {
        const pages = PdfEngine.parsePageRange(rangeStr);
        if (pages.length === 0) {
            showToast('Invalid page range', 'error');
            return;
        }
        await PdfEngine.removePages(pages);
        await renderThumbnails();
        updateFileInfo();
        showToast(`${pages.length} page(s) deleted`, 'success');
    }

    /**
     * Rotate a page
     */
    async function rotatePage(pageNum) {
        await PdfEngine.rotatePage(pageNum, 90);
        await renderThumbnails();
        showToast(`Page ${pageNum} rotated`, 'success');
    }

    /**
     * Undo last operation
     */
    async function undoAction() {
        const success = await PdfEngine.undo();
        if (success) {
            await renderThumbnails();
            updateFileInfo();
            showToast('Undone', 'success');
        } else {
            showToast('Nothing to undo', 'info');
        }
    }

    /**
     * Download the edited PDF
     */
    function downloadPdf() {
        PdfEngine.download();
        showToast('Download started', 'success');
    }

    /**
     * Add branding overlay
     */
    async function applyBranding(options = {}) {
        await PdfEngine.addBranding(options);
        await renderThumbnails();
        updateFileInfo();
        showToast('Branding applied', 'success');
    }

    /**
     * Optimize (re-save to remove unused objects)
     */
    async function optimizePdf() {
        const before = PdfEngine.getCurrentBytes().length;
        // pdf-lib re-serialization removes unused objects
        const pdfDoc = await PDFLib.PDFDocument.load(PdfEngine.getCurrentBytes());
        const optimized = await pdfDoc.save();
        const after = optimized.length;
        if (after < before) {
            await PdfEngine.loadFromBytes(optimized, PdfEngine.getFileName());
            const saved = ((before - after) / before * 100).toFixed(1);
            showToast(`Optimized: -${saved}% (${(before/1024).toFixed(0)}KB → ${(after/1024).toFixed(0)}KB)`, 'success');
        } else {
            showToast('Already optimized', 'info');
        }
        await renderThumbnails();
        updateFileInfo();
    }

    /**
     * Update file info display
     */
    function updateFileInfo() {
        const info = PdfEngine.getFileInfo();
        const el = document.getElementById('file-info');
        if (el) {
            el.innerHTML = `
                <p class="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">${info.fileName}</p>
                <p class="text-xs text-gray-500">${info.pageCount} pages | ${info.fileSizeMB} MB</p>
            `;
        }
        // Update undo button state
        const undoBtn = document.getElementById('undo-btn');
        if (undoBtn) {
            undoBtn.disabled = !info.hasUndo;
            undoBtn.classList.toggle('opacity-50', !info.hasUndo);
        }
    }

    /**
     * Show toast notification
     */
    function showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        if (!container) return;
        const colors = {
            success: 'bg-green-500',
            error: 'bg-red-500',
            info: 'bg-blue-500',
        };
        const toast = document.createElement('div');
        toast.className = `${colors[type] || colors.info} text-white px-4 py-2 rounded-lg shadow-lg text-sm transition-all transform translate-y-2 opacity-0`;
        toast.textContent = message;
        toast.setAttribute('role', 'status');
        container.appendChild(toast);
        // Animate in
        requestAnimationFrame(() => {
            toast.classList.remove('translate-y-2', 'opacity-0');
        });
        // Remove after 3s
        setTimeout(() => {
            toast.classList.add('translate-y-2', 'opacity-0');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    return {
        renderThumbnails,
        deletePage,
        deletePageRange,
        rotatePage,
        undoAction,
        downloadPdf,
        applyBranding,
        optimizePdf,
        updateFileInfo,
        showToast,
    };
})();
