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

    const FONT_SIZES = [6, 7, 8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36, 42, 48, 54, 60, 72];

    // -------------------------------------------------------
    // Slide Templates
    // -------------------------------------------------------

    const SLIDE_TEMPLATES = {
        'title-slide': {
            id: 'title-slide',
            name: 'タイトルスライド',
            icon: '🎯',
            description: '大きなタイトルとサブタイトルのみ',
            xml: '<slide>\n  <title font-size="48">プレゼンテーションタイトル</title>\n  <subtitle font-size="28">サブタイトル・発表者名</subtitle>\n  <content>\n  </content>\n  <charts></charts>\n  <images></images>\n  <layout>中央寄せ、タイトルを大きく表示</layout>\n  <color_scheme>background: #1B2A4A, text: #FFFFFF</color_scheme>\n  <notes font-size="9"></notes>\n</slide>'
        },
        'content-slide': {
            id: 'content-slide',
            name: 'コンテンツスライド',
            icon: '📝',
            description: 'タイトル＋2セクション（各3項目）',
            xml: '<slide>\n  <title font-size="36">スライドタイトル</title>\n  <subtitle font-size="24"></subtitle>\n  <content>\n    <section name="ポイント1" type="main">\n      <bullet font-size="16">項目1の内容を入力</bullet>\n      <bullet font-size="16">項目2の内容を入力</bullet>\n      <bullet font-size="16">項目3の内容を入力</bullet>\n    </section>\n    <section name="ポイント2" type="main">\n      <bullet font-size="16">項目1の内容を入力</bullet>\n      <bullet font-size="16">項目2の内容を入力</bullet>\n      <bullet font-size="16">項目3の内容を入力</bullet>\n    </section>\n  </content>\n  <charts></charts>\n  <images></images>\n  <layout>タイトル上部、コンテンツは箇条書き</layout>\n  <color_scheme>background: #FFFFFF, text: #1B2A4A</color_scheme>\n  <notes font-size="9"></notes>\n</slide>'
        },
        'two-column': {
            id: 'two-column',
            name: '2カラム',
            icon: '▥',
            description: 'タイトル＋左右2列レイアウト',
            xml: '<slide>\n  <title font-size="36">比較・2カラムタイトル</title>\n  <subtitle font-size="24"></subtitle>\n  <content>\n    <section name="左カラム" type="main">\n      <bullet font-size="16">左側の項目1</bullet>\n      <bullet font-size="16">左側の項目2</bullet>\n      <bullet font-size="16">左側の項目3</bullet>\n    </section>\n    <section name="右カラム" type="main">\n      <bullet font-size="16">右側の項目1</bullet>\n      <bullet font-size="16">右側の項目2</bullet>\n      <bullet font-size="16">右側の項目3</bullet>\n    </section>\n  </content>\n  <charts></charts>\n  <images></images>\n  <layout>2カラム、左右に均等配置</layout>\n  <color_scheme>background: #FFFFFF, text: #1B2A4A</color_scheme>\n  <notes font-size="9"></notes>\n</slide>'
        },
        'with-image': {
            id: 'with-image',
            name: '画像付き',
            icon: '🖼',
            description: 'タイトル＋1セクション＋画像',
            xml: '<slide>\n  <title font-size="36">画像付きスライドタイトル</title>\n  <subtitle font-size="24"></subtitle>\n  <content>\n    <section name="説明" type="main">\n      <bullet font-size="16">画像に関する説明文1</bullet>\n      <bullet font-size="16">画像に関する説明文2</bullet>\n      <bullet font-size="16">画像に関する説明文3</bullet>\n    </section>\n  </content>\n  <charts></charts>\n  <images>右側に関連画像を配置（写真・図解など）</images>\n  <layout>左にテキスト、右に画像を配置</layout>\n  <color_scheme>background: #FFFFFF, text: #1B2A4A</color_scheme>\n  <notes font-size="9"></notes>\n</slide>'
        },
        'with-chart': {
            id: 'with-chart',
            name: 'チャート付き',
            icon: '📊',
            description: 'タイトル＋グラフ＋1セクション',
            xml: '<slide>\n  <title font-size="36">データ分析タイトル</title>\n  <subtitle font-size="24"></subtitle>\n  <content>\n    <section name="要点" type="main">\n      <bullet font-size="16">データから読み取れるポイント1</bullet>\n      <bullet font-size="16">データから読み取れるポイント2</bullet>\n    </section>\n  </content>\n  <charts font-size="12">棒グラフ: 項目A=40%, 項目B=30%, 項目C=20%, 項目D=10%</charts>\n  <images></images>\n  <layout>上部にグラフ、下部に要点を箇条書き</layout>\n  <color_scheme>background: #FFFFFF, text: #1B2A4A</color_scheme>\n  <notes font-size="9"></notes>\n</slide>'
        },
        'summary': {
            id: 'summary',
            name: 'まとめ',
            icon: '✅',
            description: 'タイトル＋3セクション（要点まとめ）',
            xml: '<slide>\n  <title font-size="36">まとめ</title>\n  <subtitle font-size="24"></subtitle>\n  <content>\n    <section name="要点1" type="main">\n      <bullet font-size="16">最も重要なポイント</bullet>\n    </section>\n    <section name="要点2" type="main">\n      <bullet font-size="16">次に重要なポイント</bullet>\n    </section>\n    <section name="要点3" type="main">\n      <bullet font-size="16">補足・今後のアクション</bullet>\n    </section>\n  </content>\n  <charts></charts>\n  <images></images>\n  <layout>3つの要点を均等に配置、各セクション強調</layout>\n  <color_scheme>background: #1B2A4A, text: #FFFFFF</color_scheme>\n  <notes font-size="9"></notes>\n</slide>'
        },
    };

    const DEFAULT_FONT_SIZES = {
        title: 36,
        subtitle: 24,
        bullet: 16,
        bulletFooter: 10,
        charts: 12,
        notes: 9,
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
        return (n >= 6 && n <= 72) ? n : defaultSize;
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
        return Array.from(sections).map(sec => {
            const sectionType = sec.getAttribute('type') || 'main';
            const defaultBulletSize = sectionType === 'footer'
                ? DEFAULT_FONT_SIZES.bulletFooter
                : DEFAULT_FONT_SIZES.bullet;
            return {
                name: sec.getAttribute('name') || '',
                type: sectionType,
                bullets: Array.from(sec.querySelectorAll('bullet')).map(b => ({
                    text: b.textContent.trim(),
                    fontSize: (() => {
                        const fs = b.getAttribute('font-size');
                        if (!fs) return defaultBulletSize;
                        const n = parseInt(fs, 10);
                        return (n >= 6 && n <= 72) ? n : defaultBulletSize;
                    })(),
                })),
            };
        });
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
    // Color scheme helpers
    // -------------------------------------------------------

    /** Default colors for the color picker */
    const DEFAULT_COLORS = { background: '#FFFFFF', text: '#1C3058', accent: '#CFAE70' };

    /** Japanese/English label mappings for color roles */
    const COLOR_ROLE_PATTERNS = [
        { role: 'background', patterns: [/(?:background|bg|背景)[:\s]+([#][0-9a-fA-F]{3,8})/i] },
        { role: 'text',       patterns: [/(?:text|font|文字|テキスト)[:\s]+([#][0-9a-fA-F]{3,8})/i] },
        { role: 'accent',     patterns: [/(?:accent|アクセント|強調)[:\s]+([#][0-9a-fA-F]{3,8})/i] },
    ];

    /**
     * Parse hex color codes from a color_scheme text string.
     * Maps common Japanese/English color terms to roles.
     * @param {string} colorSchemeText
     * @returns {{background: string, text: string, accent: string}}
     */
    function parseColors(colorSchemeText) {
        const result = { ...DEFAULT_COLORS };
        if (!colorSchemeText) return result;

        // Try to match labeled colors first
        for (const { role, patterns } of COLOR_ROLE_PATTERNS) {
            for (const pat of patterns) {
                const m = colorSchemeText.match(pat);
                if (m) {
                    result[role] = m[1];
                    break;
                }
            }
        }

        // If no labeled matches were found, try to extract bare hex codes in order
        const labeledFound = COLOR_ROLE_PATTERNS.some(({ patterns }) =>
            patterns.some(p => p.test(colorSchemeText))
        );
        if (!labeledFound) {
            const hexMatches = colorSchemeText.match(/#[0-9a-fA-F]{3,8}/g);
            if (hexMatches) {
                const roles = ['background', 'text', 'accent'];
                hexMatches.slice(0, 3).forEach((hex, i) => {
                    result[roles[i]] = hex;
                });
            }
        }

        return result;
    }

    /**
     * Convert a color object back to a formatted Japanese text string.
     * @param {{background: string, text: string, accent: string}} colors
     * @returns {string}
     */
    function formatColorScheme(colors) {
        return `背景: ${colors.background}, テキスト: ${colors.text}, アクセント: ${colors.accent}`;
    }

    /**
     * Build HTML for the color scheme field with color pickers and swatches.
     * @param {string} value - current color_scheme text
     * @param {number} pageNum
     * @returns {string}
     */
    function buildColorSchemeField(value, pageNum) {
        const colors = parseColors(value);

        const pickerRow = [
            { label: '背景', role: 'background', color: colors.background },
            { label: 'テキスト', role: 'text', color: colors.text },
            { label: 'アクセント', role: 'accent', color: colors.accent },
        ].map(({ label, role, color }) => `
            <div class="flex items-center gap-1">
                <span style="
                    display:inline-block;
                    width:20px;height:20px;
                    border-radius:50%;
                    border:2px solid #d1d5db;
                    background:${escapeHtml(color)};
                    flex-shrink:0;
                " data-color-swatch="${role}"></span>
                <input type="color"
                       value="${escapeHtml(color)}"
                       data-color-role="${role}"
                       data-page="${pageNum}"
                       class="w-7 h-7 p-0 border-0 rounded cursor-pointer bg-transparent"
                       title="${escapeHtml(label)}" />
                <span class="text-xs text-gray-500 dark:text-gray-400">${escapeHtml(label)}</span>
            </div>
        `).join('');

        return `<div class="mb-3" data-color-scheme-field>
            <div class="flex items-center justify-between mb-1">
                <label class="${CLS_LABEL}">配色</label>
            </div>
            <div class="flex items-center gap-3 mb-2 flex-wrap">
                ${pickerRow}
            </div>
            <textarea data-page="${pageNum}"
                      data-field="colorScheme"
                      rows="2"
                      class="${CLS_TEXTAREA}"
                      placeholder="自由記述も可能です">${escapeHtml(value)}</textarea>
        </div>`;
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
        const sectionType = sectionData.type || 'main';
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
                <select data-field="sectionType"
                        data-section-index="${sectionIndex}"
                        data-page="${pageNum}"
                        class="text-xs px-1 py-1 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200"
                        aria-label="セクション種別">
                    <option value="main"${sectionType === 'main' ? ' selected' : ''}>本文</option>
                    <option value="footer"${sectionType === 'footer' ? ' selected' : ''}>フッター</option>
                </select>
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

        // Color scheme (with color pickers)
        html += buildColorSchemeField(data.colorScheme, pageNum);

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

        // Attach color picker handlers
        attachColorPickerHandlers(container, pageNum);
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

            const typeSelect = container.querySelector(
                `[data-field="sectionType"][data-section-index="${si}"]`
            );
            const sectionType = typeSelect ? typeSelect.value : 'main';
            xml += `    <section name="${escapeXml(nameInput.value)}" type="${escapeXml(sectionType)}">\n`;

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
            type: 'main',
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
    // Preview rendering
    // -------------------------------------------------------

    /**
     * Collect current slide data from the structured editor DOM.
     * @param {string} containerId
     * @param {number} pageNum
     * @returns {Object} SlideData-like object
     */
    function collectSlideData(containerId, pageNum) {
        const container = document.getElementById(containerId);
        if (!container) return null;

        const get = (field) => {
            const el = container.querySelector(`[data-field="${field}"][data-page="${pageNum}"]`);
            return el ? el.value : '';
        };
        const getFs = (field) => {
            const el = container.querySelector(`[data-field="${field}"][data-page="${pageNum}"]`);
            return el ? parseInt(el.value, 10) || 0 : 0;
        };

        const sections = [];
        const processedSections = new Set();
        container.querySelectorAll('[data-section-index]').forEach(el => {
            const si = el.getAttribute('data-section-index');
            if (processedSections.has(si)) return;
            const nameInput = container.querySelector(`[data-field="sectionName"][data-section-index="${si}"]`);
            if (!nameInput) return;
            processedSections.add(si);

            const typeSelect = container.querySelector(`[data-field="sectionType"][data-section-index="${si}"]`);
            const sectionType = typeSelect ? typeSelect.value : 'main';
            const bullets = [];
            const bulletList = container.querySelector(`.bullet-list[data-section-index="${si}"]`);
            if (bulletList) {
                bulletList.querySelectorAll('.bullet-item').forEach(bulletEl => {
                    const textEl = bulletEl.querySelector('[data-field="bulletText"]');
                    const fsEl = bulletEl.querySelector('[data-field="bulletFontSize"]');
                    bullets.push({
                        text: textEl ? textEl.value : '',
                        fontSize: fsEl ? parseInt(fsEl.value, 10) || DEFAULT_FONT_SIZES.bullet : DEFAULT_FONT_SIZES.bullet,
                    });
                });
            }
            sections.push({ name: nameInput.value, type: sectionType, bullets });
        });

        return {
            title: get('title'),
            titleFontSize: getFs('titleFontSize') || DEFAULT_FONT_SIZES.title,
            subtitle: get('subtitle'),
            subtitleFontSize: getFs('subtitleFontSize') || DEFAULT_FONT_SIZES.subtitle,
            sections,
            charts: get('charts'),
            chartsFontSize: getFs('chartsFontSize') || DEFAULT_FONT_SIZES.charts,
            images: get('images'),
            layout: get('layout'),
            colorScheme: get('colorScheme'),
            notes: get('notes'),
            notesFontSize: getFs('notesFontSize') || DEFAULT_FONT_SIZES.notes,
        };
    }

    /**
     * Parse a color_scheme string to extract background and text colors.
     * Delegates to parseColors() for consistent parsing.
     * @param {string} colorScheme
     * @returns {{bg: string, text: string, accent: string}}
     */
    function parseColorScheme(colorScheme) {
        const parsed = parseColors(colorScheme);
        return { bg: parsed.background, text: parsed.text, accent: parsed.accent };
    }

    /**
     * Render a live HTML preview of slide data into a container.
     * @param {Object} data - SlideData object
     * @param {string} containerId - DOM id of the preview container
     */
    function renderPreview(data, containerId) {
        const container = document.getElementById(containerId);
        if (!container || !data) return;

        const colors = parseColorScheme(data.colorScheme);

        // Scale factor: XML font sizes are in pt for a real slide (~960px wide).
        // Preview container is smaller, so we scale down.
        const scale = 0.55;
        const fs = (pt) => Math.max(8, Math.round(pt * scale));

        let html = '';

        // Title
        if (data.title) {
            html += `<div style="text-align:center;font-size:${fs(data.titleFontSize)}px;font-weight:bold;margin-bottom:4px;line-height:1.2;">${escapeHtml(data.title)}</div>`;
        }

        // Subtitle
        if (data.subtitle) {
            html += `<div style="text-align:center;font-size:${fs(data.subtitleFontSize)}px;color:#666;margin-bottom:8px;line-height:1.3;">${escapeHtml(data.subtitle)}</div>`;
        }

        // Sections
        const mainSections = data.sections.filter(s => s.type !== 'footer');
        const footerSections = data.sections.filter(s => s.type === 'footer');

        if (mainSections.length > 0) {
            html += '<div style="flex:1;overflow:hidden;">';
            mainSections.forEach(sec => {
                if (sec.name) {
                    html += `<div style="font-size:${fs(18)}px;font-weight:600;margin:6px 0 2px 0;color:${escapeHtml(colors.text)};">${escapeHtml(sec.name)}</div>`;
                }
                sec.bullets.forEach(b => {
                    if (b.text) {
                        html += `<div style="font-size:${fs(b.fontSize)}px;padding-left:12px;line-height:1.4;margin-bottom:1px;">&#8226; ${escapeHtml(b.text)}</div>`;
                    }
                });
            });
            html += '</div>';
        }

        // Charts placeholder
        if (data.charts) {
            html += `<div style="margin:6px 0;padding:6px 8px;background:#f0f0f0;border:1px dashed #ccc;border-radius:4px;font-size:${fs(data.chartsFontSize)}px;color:#888;">&#128202; ${escapeHtml(data.charts)}</div>`;
        }

        // Images placeholder
        if (data.images) {
            html += `<div style="margin:6px 0;padding:6px 8px;background:#f5f0ff;border:1px dashed #c0b0e0;border-radius:4px;font-size:${fs(12)}px;color:#888;">&#128444; ${escapeHtml(data.images)}</div>`;
        }

        // Footer sections
        footerSections.forEach(sec => {
            html += '<div style="margin-top:auto;border-top:1px solid #ddd;padding-top:4px;">';
            sec.bullets.forEach(b => {
                if (b.text) {
                    html += `<div style="font-size:${fs(b.fontSize)}px;color:#999;line-height:1.3;">${escapeHtml(b.text)}</div>`;
                }
            });
            html += '</div>';
        });

        // Notes (small, at the very bottom)
        if (data.notes) {
            html += `<div style="margin-top:auto;font-size:${fs(data.notesFontSize)}px;color:#aaa;border-top:1px dotted #ddd;padding-top:3px;line-height:1.2;">${escapeHtml(data.notes)}</div>`;
        }

        container.innerHTML = `<div style="
            width:100%;
            aspect-ratio:16/9;
            background:${escapeHtml(colors.bg)};
            color:${escapeHtml(colors.text)};
            border:1px solid #e0e0e0;
            border-radius:6px;
            padding:12px 16px;
            box-sizing:border-box;
            overflow:hidden;
            display:flex;
            flex-direction:column;
            font-family:sans-serif;
            box-shadow:0 1px 4px rgba(0,0,0,0.08);
        ">${html}</div>`;
    }

    // -------------------------------------------------------
    // Debounced preview wiring
    // -------------------------------------------------------

    /** Map of containerId -> timeout id for debounce */
    const _previewTimers = {};

    /**
     * Set up debounced live preview for a structured editor.
     * Listens to input/change events and re-renders the preview after 300ms.
     * @param {string} editorContainerId - e.g. "structured-editor-3"
     * @param {string} previewContainerId - e.g. "slide-preview-3"
     * @param {number} pageNum
     */
    function setupPreviewSync(editorContainerId, previewContainerId, pageNum) {
        const editor = document.getElementById(editorContainerId);
        if (!editor) return;

        // Remove previous listener if exists
        if (editor._previewInputHandler) {
            editor.removeEventListener('input', editor._previewInputHandler);
            editor.removeEventListener('change', editor._previewInputHandler);
        }

        const handler = () => {
            clearTimeout(_previewTimers[editorContainerId]);
            _previewTimers[editorContainerId] = setTimeout(() => {
                const previewEl = document.getElementById(previewContainerId);
                if (!previewEl || previewEl.classList.contains('hidden')) return;
                const slideData = collectSlideData(editorContainerId, pageNum);
                if (slideData) renderPreview(slideData, previewContainerId);
            }, 300);
        };

        editor._previewInputHandler = handler;
        editor.addEventListener('input', handler);
        editor.addEventListener('change', handler);

        // Initial render
        const slideData = collectSlideData(editorContainerId, pageNum);
        if (slideData) renderPreview(slideData, previewContainerId);
    }

    // -------------------------------------------------------
    // Color picker event handling
    // -------------------------------------------------------

    /**
     * Attach change listeners on color picker inputs to update textarea and swatches.
     * @param {HTMLElement} container
     * @param {number} pageNum
     */
    function attachColorPickerHandlers(container, pageNum) {
        const colorField = container.querySelector('[data-color-scheme-field]');
        if (!colorField) return;

        const pickers = colorField.querySelectorAll('input[type="color"]');
        const textarea = colorField.querySelector('[data-field="colorScheme"]');
        if (!textarea) return;

        pickers.forEach(picker => {
            picker.addEventListener('input', () => {
                // Update the corresponding swatch
                const role = picker.dataset.colorRole;
                const swatch = colorField.querySelector(`[data-color-swatch="${role}"]`);
                if (swatch) swatch.style.background = picker.value;

                // Collect current picker values and update textarea
                const colors = {};
                colorField.querySelectorAll('input[type="color"]').forEach(p => {
                    colors[p.dataset.colorRole] = p.value;
                });
                textarea.value = formatColorScheme(colors);

                // Trigger input event on textarea so preview sync picks it up
                textarea.dispatchEvent(new Event('input', { bubbles: true }));
            });
        });

        // When textarea is edited manually, sync pickers back
        textarea.addEventListener('input', () => {
            if (textarea._colorPickerUpdating) return;
            const colors = parseColors(textarea.value);
            colorField.querySelectorAll('input[type="color"]').forEach(p => {
                const role = p.dataset.colorRole;
                if (colors[role]) {
                    // Normalize short hex to full hex for input[type=color]
                    let hex = colors[role];
                    if (/^#[0-9a-fA-F]{3}$/.test(hex)) {
                        hex = '#' + hex[1] + hex[1] + hex[2] + hex[2] + hex[3] + hex[3];
                    }
                    p.value = hex;
                    const swatch = colorField.querySelector(`[data-color-swatch="${role}"]`);
                    if (swatch) swatch.style.background = hex;
                }
            });
        });
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
    // Template methods
    // -------------------------------------------------------

    /**
     * Get list of available templates with id, name, icon, description.
     * @returns {Array<{id: string, name: string, icon: string, description: string}>}
     */
    function getTemplates() {
        return Object.values(SLIDE_TEMPLATES).map(t => ({
            id: t.id,
            name: t.name,
            icon: t.icon,
            description: t.description,
        }));
    }

    /**
     * Apply a template to a structured editor container.
     * Parses the template XML, renders into the editor, and syncs the XML textarea.
     * @param {string} templateId
     * @param {string} containerId - e.g. "structured-editor-3"
     * @param {number} pageNum
     * @returns {boolean} true if applied successfully
     */
    function applyTemplate(templateId, containerId, pageNum) {
        const template = SLIDE_TEMPLATES[templateId];
        if (!template) return false;

        try {
            const data = parseXml(template.xml);
            renderEditor(data, containerId, pageNum);
            setupPreviewSync(containerId, 'slide-preview-' + pageNum, pageNum);

            // Also update the raw XML textarea
            const xmlTextarea = document.getElementById('xml-editor-' + pageNum);
            if (xmlTextarea) {
                xmlTextarea.value = template.xml;
            }

            return true;
        } catch (e) {
            console.error('テンプレート適用エラー:', e);
            return false;
        }
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
        renderPreview,
        collectSlideData,
        setupPreviewSync,
        getTemplates,
        applyTemplate,
    };
})();
