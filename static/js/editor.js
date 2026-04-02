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

        // Clean stale selections
        for (const p of Array.from(_selectedPages)) {
            if (p > count) _selectedPages.delete(p);
        }

        if (count === 0) {
            _selectedPages.clear();
            _updateBatchToolbar();
            container.innerHTML = '<div class="col-span-full text-center py-12 text-gray-400"><p class="text-lg">ページがありません</p></div>';
            return;
        }

        // Helper to create an insert button between pages
        function _createInsertBtn(afterPageNum) {
            const btn = document.createElement('div');
            btn.className = 'insert-blank-btn flex items-center justify-center';
            btn.setAttribute('data-insert-after', afterPageNum);
            btn.innerHTML = `
                <button onclick="event.stopPropagation(); EditorUI.insertBlankPage(${afterPageNum})"
                        class="w-7 h-7 rounded-full bg-green-500 hover:bg-green-600 text-white shadow-md hover:shadow-lg transition-all opacity-0 hover:opacity-100 focus:opacity-100 flex items-center justify-center hover:scale-110"
                        title="ここに空白ページを挿入"
                        aria-label="ページ${afterPageNum}の後に空白ページを挿入">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
                </button>
            `;
            return btn;
        }

        // Insert button before page 1 (insert at beginning)
        container.appendChild(_createInsertBtn(0));

        for (let i = 1; i <= count; i++) {
            const card = document.createElement('div');
            const isSelected = _selectedPages.has(i);
            card.className = 'page-card group relative rounded-lg overflow-hidden shadow-md hover:shadow-xl transition-all cursor-move border-2'
                + (isSelected ? ' border-yellow-400 ring-2 ring-yellow-400' : ' border-transparent hover:border-yellow-500');
            card.setAttribute('data-page-num', i);
            card.setAttribute('role', 'listitem');
            card.setAttribute('aria-label', `ページ ${i}`);

            const thumbUrl = await PdfEngine.getPageThumbnail(i, 0.3);

            card.innerHTML = `
                <div class="aspect-[3/4] bg-white relative">
                    <img src="${thumbUrl}" alt="ページ ${i} プレビュー" class="w-full h-full object-contain" loading="lazy" />
                    <div class="batch-select-overlay absolute inset-0 bg-yellow-400/20 flex items-center justify-center pointer-events-none ${isSelected ? '' : 'hidden'}">
                        <svg class="w-10 h-10 text-yellow-500 drop-shadow-lg" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"/></svg>
                    </div>
                </div>
                <label class="absolute top-1.5 left-1.5 z-10 cursor-pointer" onclick="event.stopPropagation()">
                    <input type="checkbox" class="batch-checkbox w-5 h-5 rounded border-gray-300 text-yellow-500 focus:ring-yellow-400 cursor-pointer shadow" ${isSelected ? 'checked' : ''}
                           onchange="EditorUI.togglePageSelection(${i})" />
                </label>
                <div class="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent p-2 flex justify-between items-end">
                    <span class="text-white text-sm font-bold">P${i}</span>
                    <div class="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button onclick="event.stopPropagation(); EditorUI.rotatePage(${i})" class="bg-blue-500 text-white rounded p-1 text-xs hover:bg-blue-600" title="回転" aria-label="ページ ${i} を回転">
                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
                        </button>
                        <button onclick="event.stopPropagation(); EditorUI.deletePage(${i})" class="bg-red-500 text-white rounded p-1 text-xs hover:bg-red-600" title="削除" aria-label="ページ ${i} を削除">
                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                        </button>
                    </div>
                </div>
            `;
            // Attach click handler for page selection
            card.addEventListener('click', (e) => EditorUI.handlePageClick(e, i));
            container.appendChild(card);

            // Insert button after each page
            container.appendChild(_createInsertBtn(i));
        }

        _updateBatchToolbar();

        // Initialize Sortable.js for drag-and-drop
        if (typeof Sortable !== 'undefined') {
            Sortable.create(container, {
                animation: 150,
                ghostClass: 'sortable-ghost',
                delay: 100,
                delayOnTouchOnly: true,
                filter: '.batch-checkbox, .insert-blank-btn',
                preventOnFilter: false,
                draggable: '.page-card',
                onEnd: async function() {
                    const cards = container.querySelectorAll('[data-page-num]');
                    const newOrder = Array.from(cards).map(c => parseInt(c.dataset.pageNum));
                    await PdfEngine.reorderPages(newOrder);
                    _selectedPages.clear();
                    await renderThumbnails(containerId);
                    updateFileInfo();
                    if (typeof PdfStorage !== 'undefined' && PdfStorage.triggerAutoSave) PdfStorage.triggerAutoSave();
                    showToast('ページ順序変更完了', 'success');
                }
            });
        }
    }

    /**
     * Delete a single page
     */
    async function deletePage(pageNum) {
        if (!confirm(`ページ${pageNum}を削除しますか？`)) return;
        await PdfEngine.removePages([pageNum]);
        _selectedPages.delete(pageNum);
        await renderThumbnails();
        updateFileInfo();
        if (typeof PdfStorage !== 'undefined' && PdfStorage.triggerAutoSave) PdfStorage.triggerAutoSave();
        showToast(`ページ${pageNum}削除完了`, 'success');
    }

    /**
     * Delete pages by range string
     */
    async function deletePageRange(rangeStr) {
        const pages = PdfEngine.parsePageRange(rangeStr);
        if (pages.length === 0) {
            showToast('無効なページ指定', 'error');
            return;
        }
        await PdfEngine.removePages(pages);
        _selectedPages.clear();
        await renderThumbnails();
        updateFileInfo();
        if (typeof PdfStorage !== 'undefined' && PdfStorage.triggerAutoSave) PdfStorage.triggerAutoSave();
        showToast(`${pages.length}ページ削除完了`, 'success');
    }

    /**
     * Rotate a page
     */
    async function rotatePage(pageNum) {
        await PdfEngine.rotatePage(pageNum, 90);
        await renderThumbnails();
        if (typeof PdfStorage !== 'undefined' && PdfStorage.triggerAutoSave) PdfStorage.triggerAutoSave();
        showToast(`ページ${pageNum}回転完了`, 'success');
    }

    /**
     * Undo last operation
     */
    async function undoAction() {
        const success = await PdfEngine.undo();
        if (success) {
            _selectedPages.clear();
            await renderThumbnails();
            updateFileInfo();
            if (typeof PdfStorage !== 'undefined' && PdfStorage.triggerAutoSave) PdfStorage.triggerAutoSave();
            showToast('元に戻しました', 'success');
        } else {
            showToast('戻す操作がありません', 'info');
        }
    }

    /**
     * Download the edited PDF
     */
    function downloadPdf() {
        if (!PdfEngine.isLoaded()) {
            showToast('PDFが読み込まれていません', 'error');
            return;
        }
        try {
            PdfEngine.download();
            showToast('ダウンロード開始', 'success');
        } catch (e) {
            console.error('[Download] error:', e);
            showToast('ダウンロードエラー: ' + e.message, 'error');
        }
    }

    // Store uploaded logo bytes
    let _logoBytes = null;

    /**
     * Handle logo file upload from input
     */
    async function handleLogoUpload(input) {
        if (!input.files || !input.files[0]) return;
        const file = input.files[0];
        const arrayBuffer = await file.arrayBuffer();
        _logoBytes = new Uint8Array(arrayBuffer);
        const preview = document.getElementById('logo-preview');
        if (preview) {
            const url = URL.createObjectURL(file);
            preview.innerHTML = `<img src="${url}" class="h-8 object-contain rounded" alt="Logo" />
                <span class="text-xs text-green-500 ml-2">${file.name}</span>`;
        }
        showToast('ロゴ読み込み完了', 'success');
    }

    /**
     * Load default logo from server
     */
    async function loadDefaultLogo() {
        if (_logoBytes) return; // Already loaded
        try {
            const resp = await fetch('/static/img/default_logo.png');
            if (resp.ok) {
                const buf = await resp.arrayBuffer();
                _logoBytes = new Uint8Array(buf);
                const preview = document.getElementById('logo-preview');
                if (preview) {
                    preview.innerHTML = '<span class="text-xs text-gray-500">デフォルトロゴ読み込み済み</span>';
                }
            }
        } catch (e) { /* ignore */ }
    }

    /**
     * Add branding overlay
     */
    async function applyBranding(options = {}) {
        // Load default logo if none uploaded
        if (!_logoBytes) await loadDefaultLogo();
        options.logoBytes = _logoBytes;

        // Parse targetPages string to array of ints (or null for all)
        if (typeof options.targetPages === 'string') {
            const parsed = PdfEngine.parsePageRange(options.targetPages);
            options.targetPages = parsed.length > 0 ? parsed : null;
        }

        console.log('[Branding] options:', {
            enableLogo: options.enableLogo,
            enablePageNum: options.enablePageNum,
            logoBytes: _logoBytes ? `${_logoBytes.length} bytes` : 'null',
            targetPages: options.targetPages,
        });

        try {
            await PdfEngine.addBranding(options);
            await renderThumbnails();
            updateFileInfo();
            if (typeof PdfStorage !== 'undefined' && PdfStorage.triggerAutoSave) PdfStorage.triggerAutoSave();
            showToast('ブランディング適用完了', 'success');
        } catch (e) {
            console.error('[Branding] error:', e);
            showToast('ブランディングエラー: ' + e.message, 'error');
        }
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
            showToast(`最適化完了: -${saved}% (${(before/1024).toFixed(0)}KB → ${(after/1024).toFixed(0)}KB)`, 'success');
        } else {
            showToast('既に最適化済みです', 'info');
        }
        await renderThumbnails();
        updateFileInfo();
        if (typeof PdfStorage !== 'undefined' && PdfStorage.triggerAutoSave) PdfStorage.triggerAutoSave();
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
                <p class="text-xs text-gray-500">${info.pageCount} ページ | ${info.fileSizeMB} MB</p>
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

    // =========================================
    // Page Selection System
    // =========================================
    const _selectedPages = new Set();

    /**
     * Get the set of currently selected page numbers
     */
    function getSelectedPages() {
        return new Set(_selectedPages);
    }

    /**
     * Update visual selection state on thumbnail cards and batch toolbar
     */
    function _updateSelectionUI() {
        const container = document.getElementById('preview-grid');
        if (!container) return;
        const cards = container.querySelectorAll('[data-page-num]');
        cards.forEach(card => {
            const pageNum = parseInt(card.dataset.pageNum);
            const isSelected = _selectedPages.has(pageNum);

            // Update border
            if (isSelected) {
                card.classList.remove('border-transparent', 'hover:border-yellow-500');
                card.classList.add('border-yellow-400', 'ring-2', 'ring-yellow-400');
            } else {
                card.classList.remove('border-yellow-400', 'ring-2', 'ring-yellow-400');
                card.classList.add('border-transparent', 'hover:border-yellow-500');
            }

            // Update checkbox
            const checkbox = card.querySelector('.batch-checkbox');
            if (checkbox) checkbox.checked = isSelected;

            // Update overlay
            const overlay = card.querySelector('.batch-select-overlay');
            if (overlay) overlay.classList.toggle('hidden', !isSelected);
        });

        // Update selection count badge
        const badge = document.getElementById('selection-count-badge');
        if (badge) {
            if (_selectedPages.size > 0) {
                badge.textContent = `${_selectedPages.size} 選択中`;
                badge.classList.remove('hidden');
            } else {
                badge.classList.add('hidden');
            }
        }

        _updateBatchToolbar();
    }

    /**
     * Update the batch operations toolbar visibility and content
     */
    function _updateBatchToolbar() {
        const toolbar = document.getElementById('batch-toolbar');
        if (!toolbar) return;

        const count = _selectedPages.size;
        if (count > 0) {
            toolbar.classList.remove('-translate-y-full', 'opacity-0', 'pointer-events-none');
            toolbar.classList.add('translate-y-0', 'opacity-100');
        } else {
            toolbar.classList.add('-translate-y-full', 'opacity-0', 'pointer-events-none');
            toolbar.classList.remove('translate-y-0', 'opacity-100');
        }

        const counter = document.getElementById('batch-count');
        if (counter) counter.textContent = `選択中: ${count} ページ`;

        const toggleBtn = document.getElementById('batch-toggle-all');
        if (toggleBtn) {
            const total = PdfEngine.isLoaded() ? PdfEngine.getPageCount() : 0;
            toggleBtn.textContent = (count >= total && total > 0) ? '選択解除' : '全選択';
        }
    }

    /**
     * Select a single page (clear others)
     */
    function selectPage(pageNum) {
        _selectedPages.clear();
        _selectedPages.add(pageNum);
        _updateSelectionUI();
    }

    /**
     * Toggle selection of a page (checkbox or Ctrl/Cmd+click)
     */
    function togglePageSelection(pageNum) {
        if (_selectedPages.has(pageNum)) {
            _selectedPages.delete(pageNum);
        } else {
            _selectedPages.add(pageNum);
        }
        _updateSelectionUI();
    }

    /**
     * Range select pages (Shift+click) from last selected to target
     */
    function rangeSelectTo(pageNum) {
        const existing = Array.from(_selectedPages).sort((a, b) => a - b);
        const anchor = existing.length > 0 ? existing[0] : 1;
        const start = Math.min(anchor, pageNum);
        const end = Math.max(anchor, pageNum);
        _selectedPages.clear();
        for (let i = start; i <= end; i++) {
            _selectedPages.add(i);
        }
        _updateSelectionUI();
    }

    /**
     * Select all pages
     */
    function selectAllPages() {
        if (!PdfEngine.isLoaded()) return;
        const count = PdfEngine.getPageCount();
        _selectedPages.clear();
        for (let i = 1; i <= count; i++) {
            _selectedPages.add(i);
        }
        _updateSelectionUI();
    }

    /**
     * Deselect all pages
     */
    function deselectAll() {
        _selectedPages.clear();
        _updateSelectionUI();
    }

    /**
     * Handle click on a page card for selection
     */
    function handlePageClick(event, pageNum) {
        const isMeta = event.metaKey || event.ctrlKey;
        const isShift = event.shiftKey;

        if (isShift) {
            rangeSelectTo(pageNum);
        } else if (isMeta) {
            togglePageSelection(pageNum);
        } else {
            selectPage(pageNum);
        }
    }

    /**
     * Navigate to next/previous page (arrow keys)
     */
    function navigatePage(direction) {
        if (!PdfEngine.isLoaded()) return;
        const count = PdfEngine.getPageCount();
        if (count === 0) return;

        const selected = Array.from(_selectedPages).sort((a, b) => a - b);
        let target;

        if (selected.length === 0) {
            target = direction > 0 ? 1 : count;
        } else if (direction > 0) {
            target = Math.min(selected[selected.length - 1] + 1, count);
        } else {
            target = Math.max(selected[0] - 1, 1);
        }

        selectPage(target);

        // Scroll selected card into view
        const container = document.getElementById('preview-grid');
        if (container) {
            const card = container.querySelector(`[data-page-num="${target}"]`);
            if (card) card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }

    /**
     * Toggle between select-all and deselect-all (for batch toolbar button)
     */
    function handleToggleAll() {
        const total = PdfEngine.isLoaded() ? PdfEngine.getPageCount() : 0;
        if (_selectedPages.size >= total && total > 0) {
            deselectAll();
        } else {
            selectAllPages();
        }
    }

    // =========================================
    // Batch Operations
    // =========================================

    /**
     * Delete all selected pages
     */
    async function batchDelete() {
        const pages = Array.from(_selectedPages).sort((a, b) => a - b);
        if (pages.length === 0) return;
        const total = PdfEngine.getPageCount();
        if (pages.length >= total) {
            showToast('すべてのページは削除できません', 'error');
            return;
        }
        if (!confirm(`${pages.length}ページを削除しますか？`)) return;
        await PdfEngine.removePages(pages);
        _selectedPages.clear();
        await renderThumbnails();
        updateFileInfo();
        if (typeof PdfStorage !== 'undefined' && PdfStorage.triggerAutoSave) PdfStorage.triggerAutoSave();
        showToast(`${pages.length}ページ削除完了`, 'success');
    }

    /**
     * Rotate all selected pages 90 degrees
     */
    async function batchRotate() {
        const pages = Array.from(_selectedPages).sort((a, b) => a - b);
        if (pages.length === 0) return;
        for (const p of pages) {
            await PdfEngine.rotatePage(p, 90);
        }
        _selectedPages.clear();
        await renderThumbnails();
        if (typeof PdfStorage !== 'undefined' && PdfStorage.triggerAutoSave) PdfStorage.triggerAutoSave();
        showToast(`${pages.length}ページ回転完了`, 'success');
    }

    // =========================================
    // Page Extraction
    // =========================================

    /**
     * Show the extract pages modal, pre-filling with selected pages if any
     */
    function showExtractModal() {
        if (!PdfEngine.isLoaded()) {
            showToast('PDFが読み込まれていません', 'error');
            return;
        }
        const modal = document.getElementById('extract-pages-modal');
        if (!modal) return;

        // Pre-fill with selected pages if any
        const input = document.getElementById('extract-range-input');
        if (input && _selectedPages.size > 0) {
            const sorted = Array.from(_selectedPages).sort((a, b) => a - b);
            input.value = _formatPageRange(sorted);
        } else if (input) {
            input.value = '';
        }

        // Update total pages display
        const totalEl = document.getElementById('extract-total-pages');
        if (totalEl) totalEl.textContent = PdfEngine.getPageCount();

        modal.classList.remove('hidden');
    }

    function hideExtractModal() {
        const modal = document.getElementById('extract-pages-modal');
        if (modal) modal.classList.add('hidden');
    }

    /**
     * Format an array of page numbers into a compact range string.
     * e.g., [1,2,3,5,7,8] -> "1-3,5,7-8"
     */
    function _formatPageRange(pages) {
        if (pages.length === 0) return '';
        const sorted = [...pages].sort((a, b) => a - b);
        const ranges = [];
        let start = sorted[0];
        let end = sorted[0];
        for (let i = 1; i < sorted.length; i++) {
            if (sorted[i] === end + 1) {
                end = sorted[i];
            } else {
                ranges.push(start === end ? `${start}` : `${start}-${end}`);
                start = sorted[i];
                end = sorted[i];
            }
        }
        ranges.push(start === end ? `${start}` : `${start}-${end}`);
        return ranges.join(',');
    }

    /**
     * Extract pages specified in the modal input and download as a new PDF
     */
    async function extractSelectedPages() {
        const input = document.getElementById('extract-range-input');
        if (!input || !input.value.trim()) {
            showToast('ページ範囲を指定してください', 'error');
            return;
        }
        const pages = PdfEngine.parsePageRange(input.value);
        if (pages.length === 0) {
            showToast('無効なページ指定です', 'error');
            return;
        }

        // Validate page numbers against total
        const total = PdfEngine.getPageCount();
        const invalid = pages.filter(p => p < 1 || p > total);
        if (invalid.length > 0) {
            showToast(`無効なページ番号: ${invalid.join(', ')} (全${total}ページ)`, 'error');
            return;
        }

        try {
            await PdfEngine.downloadExtractedPages(pages);
            hideExtractModal();
            showToast(`${pages.length}ページを抽出しました`, 'success');
        } catch (e) {
            console.error('[ExtractPages] error:', e);
            showToast('抽出エラー: ' + e.message, 'error');
        }
    }

    // =========================================
    // Keyboard Shortcuts Help
    // =========================================

    function showShortcutsHelp() {
        const modal = document.getElementById('shortcuts-help-modal');
        if (modal) modal.classList.remove('hidden');
    }

    function hideShortcutsHelp() {
        const modal = document.getElementById('shortcuts-help-modal');
        if (modal) modal.classList.add('hidden');
    }

    // =========================================
    // Keyboard Shortcut Handler
    // =========================================

    function _initKeyboardShortcuts() {
        document.addEventListener('keydown', async (e) => {
            // Skip if focus is in an input, textarea, or contenteditable
            const tag = e.target.tagName.toLowerCase();
            const isEditable = e.target.isContentEditable;
            if (tag === 'input' || tag === 'textarea' || tag === 'select' || isEditable) {
                return;
            }

            // Skip if PDF not loaded (except ? for help)
            const isMod = e.metaKey || e.ctrlKey;

            // ? — show shortcuts help
            if (e.key === '?' && !isMod) {
                e.preventDefault();
                const modal = document.getElementById('shortcuts-help-modal');
                if (modal && modal.classList.contains('hidden')) {
                    showShortcutsHelp();
                } else {
                    hideShortcutsHelp();
                }
                return;
            }

            // Escape — close help modal or deselect
            if (e.key === 'Escape') {
                const modal = document.getElementById('shortcuts-help-modal');
                if (modal && !modal.classList.contains('hidden')) {
                    hideShortcutsHelp();
                } else {
                    deselectAll();
                    showToast('選択解除', 'info');
                }
                return;
            }

            if (!PdfEngine.isLoaded()) return;

            // Ctrl/Cmd+Z — Undo
            if (isMod && e.key === 'z' && !e.shiftKey) {
                e.preventDefault();
                await undoAction();
                return;
            }

            // Ctrl/Cmd+S — Save/Download
            if (isMod && e.key === 's') {
                e.preventDefault();
                downloadPdf();
                return;
            }

            // Ctrl/Cmd+A — Select all
            if (isMod && e.key === 'a') {
                e.preventDefault();
                selectAllPages();
                showToast('全ページ選択', 'info');
                return;
            }

            // Delete / Backspace — Delete selected pages
            if (e.key === 'Delete' || e.key === 'Backspace') {
                if (_selectedPages.size === 0) {
                    showToast('ページが選択されていません', 'info');
                    return;
                }
                e.preventDefault();
                await batchDelete();
                return;
            }

            // R — Rotate selected pages
            if (e.key === 'r' || e.key === 'R') {
                if (_selectedPages.size === 0) {
                    showToast('ページが選択されていません', 'info');
                    return;
                }
                e.preventDefault();
                await batchRotate();
                return;
            }

            // Arrow Left — Previous page
            if (e.key === 'ArrowLeft') {
                e.preventDefault();
                navigatePage(-1);
                return;
            }

            // Arrow Right — Next page
            if (e.key === 'ArrowRight') {
                e.preventDefault();
                navigatePage(1);
                return;
            }
        });
    }

    /**
     * Insert a blank page after the given page number
     * @param {number} afterPageNum - 0 = beginning, pageCount = end
     */
    async function insertBlankPage(afterPageNum) {
        if (!PdfEngine.isLoaded()) {
            showToast('PDFが読み込まれていません', 'error');
            return;
        }
        try {
            await PdfEngine.addBlankPage(afterPageNum);
            _selectedPages.clear();
            await renderThumbnails();
            updateFileInfo();
            if (typeof PdfStorage !== 'undefined' && PdfStorage.triggerAutoSave) PdfStorage.triggerAutoSave();
            const pos = afterPageNum === 0 ? '先頭' : `ページ${afterPageNum}の後`;
            showToast(`空白ページ追加完了 (${pos})`, 'success');
        } catch (e) {
            console.error('[InsertBlankPage] error:', e);
            showToast('ページ追加失敗: ' + e.message, 'error');
        }
    }

    /**
     * Resize all pages to match the first page's dimensions
     */
    async function resizeToFirstPage() {
        if (!PdfEngine.isLoaded()) {
            showToast('PDFが読み込まれていません', 'error');
            return;
        }
        const count = PdfEngine.getPageCount();
        if (count < 2) {
            showToast('2ページ以上のPDFが必要です', 'info');
            return;
        }

        // Get first page size for confirmation dialog
        const size = await PdfEngine.getPageSize(1);
        const w = Math.round(size.width);
        const h = Math.round(size.height);
        if (!confirm(`1ページ目のサイズ (${w} x ${h} pt) に全ページを統一します。\nよろしいですか？`)) {
            return;
        }

        showToast('ページサイズ統一中...', 'info');
        try {
            const result = await PdfEngine.resizePages();
            await renderThumbnails();
            updateFileInfo();
            if (result.resizedCount === 0) {
                showToast('すべてのページが既に同じサイズです', 'info');
            } else {
                showToast(`${result.resizedCount}ページのサイズを統一しました (${Math.round(result.targetWidth)} x ${Math.round(result.targetHeight)} pt)`, 'success');
            }
        } catch (e) {
            console.error('[ResizePages] error:', e);
            showToast('サイズ統一エラー: ' + e.message, 'error');
        }
    }

    /**
     * Print pages with the selected mode.
     * - "grid" mode: prints thumbnail grid as-is
     * - "one-per-page" mode: re-renders at high resolution, one PDF page per print page
     */
    async function printPages() {
        if (!PdfEngine.isLoaded()) {
            showToast('PDFが読み込まれていません', 'error');
            return;
        }

        const modeSelect = document.getElementById('print-mode-select');
        const mode = modeSelect ? modeSelect.value : 'grid';
        const isOnePerPage = mode === 'one-per-page';

        // For one-per-page mode, re-render thumbnails at higher resolution
        if (isOnePerPage) {
            showToast('印刷用に高解像度で描画中...', 'info');
            const count = PdfEngine.getPageCount();
            const cards = document.querySelectorAll('#preview-grid .page-card');

            for (let i = 0; i < cards.length && i < count; i++) {
                const img = cards[i].querySelector('img');
                if (img) {
                    try {
                        const hiResUrl = await PdfEngine.getPageThumbnail(i + 1, 2.0);
                        img.src = hiResUrl;
                    } catch (e) {
                        console.warn('[Print] failed to render high-res for page', i + 1, e);
                    }
                }
            }

            // Wait for all images to load
            await Promise.all(
                Array.from(document.querySelectorAll('#preview-grid .page-card img')).map(img =>
                    img.complete ? Promise.resolve() : new Promise(resolve => {
                        img.onload = resolve;
                        img.onerror = resolve;
                    })
                )
            );

            document.body.classList.add('print-one-per-page');
        }

        // Clean up after print dialog closes
        const cleanup = () => {
            document.body.classList.remove('print-one-per-page');
            if (isOnePerPage) {
                // Restore normal-res thumbnails
                renderThumbnails();
            }
        };

        const afterPrintHandler = () => {
            window.removeEventListener('afterprint', afterPrintHandler);
            cleanup();
        };
        window.addEventListener('afterprint', afterPrintHandler);

        // Trigger print dialog
        window.print();
    }

    // Initialize keyboard shortcuts on load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', _initKeyboardShortcuts);
    } else {
        _initKeyboardShortcuts();
    }

    return {
        renderThumbnails,
        deletePage,
        deletePageRange,
        rotatePage,
        undoAction,
        downloadPdf,
        applyBranding,
        handleLogoUpload,
        loadDefaultLogo,
        optimizePdf,
        updateFileInfo,
        showToast,
        insertBlankPage,
        resizeToFirstPage,
        printPages,
        // Selection API
        selectPage,
        togglePageSelection,
        rangeSelectTo,
        selectAllPages,
        deselectAll,
        getSelectedPages,
        handlePageClick,
        handleToggleAll,
        navigatePage,
        // Batch operations
        batchDelete,
        batchRotate,
        // Shortcuts help
        showShortcutsHelp,
        hideShortcutsHelp,
        // Page extraction
        showExtractModal,
        hideExtractModal,
        extractSelectedPages,
    };
})();
