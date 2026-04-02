/**
 * PDF Workshop Pro - Client-Side Storage (IndexedDB via Dexie.js)
 * Stores PDF files, edit history, and settings locally in the browser.
 * No data is sent to the server.
 */

const PdfStorage = (() => {
    // Dexie.js is loaded via CDN
    const db = new Dexie('PdfWorkshopPro');

    db.version(1).stores({
        files: '++id, name, createdAt, updatedAt',
        settings: 'key',
    });

    /**
     * Save a PDF file to IndexedDB
     * @returns {number} The auto-generated file ID
     */
    async function saveFile(name, bytes) {
        const now = new Date();
        const id = await db.files.add({
            name,
            bytes: new Uint8Array(bytes),
            createdAt: now,
            updatedAt: now,
        });
        return id;
    }

    /**
     * Update an existing file
     */
    async function updateFile(id, bytes) {
        await db.files.update(id, {
            bytes: new Uint8Array(bytes),
            updatedAt: new Date(),
        });
    }

    /**
     * Get a file by ID
     */
    async function getFile(id) {
        return await db.files.get(id);
    }

    /**
     * List all saved files (without bytes for performance)
     */
    async function listFiles() {
        const files = await db.files.toArray();
        return files.map(f => ({
            id: f.id,
            name: f.name,
            size: f.bytes ? f.bytes.length : 0,
            sizeMB: f.bytes ? (f.bytes.length / 1024 / 1024).toFixed(2) : '0',
            createdAt: f.createdAt,
            updatedAt: f.updatedAt,
        }));
    }

    /**
     * Delete a file
     */
    async function deleteFile(id) {
        await db.files.delete(id);
    }

    /**
     * Delete all files
     */
    async function clearAll() {
        await db.files.clear();
    }

    /**
     * Delete files older than maxAge (default: 7 days)
     */
    async function cleanupOld(maxAgeDays = 7) {
        const cutoff = new Date();
        cutoff.setDate(cutoff.getDate() - maxAgeDays);
        const count = await db.files.where('updatedAt').below(cutoff).delete();
        return count;
    }

    /**
     * Get total storage usage
     */
    async function getStorageUsage() {
        if (navigator.storage && navigator.storage.estimate) {
            const est = await navigator.storage.estimate();
            return {
                used: est.usage || 0,
                usedMB: ((est.usage || 0) / 1024 / 1024).toFixed(2),
                quota: est.quota || 0,
                quotaMB: ((est.quota || 0) / 1024 / 1024).toFixed(0),
                percentUsed: est.quota ? ((est.usage / est.quota) * 100).toFixed(1) : '0',
            };
        }
        return null;
    }

    /**
     * Save a setting
     */
    async function setSetting(key, value) {
        await db.settings.put({ key, value });
    }

    /**
     * Get a setting
     */
    async function getSetting(key, defaultValue = null) {
        const record = await db.settings.get(key);
        return record ? record.value : defaultValue;
    }

    // --- Auto-save functionality ---

    const AUTOSAVE_KEY = 'autosave';
    let _autoSaveTimer = null;
    let _debounceTimer = null;
    let _isDirty = false;
    let _isSaving = false;

    /**
     * Mark the document as dirty (has unsaved changes)
     */
    function markDirty() {
        _isDirty = true;
    }

    /**
     * Save the current PDF state to IndexedDB as an auto-save entry.
     * Only saves if a PDF is loaded and dirty.
     */
    async function _performAutoSave() {
        if (_isSaving) return;
        if (!_isDirty) return;
        if (typeof PdfEngine === 'undefined' || !PdfEngine.isLoaded()) return;

        _isSaving = true;
        try {
            const bytes = PdfEngine.getCurrentBytes();
            const info = PdfEngine.getFileInfo();
            await db.settings.put({
                key: AUTOSAVE_KEY,
                value: {
                    bytes: new Uint8Array(bytes),
                    fileName: info.fileName,
                    pageCount: info.pageCount,
                    lastModified: new Date().toISOString(),
                },
            });
            _isDirty = false;
            _showAutoSaveIndicator();
        } catch (e) {
            if (e.name === 'QuotaExceededError' || (e.inner && e.inner.name === 'QuotaExceededError')) {
                console.warn('[AutoSave] Storage quota exceeded. Skipping auto-save.');
            } else {
                console.warn('[AutoSave] Failed:', e);
            }
        } finally {
            _isSaving = false;
        }
    }

    /**
     * Show a subtle "自動保存完了" indicator that fades out after 2 seconds
     */
    function _showAutoSaveIndicator() {
        let indicator = document.getElementById('autosave-indicator');
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.id = 'autosave-indicator';
            indicator.style.cssText = 'position:fixed;bottom:16px;left:16px;background:rgba(34,197,94,0.9);color:#fff;padding:6px 14px;border-radius:8px;font-size:13px;z-index:9999;transition:opacity 0.5s;pointer-events:none;';
            document.body.appendChild(indicator);
        }
        indicator.textContent = '自動保存完了';
        indicator.style.opacity = '1';
        setTimeout(() => {
            indicator.style.opacity = '0';
        }, 2000);
    }

    /**
     * Start periodic auto-saving
     * @param {number} intervalMs - save interval in milliseconds (default 30s)
     */
    function startAutoSave(intervalMs = 30000) {
        stopAutoSave();
        _autoSaveTimer = setInterval(() => {
            _performAutoSave();
        }, intervalMs);
    }

    /**
     * Stop periodic auto-saving
     */
    function stopAutoSave() {
        if (_autoSaveTimer) {
            clearInterval(_autoSaveTimer);
            _autoSaveTimer = null;
        }
        if (_debounceTimer) {
            clearTimeout(_debounceTimer);
            _debounceTimer = null;
        }
    }

    /**
     * Trigger a debounced auto-save (500ms debounce).
     * Call this after every edit operation.
     */
    function triggerAutoSave() {
        _isDirty = true;
        if (_debounceTimer) {
            clearTimeout(_debounceTimer);
        }
        _debounceTimer = setTimeout(() => {
            _debounceTimer = null;
            _performAutoSave();
        }, 500);
    }

    /**
     * Get the auto-saved file data, if any
     * @returns {object|null} { bytes, fileName, pageCount, lastModified } or null
     */
    async function getAutoSave() {
        try {
            const record = await db.settings.get(AUTOSAVE_KEY);
            return record ? record.value : null;
        } catch (e) {
            console.warn('[AutoSave] Failed to read:', e);
            return null;
        }
    }

    /**
     * Clear the auto-saved data
     */
    async function clearAutoSave() {
        try {
            await db.settings.delete(AUTOSAVE_KEY);
        } catch (e) {
            console.warn('[AutoSave] Failed to clear:', e);
        }
    }

    return {
        saveFile,
        updateFile,
        getFile,
        listFiles,
        deleteFile,
        clearAll,
        cleanupOld,
        getStorageUsage,
        setSetting,
        getSetting,
        // Auto-save
        startAutoSave,
        stopAutoSave,
        triggerAutoSave,
        markDirty,
        getAutoSave,
        clearAutoSave,
    };
})();
