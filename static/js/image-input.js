/**
 * PDF Workshop Pro - Image Input Module
 * Manages image file uploads (PNG, JPEG, WebP, PSD) for the AI Workshop.
 * Provides drag-and-drop, preview thumbnails, and PSD decoding via psd.js.
 */

const ImageInput = (() => {
    let _images = []; // Array of { file, blob, dataUrl, name, type, size, originalType }
    let _dropZone = null;
    let _previewContainer = null;
    let _fileInput = null;
    let _onChangeCallback = null;

    const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
    const MAX_FILE_COUNT = 20;
    const SUPPORTED_TYPES = ['image/png', 'image/jpeg', 'image/webp'];
    const SUPPORTED_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp', 'psd'];
    const PSD_MIME_TYPES = ['application/octet-stream', 'image/vnd.adobe.photoshop'];
    const THUMBNAIL_MAX_WIDTH = 160;

    /**
     * Announce a message to screen readers via the aria-live region.
     * @param {string} message
     */
    function _announceStatus(message) {
        const statusEl = document.getElementById('image-upload-status');
        if (statusEl) {
            statusEl.textContent = message;
        }
    }

    /**
     * Show an error/info message via EditorUI.showToast if available, otherwise alert.
     * @param {string} message
     * @param {string} [type='error'] - Toast type (error, warning, info)
     */
    function _showMessage(message, type = 'error') {
        if (typeof EditorUI !== 'undefined' && EditorUI.showToast) {
            EditorUI.showToast(message, type);
        } else {
            alert(message);
        }
    }

    /**
     * Init: attach drag-and-drop and click handlers to a drop zone element.
     * @param {string} dropZoneId - ID of the drop zone element
     * @param {string} previewContainerId - ID of the preview container element
     * @param {Function} onChange - Callback invoked when images list changes
     */
    function init(dropZoneId, previewContainerId, onChange) {
        _dropZone = document.getElementById(dropZoneId);
        _previewContainer = document.getElementById(previewContainerId);
        _onChangeCallback = onChange || null;

        if (!_dropZone) {
            console.warn('ImageInput: drop zone not found:', dropZoneId);
            return;
        }

        // Create hidden file input
        _fileInput = document.createElement('input');
        _fileInput.type = 'file';
        _fileInput.multiple = true;
        _fileInput.accept = 'image/png,image/jpeg,image/webp,.psd';
        _fileInput.style.display = 'none';
        _dropZone.appendChild(_fileInput);

        // Click to open file picker
        _dropZone.addEventListener('click', (e) => {
            if (e.target.closest('.image-preview-remove')) return;
            _fileInput.click();
        });

        // Keyboard support: Enter/Space triggers file picker
        _dropZone.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                _fileInput.click();
            }
        });

        _fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                _processFiles(e.target.files);
            }
            _fileInput.value = '';
        });

        // Drag-and-drop handlers
        _dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.stopPropagation();
            _dropZone.classList.add('drag-over');
        });

        _dropZone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            e.stopPropagation();
            _dropZone.classList.remove('drag-over');
        });

        _dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            _dropZone.classList.remove('drag-over');
            if (e.dataTransfer.files.length > 0) {
                _processFiles(e.dataTransfer.files);
            }
        });
    }

    /**
     * Process files from input or drop.
     * @param {FileList} fileList
     */
    async function _processFiles(fileList) {
        const files = Array.from(fileList);

        // Max file count check
        const remaining = MAX_FILE_COUNT - _images.length;
        if (remaining <= 0) {
            _showMessage('画像は最大' + MAX_FILE_COUNT + '枚までです');
            return;
        }
        if (files.length > remaining) {
            _showMessage('画像は最大' + MAX_FILE_COUNT + '枚までです。あと' + remaining + '枚追加できます。');
            // Process only up to the limit
            files.length = remaining;
        }

        let errorMessages = [];

        for (const file of files) {
            const error = _validateFile(file);
            if (error) {
                console.warn('ImageInput: skipped file:', file.name, '-', error);
                errorMessages.push(file.name + ': ' + error);
                continue;
            }

            try {
                const blob = await prepareForAnalysis(file);
                let dataUrl;
                try {
                    dataUrl = await _createThumbnail(blob, THUMBNAIL_MAX_WIDTH);
                } catch (thumbErr) {
                    console.warn('ImageInput: thumbnail failed for', file.name, thumbErr);
                    // Use a placeholder for corrupt/unreadable images
                    dataUrl = _createErrorPlaceholder();
                }

                _images.push({
                    file,
                    blob,
                    dataUrl,
                    name: file.name,
                    type: blob.type,
                    size: file.size,
                    originalType: file.type || _guessTypeByExtension(file.name),
                });
            } catch (err) {
                console.error('ImageInput: failed to process file:', file.name, err);
                const isPsd = file.name.toLowerCase().endsWith('.psd');
                if (isPsd) {
                    errorMessages.push(file.name + ': PSDファイルの読み込みに失敗しました。別の形式で保存して再試行してください。');
                } else {
                    errorMessages.push(file.name + ': ファイルの処理に失敗しました');
                }
            }
        }

        if (errorMessages.length > 0) {
            _showMessage(errorMessages.join('\n'));
        }

        _renderPreviews();
        _announceStatus(_images.length + '枚の画像がアップロードされました');

        if (_onChangeCallback) {
            _onChangeCallback(_images.length);
        }
    }

    /**
     * Create a placeholder data URL for images that fail to load.
     * @returns {string} dataURL of a "?" placeholder
     */
    function _createErrorPlaceholder() {
        const canvas = document.createElement('canvas');
        canvas.width = 80;
        canvas.height = 80;
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = '#f8d7da';
        ctx.fillRect(0, 0, 80, 80);
        ctx.strokeStyle = '#dc3545';
        ctx.lineWidth = 2;
        ctx.strokeRect(1, 1, 78, 78);
        ctx.fillStyle = '#dc3545';
        ctx.font = 'bold 36px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('?', 40, 40);
        return canvas.toDataURL('image/png');
    }

    /**
     * Validate a single file: check format and size.
     * @param {File} file
     * @returns {string|null} Error message or null if valid
     */
    function _validateFile(file) {
        // Empty file check
        if (!file || file.size === 0) {
            return 'ファイルが空です';
        }

        // Size validation with actual size in message
        if (file.size > MAX_FILE_SIZE) {
            return 'ファイルサイズが10MBを超えています（実際のサイズ: ' + _formatSize(file.size) + '）';
        }

        // Extension validation
        const ext = file.name.toLowerCase().split('.').pop();
        if (!SUPPORTED_EXTENSIONS.includes(ext)) {
            return '対応していないファイル形式です (PNG, JPEG, WebP, PSD のみ)';
        }

        // MIME type validation
        const isPsd = ext === 'psd';
        if (isPsd) {
            // PSD files may report as application/octet-stream or image/vnd.adobe.photoshop
            if (file.type && !PSD_MIME_TYPES.includes(file.type)) {
                return 'PSDファイルのMIMEタイプが不正です: ' + file.type;
            }
        } else {
            // For non-PSD, MIME type must match supported types
            if (!SUPPORTED_TYPES.includes(file.type)) {
                return '対応していないファイル形式です (PNG, JPEG, WebP, PSD のみ)。MIMEタイプ: ' + file.type;
            }
        }

        return null;
    }

    /**
     * Guess MIME type by file extension.
     * @param {string} name
     * @returns {string}
     */
    function _guessTypeByExtension(name) {
        const ext = name.toLowerCase().split('.').pop();
        const map = { png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', webp: 'image/webp', psd: 'image/vnd.adobe.photoshop' };
        return map[ext] || 'application/octet-stream';
    }

    /**
     * Normalize any supported image to a Blob ready for API.
     * PNG/JPG/WebP: use as-is; PSD: decode to PNG via psd.js.
     * @param {File} file
     * @returns {Promise<Blob>}
     */
    async function prepareForAnalysis(file) {
        const isPsd = file.name.toLowerCase().endsWith('.psd') ||
                       file.type === 'application/octet-stream';

        if (isPsd) {
            return await decodePsd(file);
        }

        // PNG, JPEG, WebP — use as-is
        return file;
    }

    /**
     * Decode PSD file to PNG Blob using psd.js library.
     * @param {File} file
     * @returns {Promise<Blob>}
     */
    async function decodePsd(file) {
        if (typeof PSD === 'undefined') {
            throw new Error('psd.js が読み込まれていません');
        }

        try {
            const arrayBuffer = await file.arrayBuffer();
            const psd = new PSD(new Uint8Array(arrayBuffer));
            psd.parse();
            const canvas = psd.image.toCanvas();

            return new Promise((resolve, reject) => {
                canvas.toBlob(
                    (blob) => blob ? resolve(blob) : reject(new Error('PSD→PNG変換失敗')),
                    'image/png'
                );
            });
        } catch (err) {
            throw new Error('PSDファイルの読み込みに失敗しました。別の形式で保存して再試行してください。');
        }
    }

    /**
     * Create thumbnail dataURL for preview.
     * @param {Blob} blob
     * @param {number} maxWidth
     * @returns {Promise<string>} dataURL
     */
    async function _createThumbnail(blob, maxWidth = 160) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            const url = URL.createObjectURL(blob);

            img.onload = () => {
                URL.revokeObjectURL(url);

                let width = img.width;
                let height = img.height;

                if (width > maxWidth) {
                    height = Math.round(height * (maxWidth / width));
                    width = maxWidth;
                }

                const canvas = document.createElement('canvas');
                canvas.width = width;
                canvas.height = height;

                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, width, height);

                resolve(canvas.toDataURL('image/png'));
            };

            img.onerror = () => {
                URL.revokeObjectURL(url);
                reject(new Error('画像の読み込みに失敗しました'));
            };

            img.src = url;
        });
    }

    /**
     * Get all processed images.
     * @returns {Array} Copy of the images array
     */
    function getImages() {
        return [..._images];
    }

    /**
     * Remove image at index.
     * @param {number} index
     */
    function removeImage(index) {
        if (index >= 0 && index < _images.length) {
            _images.splice(index, 1);
            _renderPreviews();

            // Focus management: move focus to next thumbnail's delete button, or drop zone
            if (_previewContainer) {
                const buttons = _previewContainer.querySelectorAll('.image-preview-remove');
                if (buttons.length > 0) {
                    const focusIndex = Math.min(index, buttons.length - 1);
                    buttons[focusIndex].focus();
                } else if (_dropZone) {
                    _dropZone.focus();
                }
            }

            // Screen reader announcement
            if (_images.length > 0) {
                _announceStatus('画像を削除しました。残り' + _images.length + '枚');
            } else {
                _announceStatus('すべての画像が削除されました');
            }

            if (_onChangeCallback) {
                _onChangeCallback(_images.length);
            }
        }
    }

    /**
     * Clear all images.
     */
    function clearAll() {
        _images = [];
        _renderPreviews();
        _announceStatus('すべての画像が削除されました');

        if (_dropZone) {
            _dropZone.focus();
        }

        if (_onChangeCallback) {
            _onChangeCallback(0);
        }
    }

    /**
     * Get count of uploaded images.
     * @returns {number}
     */
    function getCount() {
        return _images.length;
    }

    /**
     * Format file size for display.
     * @param {number} bytes
     * @returns {string}
     */
    function _formatSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    /**
     * Render preview thumbnails into the preview container.
     */
    function _renderPreviews() {
        if (!_previewContainer) return;

        _previewContainer.innerHTML = '';

        _images.forEach((img, index) => {
            const card = document.createElement('div');
            card.className = 'image-preview-card';
            card.innerHTML =
                '<img src="' + img.dataUrl + '" alt="' + _escapeHtml(img.name) + '" class="image-preview-thumb">' +
                '<div class="image-preview-info">' +
                    '<span class="image-preview-name" title="' + _escapeHtml(img.name) + '">' + _escapeHtml(img.name) + '</span>' +
                    '<span class="image-preview-size">' + _formatSize(img.size) + '</span>' +
                '</div>' +
                '<button type="button" class="image-preview-remove" data-index="' + index + '" title="削除" aria-label="画像を削除: ' + _escapeHtml(img.name) + '">&times;</button>';

            card.querySelector('.image-preview-remove').addEventListener('click', (e) => {
                e.stopPropagation();
                removeImage(index);
            });

            _previewContainer.appendChild(card);
        });
    }

    /**
     * Escape HTML special characters.
     * @param {string} str
     * @returns {string}
     */
    function _escapeHtml(str) {
        const div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }

    /**
     * Validate images before analysis. Returns the images array or null if empty.
     * Shows an alert if no images are uploaded.
     * @returns {Array|null}
     */
    function analyzeUploadedImages() {
        if (_images.length === 0) {
            _showMessage('画像がアップロードされていません。分析するには画像を追加してください。', 'warning');
            return null;
        }
        return getImages();
    }

    return { init, getImages, removeImage, clearAll, getCount, decodePsd, prepareForAnalysis, analyzeUploadedImages };
})();
