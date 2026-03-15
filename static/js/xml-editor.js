/**
 * XmlEditor - 構造化XMLエディタモジュール
 *
 * XML解析、構造化エディタレンダリング、XML再構築を担当する。
 * PdfEngine, EditorUI, Sortable.js グローバルと連携して動作する。
 */
const XmlEditor = (() => {
    'use strict';

    // -------------------------------------------------------
    // Constants
    // -------------------------------------------------------

    const FONT_SIZES = [8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36, 42, 48, 54, 60, 72];

    const DEFAULT_FONT_SIZES = {
        title: 28,
        subtitle: 18,
        bullet: 14,
        charts: 12,
        notes: 10,
    };

    // Tailwind class constants
    const CLS_LABEL = 'text-xs font-medium text-gray-700 dark:text-gray-300';
    const CLS_INPUT = 'w-full px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200';
    const CLS_TEXTAREA = 'w-full px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 resize-y';
    const CLS_FONT_SELECT = 'w-16 text-xs px-1 py-1 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200';
    const CLS_BULLET_ITEM = 'flex items-center gap-1 mb-1 bullet-item';
    const CLS_SECTION_CONTAINER = 'ml-2 pl-3 border-l-2 border-gray-200 dark:border-gray-600 bullet-list';
    const CLS_BTN_DELETE = 'text-red-400 hover:text-red-600 p-1 text-xs';
    const CLS_BTN_MOVE = 'text-gray-400 hover:text-gray-600 p-1 text-xs';
    const CLS_BTN_ADD = 'text-xs text-blue-600 dark:text-blue-400 hover:underline mt-1';
    const CLS_SECTION_LABEL = 'text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider';

    // -------------------------------------------------------
    // Internal helpers - text extraction
    // -------------------------------------------------------

    /**
     * Get text content of a direct child element by tag name.
     * @param {Element} parent
     * @param {string} tagName
     * @returns {string}
     */
    function getTextContent(parent, tagName) {
        const el = parent.querySelector(':scope > ' + tagName)
                || parent.querySelector(tagName);
        return el ? el.textContent.trim() : '';
    }

    /**
     * Get font-size attribute value of a child element, with default fallback.
     * @param {Element} parent
     * @param {string} tagName
     * @param {number} defaultSize
     * @returns {number}
     */
    function getFontSize(parent, tagName, defaultSize) {
        const el = parent.querySelector(':scope > ' + tagName)
                || parent.querySelector(tagName);
        if (!el) return defaultSize;
        const fs = el.getAttribute('font-size');
        if (!fs) return defaultSize;
        const n = parseInt(fs, 10);
        return (n >= 8 && n <= 72) ? n : defaultSize;
    }

    /**
     * Parse all <section> elements inside <content>.
     * @param {Element} slide
     * @returns {Array<{name: string, bullets: Array<{text: string, fontSize: number}>}>}
     */
    function parseSections(slide) {
        const content = slide.querySelector('content');
        if (!content) return [];
        const sections = content.querySelectorAll('section');
        return Array.from(sections).map(sec => ({
            name: sec.getAttribute('name') || '',
            bullets: Array.from(sec.querySelectorAll('bullet')).map(b => ({
                text: b.textContent.trim(),
                fontSize: (() => {
                    const fs = b.getAttribute('font-size');
                    if (!fs) return DEFAULT_FONT_SIZES.bullet;
                    const n = parseInt(fs, 10);
                    return (n >= 8 && n <= 72) ? n : DEFAULT_FONT_SIZES.bullet;
                })(),
            })),
        }));
    }

    // -------------------------------------------------------
    // Escape utilities
    // -------------------------------------------------------

    /**
     * Escape special XML characters.
     * @param {string} str
     * @returns {string}
     */
    function escapeXml(str) {
        if (!str) return '';
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&apos;');
    }

    /**
     * Escape special characters for safe HTML attribute/content insertion.
     * Same set as escapeXml for HTML context.
     * @param {string} str
     * @returns {string}
     */
    function escapeHtml(str) {
        if (!str) return '';
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    // -------------------------------------------------------
    // Font size selector builder
    // -------------------------------------------------------

    /**
     * Build a font-size <select> element as an HTML string.
     * @param {number} currentSize
     * @param {Object} attrs - data-* attributes as key-value pairs
     * @returns {string} HTML string
     */
    function buildFontSizeSelect(currentSize, attrs) {
        const attrParts = Object.entries(attrs || {})
            .map(([k, v]) => `${escapeHtml(k)}="${escapeHtml(String(v))}"`)
            .join(' ');

        const options = FONT_SIZES.map(size => {
            const selected = size === currentSize ? ' selected' : '';
            return `<option value="${size}"${selected}>${size}</option>`;
        }).join('');

        return `<select class="${CLS_FONT_SELECT}" aria-label="フォントサイズ" ${attrParts}>${options}</select>`;
    }

    // -------------------------------------------------------
    // HTML builders
    // -------------------------------------------------------

    /**
     * Build HTML for a single bullet item.
     * @param {number} sectionIndex
     * @param {number} bulletIndex
     * @param {{text: string, fontSize: number}} bulletData
     * @param {number} pageNum
     * @returns {string}
     */
    function buildBulletHtml(sectionIndex, bulletIndex, bulletData, pageNum) {
        const fontSelect = buildFontSizeSelect(bulletData.fontSize, {
            'data-field': 'bulletFontSize',
            'data-section-index': sectionIndex,
            'data-bullet-index': bulletIndex,
            'data-page': pageNum,
        });

        return `<div class="${CLS_BULLET_ITEM}" data-bullet-index="${bulletIndex}" role="listitem">
            ${fontSelect}
            <input type="text"
                   data-field="bulletText"
                   data-section-index="${sectionIndex}"
                   data-bullet-index="${bulletIndex}"
                   data-page="${pageNum}"
                   value="${escapeHtml(bulletData.text)}"
                   class="flex-1 px-2 py-1 text-sm rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200"
                   placeholder="箇条書きテキスト" />
            <button data-action="deleteBullet"
                    data-section-index="${sectionIndex}"
                    data-bullet-index="${bulletIndex}"
                    class="${CLS_BTN_DELETE} bullet-action-btn"
                    title="削除"
                    aria-label="箇条書き削除">&times;</button>
            <button data-action="moveBulletUp"
                    data-section-index="${sectionIndex}"
                    data-bullet-index="${bulletIndex}"
                    class="${CLS_BTN_MOVE} bullet-action-btn"
                    title="上へ"
                    aria-label="上へ移動">&uarr;</button>
            <button data-action="moveBulletDown"
                    data-section-index="${sectionIndex}"
                    data-bullet-index="${bulletIndex}"
                    class="${CLS_BTN_MOVE} bullet-action-btn"
                    title="下へ"
                    aria-label="下へ移動">&darr;</button>
        </div>`;
    }

    /**
     * Build HTML for a complete section (header + bullets + add button).
     * @param {number} sectionIndex
     * @param {number} pageNum
     * @param {{name: string, bullets: Array}} sectionData
     * @returns {string}
     */
    function buildSectionHtml(sectionIndex, pageNum, sectionData) {
        const bulletsHtml = sectionData.bullets.map((b, bi) =>
            buildBulletHtml(sectionIndex, bi, b, pageNum)
        ).join('');

        return `<div class="mb-3" data-section-index="${sectionIndex}">
            <div class="flex items-center gap-2 mb-1">
                <span class="${CLS_SECTION_LABEL}">セクション:</span>
                <input type="text"
                       data-page="${pageNum}"
                       data-field="sectionName"
                       data-section-index="${sectionIndex}"
                       value="${escapeHtml(sectionData.name)}"
                       class="flex-1 px-2 py-1 text-xs rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200"
                       placeholder="セクション名" />
                <button data-action="deleteSection"
                        data-section-index="${sectionIndex}"
                        class="${CLS_BTN_DELETE}"
                        aria-label="セクション削除">削除</button>
            </div>
            <div class="${CLS_SECTION_CONTAINER}"
                 data-section-index="${sectionIndex}"
                 role="group"
                 aria-label="セクション: ${escapeHtml(sectionData.name)}">
                ${bulletsHtml}
                <button data-action="addBullet"
                        data-section-index="${sectionIndex}"
                        class="${CLS_BTN_ADD}"
                        aria-label="箇条書き追加">+ 箇条書き追加</button>
            </div>
        </div>`;
    }

    /**
     * Build a single-line field with optional font-size selector.
     * @param {string} label - Japanese label text
     * @param {string} fieldName - data-field value
     * @param {string} value - current value
     * @param {number} pageNum
     * @param {number|null} fontSize - current font size or null if no selector
     * @param {string|null} fontSizeField - data-field for font size select
     * @returns {string}
     */
    function buildTextField(label, fieldName, value, pageNum, fontSize, fontSizeField) {
        const fontSelectHtml = (fontSize !== null && fontSizeField)
            ? buildFontSizeSelect(fontSize, {
                'data-page': pageNum,
                'data-field': fontSizeField,
            })
            : '';

        return `<div class="mb-3">
            <div class="flex items-center justify-between mb-1">
                <label class="${CLS_LABEL}">${escapeHtml(label)}</label>
                ${fontSelectHtml}
            </div>
            <input type="text"
                   data-page="${pageNum}"
                   data-field="${escapeHtml(fieldName)}"
                   value="${escapeHtml(value)}"
                   class="${CLS_INPUT}" />
        </div>`;
    }

    /**
     * Build a textarea field with optional font-size selector.
     * @param {string} label
     * @param {string} fieldName
     * @param {string} value
     * @param {number} pageNum
     * @param {number|null} fontSize
     * @param {string|null} fontSizeField
     * @returns {string}
     */
    function buildTextareaField(label, fieldName, value, pageNum, fontSize, fontSizeField) {
        const fontSelectHtml = (fontSize !== null && fontSizeField)
            ? buildFontSizeSelect(fontSize, {
                'data-page': pageNum,
                'data-field': fontSizeField,
            })
            : '';

        return `<div class="mb-3">
            <div class="flex items-center justify-between mb-1">
                <label class="${CLS_LABEL}">${escapeHtml(label)}</label>
                ${fontSelectHtml}
            </div>
            <textarea data-page="${pageNum}"
                      data-field="${escapeHtml(fieldName)}"
                      rows="2"
                      class="${CLS_TEXTAREA}">${escapeHtml(value)}</textarea>
        </div>`;
    }

    // -------------------------------------------------------
    // Public: parseXml
    // -------------------------------------------------------

    /**
     * Parse an XML string into a SlideData object.
     * @param {string} xmlString
     * @returns {Object} SlideData
     */
    function parseXml(xmlString) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(xmlString, 'text/xml');

        // Check for parse errors
        const parseError = doc.querySelector('parsererror');
        if (parseError) {
            throw new Error('XMLパースエラー: ' + parseError.textContent);
        }

        // Get <slide> root element
        const slide = doc.querySelector('slide');
        if (!slide) {
            throw new Error('<slide>要素が見つかりません');
        }

        return {
            title: getTextContent(slide, 'title'),
            titleFontSize: getFontSize(slide, 'title', DEFAULT_FONT_SIZES.title),
            subtitle: getTextContent(slide, 'subtitle'),
            subtitleFontSize: getFontSize(slide, 'subtitle', DEFAULT_FONT_SIZES.subtitle),
            sections: parseSections(slide),
            charts: getTextContent(slide, 'charts'),
            chartsFontSize: getFontSize(slide, 'charts', DEFAULT_FONT_SIZES.charts),
            images: getTextContent(slide, 'images'),
            layout: getTextContent(slide, 'layout'),
            colorScheme: getTextContent(slide, 'color_scheme'),
            notes: getTextContent(slide, 'notes'),
            notesFontSize: getFontSize(slide, 'notes', DEFAULT_FONT_SIZES.notes),
        };
    }

    // -------------------------------------------------------
    // Public: renderEditor
    // -------------------------------------------------------

    /**
     * Render the structured editor form into a container element.
     * @param {Object} data - SlideData object
     * @param {string} containerId - DOM id of the container
     * @param {number} pageNum - page number
     */
    function renderEditor(data, containerId, pageNum) {
        const container = document.getElementById(containerId);
        if (!container) return;

        let html = '';

        // Title
        html += buildTextField('タイトル', 'title', data.title, pageNum, data.titleFontSize, 'titleFontSize');

        // Subtitle
        html += buildTextField('サブタイトル', 'subtitle', data.subtitle, pageNum, data.subtitleFontSize, 'subtitleFontSize');

        // Content sections divider
        html += `<div class="mb-2 mt-4 flex items-center gap-2">
            <span class="${CLS_SECTION_LABEL}">コンテンツ</span>
            <span class="flex-1 border-t border-gray-200 dark:border-gray-600"></span>
        </div>`;

        // Sections
        data.sections.forEach((sec, si) => {
            html += buildSectionHtml(si, pageNum, sec);
        });

        // Add section button
        html += `<button data-action="addSection"
                         class="${CLS_BTN_ADD} block mb-4"
                         aria-label="セクション追加">+ セクション追加</button>`;

        // Other fields divider
        html += `<div class="mb-2 mt-2 flex items-center gap-2">
            <span class="${CLS_SECTION_LABEL}">その他</span>
            <span class="flex-1 border-t border-gray-200 dark:border-gray-600"></span>
        </div>`;

        // Charts (with font-size)
        html += buildTextareaField('グラフ・チャート', 'charts', data.charts, pageNum, data.chartsFontSize, 'chartsFontSize');

        // Images (no font-size)
        html += buildTextareaField('画像・図形', 'images', data.images, pageNum, null, null);

        // Layout (no font-size)
        html += buildTextareaField('レイアウト', 'layout', data.layout, pageNum, null, null);

        // Color scheme (no font-size)
        html += buildTextareaField('配色', 'colorScheme', data.colorScheme, pageNum, null, null);

        // Notes (with font-size)
        html += buildTextareaField('備考', 'notes', data.notes, pageNum, data.notesFontSize, 'notesFontSize');

        // Set the HTML
        container.innerHTML = html;

        // Attach event listeners via delegation
        attachEventListeners(containerId, pageNum);

        // Initialize Sortable.js on bullet lists
        initSortable(container);

        // Attach IME-aware Enter key handling on bullet inputs
        attachBulletKeyHandlers(container, pageNum);
    }

    // -------------------------------------------------------
    // Public: collectToXml
    // -------------------------------------------------------

    /**
     * Collect form values from the structured editor and build an XML string.
     * @param {string} containerId
     * @param {number} pageNum
     * @returns {string} XML string
     */
    function collectToXml(containerId, pageNum) {
        const container = document.getElementById(containerId);
        if (!container) return '<slide></slide>';

        const get = (field) => {
            const el = container.querySelector(`[data-field="${field}"][data-page="${pageNum}"]`);
            return el ? el.value : '';
        };
        const getFs = (field) => {
            const el = container.querySelector(`[data-field="${field}"][data-page="${pageNum}"]`);
            return el ? el.value : '';
        };

        let xml = '<slide>\n';

        // title
        const titleFs = getFs('titleFontSize');
        xml += `  <title${titleFs ? ` font-size="${titleFs}"` : ''}>${escapeXml(get('title'))}</title>\n`;

        // subtitle
        const subtitleFs = getFs('subtitleFontSize');
        xml += `  <subtitle${subtitleFs ? ` font-size="${subtitleFs}"` : ''}>${escapeXml(get('subtitle'))}</subtitle>\n`;

        // content > sections
        xml += '  <content>\n';

        const processedSections = new Set();
        const allSectionEls = container.querySelectorAll('[data-section-index]');
        allSectionEls.forEach(el => {
            const si = el.getAttribute('data-section-index');
            if (processedSections.has(si)) return;

            // Only process elements that have a section name input
            const nameInput = container.querySelector(
                `[data-field="sectionName"][data-section-index="${si}"]`
            );
            if (!nameInput) return;
            processedSections.add(si);

            xml += `    <section name="${escapeXml(nameInput.value)}">\n`;

            const bulletList = container.querySelector(
                `.bullet-list[data-section-index="${si}"]`
            );
            if (bulletList) {
                const bullets = bulletList.querySelectorAll('.bullet-item');
                bullets.forEach(bulletEl => {
                    const textEl = bulletEl.querySelector('[data-field="bulletText"]');
                    const fsEl = bulletEl.querySelector('[data-field="bulletFontSize"]');
                    const text = textEl ? textEl.value : '';
                    const fs = fsEl ? fsEl.value : String(DEFAULT_FONT_SIZES.bullet);
                    xml += `      <bullet font-size="${fs}">${escapeXml(text)}</bullet>\n`;
                });
            }

            xml += '    </section>\n';
        });

        xml += '  </content>\n';

        // charts
        const chartsFs = getFs('chartsFontSize');
        xml += `  <charts${chartsFs ? ` font-size="${chartsFs}"` : ''}>${escapeXml(get('charts'))}</charts>\n`;

        // images, layout, color_scheme (no font-size)
        xml += `  <images>${escapeXml(get('images'))}</images>\n`;
        xml += `  <layout>${escapeXml(get('layout'))}</layout>\n`;
        xml += `  <color_scheme>${escapeXml(get('colorScheme'))}</color_scheme>\n`;

        // notes
        const notesFs = getFs('notesFontSize');
        xml += `  <notes${notesFs ? ` font-size="${notesFs}"` : ''}>${escapeXml(get('notes'))}</notes>\n`;

        xml += '</slide>';
        return xml;
    }

    // -------------------------------------------------------
    // Public: extractXmlFromResponse
    // -------------------------------------------------------

    /**
     * Strip markdown code fences and extract <slide>...</slide> from raw text.
     * @param {string} rawText
     * @returns {string}
     */
    function extractXmlFromResponse(rawText) {
        if (!rawText) return rawText;

        // Remove markdown ```xml ... ``` blocks
        let text = rawText.replace(/^```(?:xml)?\s*\n?/gm, '').replace(/\n?```\s*$/gm, '');

        // Extract <slide>...</slide>
        const match = text.match(/<slide[\s>][\s\S]*<\/slide>/);
        if (match) return match[0];

        // If not found, return cleaned text (will trigger parse error downstream)
        return text;
    }

    // -------------------------------------------------------
    // Public: initSortable
    // -------------------------------------------------------

    /**
     * Initialize Sortable.js on all .bullet-list elements within a container.
     * @param {HTMLElement} container
     */
    function initSortable(container) {
        if (typeof Sortable === 'undefined') return;

        container.querySelectorAll('.bullet-list').forEach(list => {
            // Destroy existing Sortable instance if present
            if (list._sortableInstance) {
                list._sortableInstance.destroy();
            }

            list._sortableInstance = new Sortable(list, {
                animation: 150,
                handle: '.bullet-item',
                ghostClass: 'sortable-ghost',
                dragClass: 'sortable-drag',
                filter: '[data-action="addBullet"]', // Exclude add button from dragging
                onEnd: () => reindexBullets(list),
            });
        });
    }

    // -------------------------------------------------------
    // Section operations
    // -------------------------------------------------------

    /**
     * Add a new section before the "add section" button.
     * @param {HTMLElement} container
     * @param {number} pageNum
     */
    function addSection(container, pageNum) {
        const existingIndices = new Set();
        container.querySelectorAll('[data-section-index]').forEach(el => {
            existingIndices.add(parseInt(el.dataset.sectionIndex, 10));
        });
        const newIndex = existingIndices.size > 0
            ? Math.max(...existingIndices) + 1
            : 0;

        const sectionHtml = buildSectionHtml(newIndex, pageNum, {
            name: '新しいセクション',
            bullets: [{ text: '', fontSize: DEFAULT_FONT_SIZES.bullet }],
        });

        const addSectionBtn = container.querySelector('[data-action="addSection"]');
        if (addSectionBtn) {
            addSectionBtn.insertAdjacentHTML('beforebegin', sectionHtml);
        }

        // Re-initialize Sortable on new bullet list
        initSortable(container);

        // Attach IME handlers for the new bullet inputs
        attachBulletKeyHandlers(container, pageNum);
    }

    /**
     * Delete a section and all its content.
     * @param {HTMLElement} container
     * @param {number} sectionIndex
     */
    function deleteSection(container, sectionIndex) {
        const els = container.querySelectorAll(`[data-section-index="${sectionIndex}"]`);
        const toRemove = [];

        els.forEach(el => {
            // Only remove top-level section elements (avoid removing children twice)
            if (!el.parentElement.hasAttribute('data-section-index') ||
                el.parentElement.dataset.sectionIndex !== String(sectionIndex)) {
                toRemove.push(el);
            }
        });

        toRemove.forEach(el => el.remove());
    }

    // -------------------------------------------------------
    // Bullet operations
    // -------------------------------------------------------

    /**
     * Add a new bullet to the end of a section's bullet list.
     * @param {HTMLElement} container
     * @param {number} sectionIndex
     */
    function addBullet(container, sectionIndex) {
        const list = container.querySelector(`.bullet-list[data-section-index="${sectionIndex}"]`);
        if (!list) return;

        const bullets = list.querySelectorAll('.bullet-item');
        const newIndex = bullets.length;

        // Determine pageNum from an existing element
        const pageEl = container.querySelector('[data-page]');
        const pageNum = pageEl ? parseInt(pageEl.dataset.page, 10) : 0;

        const bulletHtml = buildBulletHtml(sectionIndex, newIndex, {
            text: '',
            fontSize: DEFAULT_FONT_SIZES.bullet,
        }, pageNum);

        const addBtn = list.querySelector('[data-action="addBullet"]');
        if (addBtn) {
            addBtn.insertAdjacentHTML('beforebegin', bulletHtml);
        }

        // Focus the new input
        const newItems = list.querySelectorAll('.bullet-item');
        const lastItem = newItems[newItems.length - 1];
        if (lastItem) {
            const input = lastItem.querySelector('[data-field="bulletText"]');
            if (input) input.focus();
        }

        // Attach IME handler for the new input
        attachBulletKeyHandlers(container, pageNum);
    }

    /**
     * Add a new bullet after a specific bullet index in a section.
     * @param {HTMLElement} container
     * @param {number} sectionIndex
     * @param {number} bulletIndex
     */
    function addBulletAfter(container, sectionIndex, bulletIndex) {
        const list = container.querySelector(`.bullet-list[data-section-index="${sectionIndex}"]`);
        if (!list) return;

        const pageEl = container.querySelector('[data-page]');
        const pageNum = pageEl ? parseInt(pageEl.dataset.page, 10) : 0;

        const items = list.querySelectorAll('.bullet-item');
        const newIndex = items.length;

        const bulletHtml = buildBulletHtml(sectionIndex, newIndex, {
            text: '',
            fontSize: DEFAULT_FONT_SIZES.bullet,
        }, pageNum);

        const currentItem = list.querySelector(`.bullet-item[data-bullet-index="${bulletIndex}"]`);
        if (currentItem) {
            currentItem.insertAdjacentHTML('afterend', bulletHtml);
        } else {
            const addBtn = list.querySelector('[data-action="addBullet"]');
            if (addBtn) {
                addBtn.insertAdjacentHTML('beforebegin', bulletHtml);
            }
        }

        // Reindex all bullets
        reindexBullets(list);

        // Focus the new input (it is now at bulletIndex + 1)
        const updatedItems = list.querySelectorAll('.bullet-item');
        const newItem = updatedItems[bulletIndex + 1];
        if (newItem) {
            const input = newItem.querySelector('[data-field="bulletText"]');
            if (input) input.focus();
        }

        // Attach IME handler for new inputs
        attachBulletKeyHandlers(container, pageNum);
    }

    /**
     * Delete a bullet from a section.
     * @param {HTMLElement} container
     * @param {number} sectionIndex
     * @param {number} bulletIndex
     */
    function deleteBullet(container, sectionIndex, bulletIndex) {
        const list = container.querySelector(`.bullet-list[data-section-index="${sectionIndex}"]`);
        if (!list) return;

        const item = list.querySelector(`.bullet-item[data-bullet-index="${bulletIndex}"]`);
        if (item) {
            item.remove();
            reindexBullets(list);
        }
    }

    /**
     * Move a bullet up or down within its section.
     * @param {HTMLElement} container
     * @param {number} sectionIndex
     * @param {number} bulletIndex
     * @param {number} direction - -1 for up, 1 for down
     */
    function moveBullet(container, sectionIndex, bulletIndex, direction) {
        const list = container.querySelector(`.bullet-list[data-section-index="${sectionIndex}"]`);
        if (!list) return;

        const items = Array.from(list.querySelectorAll('.bullet-item'));
        const currentItem = items[bulletIndex];
        if (!currentItem) return;

        const targetIndex = bulletIndex + direction;
        if (targetIndex < 0 || targetIndex >= items.length) return;

        const targetItem = items[targetIndex];

        if (direction === -1) {
            list.insertBefore(currentItem, targetItem);
        } else {
            list.insertBefore(targetItem, currentItem);
        }

        reindexBullets(list);
    }

    /**
     * Re-assign data-bullet-index attributes after reorder.
     * @param {HTMLElement} listEl
     */
    function reindexBullets(listEl) {
        listEl.querySelectorAll('.bullet-item').forEach((item, index) => {
            item.setAttribute('data-bullet-index', index);
            item.querySelectorAll('[data-bullet-index]').forEach(child => {
                child.setAttribute('data-bullet-index', index);
            });
        });
    }

    // -------------------------------------------------------
    // Event delegation
    // -------------------------------------------------------

    /**
     * Attach a single delegated event listener on the container for all button actions.
     * @param {string} containerId
     * @param {number} pageNum
     */
    function attachEventListeners(containerId, pageNum) {
        const container = document.getElementById(containerId);
        if (!container) return;

        // Remove previous listener if set (avoid duplicates on re-render)
        if (container._xmlEditorClickHandler) {
            container.removeEventListener('click', container._xmlEditorClickHandler);
        }

        const handler = (e) => {
            const btn = e.target.closest('[data-action]');
            if (!btn) return;

            const action = btn.dataset.action;
            const si = parseInt(btn.dataset.sectionIndex, 10);
            const bi = parseInt(btn.dataset.bulletIndex, 10);

            switch (action) {
                case 'addBullet':
                    addBullet(container, si);
                    break;
                case 'deleteBullet':
                    deleteBullet(container, si, bi);
                    break;
                case 'moveBulletUp':
                    moveBullet(container, si, bi, -1);
                    break;
                case 'moveBulletDown':
                    moveBullet(container, si, bi, 1);
                    break;
                case 'addSection':
                    addSection(container, pageNum);
                    break;
                case 'deleteSection':
                    if (confirm('このセクションを削除しますか？')) {
                        deleteSection(container, si);
                    }
                    break;
            }
        };

        container._xmlEditorClickHandler = handler;
        container.addEventListener('click', handler);
    }

    // -------------------------------------------------------
    // IME-aware Enter key handling for bullets
    // -------------------------------------------------------

    /**
     * Attach keydown handlers on all bullet text inputs for Enter key
     * (adds new bullet after current one, respecting IME composition).
     * @param {HTMLElement} container
     * @param {number} pageNum
     */
    function attachBulletKeyHandlers(container, pageNum) {
        const inputs = container.querySelectorAll('[data-field="bulletText"]');
        inputs.forEach(inputEl => {
            // Avoid attaching duplicate handlers
            if (inputEl._imeHandlerAttached) return;
            inputEl._imeHandlerAttached = true;

            inputEl.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.isComposing) {
                    e.preventDefault();
                    const si = parseInt(inputEl.dataset.sectionIndex, 10);
                    const bi = parseInt(inputEl.dataset.bulletIndex, 10);
                    addBulletAfter(container, si, bi);
                }
            });
        });
    }

    // -------------------------------------------------------
    // Public API
    // -------------------------------------------------------

    return {
        parseXml,
        renderEditor,
        collectToXml,
        extractXmlFromResponse,
        initSortable,
    };
})();
