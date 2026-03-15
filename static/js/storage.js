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
    };
})();
