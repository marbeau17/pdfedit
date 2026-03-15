# 構造化XMLエディタ 詳細仕様書

**PDF Workshop Pro - AIワークショップ機能拡張**
**バージョン**: 1.0
**作成日**: 2026-03-15
**ステータス**: 実装準備完了

---

## 目次

1. [エグゼクティブサマリー](#1-エグゼクティブサマリー)
2. [拡張XMLスキーマ定義](#2-拡張xmlスキーマ定義)
3. [構造化エディタUI設計](#3-構造化エディタui設計)
4. [JavaScript実装仕様](#4-javascript実装仕様)
5. [Geminiプロンプト修正](#5-geminiプロンプト修正)
6. [フォントサイズ制御の仕様](#6-フォントサイズ制御の仕様)
7. [セクション・箇条書きの動的操作仕様](#7-セクション箇条書きの動的操作仕様)
8. [XMLプレビューモード切り替え仕様](#8-xmlプレビューモード切り替え仕様)
9. [エラー処理仕様](#9-エラー処理仕様)
10. [レスポンシブ対応仕様](#10-レスポンシブ対応仕様)
11. [アクセシビリティ仕様](#11-アクセシビリティ仕様)
12. [セキュリティ仕様](#12-セキュリティ仕様)
13. [パフォーマンス仕様](#13-パフォーマンス仕様)
14. [テスト戦略](#14-テスト戦略)
15. [実装計画](#15-実装計画)
16. [修正対象ファイル一覧](#16-修正対象ファイル一覧)

---

## 1. エグゼクティブサマリー

### 背景
現在のAIワークショップでは、Gemini Vision APIから返されたXMLが生のテキストエリアに表示され、ユーザーはXMLタグを直接編集する必要がある。これは非技術者にとって大きな障壁であり、タグの閉じ忘れや構造破壊のリスクが高い。

### 解決策
XMLを自動解析し、各要素を個別の入力フィールドとして表示する「構造化エディタ」を実装する。ユーザーはフォームのように直感的にスライド内容を編集でき、変更は自動的にXMLに同期される。

### MVP定義（プロダクトマネージャー決定事項）
**Phase 1（MVP）**: 構造化エディタの基本機能
- XMLパース → フォーム表示
- テキスト編集（title, subtitle, bullets, charts, images, layout, color_scheme, notes）
- フォントサイズ制御（font-size属性）
- セクション・箇条書きの追加・削除・並べ替え
- 構造化エディタ ↔ 生XMLの切り替え
- XMLへの逆変換

**Phase 2（将来）**: プレビュー連動、テンプレート、カラーピッカー

### 技術スタック（CTO決定事項）
- **フロントエンド**: Alpine.js（既存利用）+ バニラJS
- **XMLパース**: DOMParser（ブラウザネイティブ）
- **並べ替え**: Sortable.js（既存CDN読み込み済み）
- **スタイル**: Tailwind CSS（既存CDN利用）
- **新規ライブラリ追加**: なし（既存依存のみ）

---

## 2. 拡張XMLスキーマ定義

### 2.1 スキーマ全体構造

```xml
<slide>
  <title font-size="28">タイトルテキスト</title>
  <subtitle font-size="18">サブタイトルテキスト</subtitle>
  <content>
    <section name="セクション名">
      <bullet font-size="14">箇条書きテキスト</bullet>
      <bullet font-size="14">箇条書きテキスト</bullet>
    </section>
    <section name="別のセクション">
      <bullet font-size="14">箇条書きテキスト</bullet>
    </section>
  </content>
  <charts font-size="12">グラフ・チャートの説明</charts>
  <images>画像・図形の説明</images>
  <layout>レイアウト指示</layout>
  <color_scheme>配色指示</color_scheme>
  <notes font-size="10">備考</notes>
</slide>
```

### 2.2 font-size属性の対応要素

| 要素 | font-size対応 | デフォルト値(pt) | 説明 |
|------|:---:|---:|------|
| `<title>` | はい | 28 | スライドタイトル |
| `<subtitle>` | はい | 18 | サブタイトル |
| `<bullet>` | はい | 14 | 箇条書き項目 |
| `<charts>` | はい | 12 | グラフ説明 |
| `<notes>` | はい | 10 | 備考 |
| `<images>` | いいえ | - | 画像説明（テキスト描画なし） |
| `<layout>` | いいえ | - | レイアウト指示（メタデータ） |
| `<color_scheme>` | いいえ | - | 配色指示（メタデータ） |
| `<section>` | いいえ | - | コンテナ要素（name属性のみ） |

### 2.3 バリデーションルール

- `<slide>` はルート要素として必須
- `<title>` は必須（空文字列は許容）
- `<content>` 内には0個以上の `<section>` を持てる
- `<section>` 内には0個以上の `<bullet>` を持てる
- `<section>` は `name` 属性が必須
- `font-size` の有効範囲: 8〜72（整数）
- font-size属性が省略された場合、デフォルト値を適用
- Geminiが返すXMLにfont-size属性がない場合（後方互換）、デフォルト値を自動付与

### 2.4 後方互換性

Geminiが従来形式（font-size属性なし）のXMLを返した場合、パーサーがデフォルト値を自動補完する。既存のXMLデータはすべて正常に読み込める。

---

## 3. 構造化エディタUI設計

### 3.1 全体レイアウト

現在の3カラムレイアウト（元画像 | XMLエディタ | 生成結果）の中央カラムを、構造化エディタに置き換える。

```
┌──────────────────────────────────────────────────────────────┐
│ ページ N                                         解析完了     │
├────────────────┬──────────────────────┬──────────────────────┤
│  元のスライド    │  スライド構造エディタ    │  生成結果            │
│  (画像)         │  [構造化] [XML]  ← タブ│  (画像)              │
│                │                      │                      │
│                │  (エディタ内容)        │                      │
│                │                      │                      │
├────────────────┴──────────────────────┴──────────────────────┘
```

### 3.2 構造化エディタの詳細UI

中央カラム内にタブ切り替え（「構造化」「XML」）を設置。「構造化」タブ選択時に以下のフォームを表示する。

```
┌─────────────────────────────────────────────────┐
│  [構造化]  [XML]                          タブ    │
├─────────────────────────────────────────────────┤
│                                                 │
│  タイトル                        フォント [28 ▼]  │
│  ┌─────────────────────────────────────────┐    │
│  │ スライドのタイトルテキスト                  │    │
│  └─────────────────────────────────────────┘    │
│                                                 │
│  サブタイトル                     フォント [18 ▼]  │
│  ┌─────────────────────────────────────────┐    │
│  │ サブタイトルテキスト                      │    │
│  └─────────────────────────────────────────┘    │
│                                                 │
│  ── コンテンツ ──────────────────────────────    │
│                                                 │
│  セクション: [宛先・発信者情報        ] [削除]     │
│  ┌ [14▼] [箇条書きテキスト1       ] [×][↑][↓] ┐ │
│  ├ [14▼] [箇条書きテキスト2       ] [×][↑][↓] ┤ │
│  └ [14▼] [箇条書きテキスト3       ] [×][↑][↓] ┘ │
│  [+ 箇条書き追加]                                │
│                                                 │
│  [+ セクション追加]                               │
│                                                 │
│  ── その他 ──────────────────────────────────    │
│                                                 │
│  グラフ・チャート                  フォント [12 ▼]  │
│  ┌─────────────────────────────────────────┐    │
│  │ チャートの説明テキスト                    │    │
│  └─────────────────────────────────────────┘    │
│                                                 │
│  画像・図形                                      │
│  ┌─────────────────────────────────────────┐    │
│  │ 画像の説明テキスト                        │    │
│  └─────────────────────────────────────────┘    │
│                                                 │
│  レイアウト                                      │
│  ┌─────────────────────────────────────────┐    │
│  │ レイアウト指示テキスト                    │    │
│  └─────────────────────────────────────────┘    │
│                                                 │
│  配色                                           │
│  ┌─────────────────────────────────────────┐    │
│  │ 配色指示テキスト                          │    │
│  └─────────────────────────────────────────┘    │
│                                                 │
│  備考                            フォント [10 ▼]  │
│  ┌─────────────────────────────────────────┐    │
│  │ 備考テキスト                              │    │
│  └─────────────────────────────────────────┘    │
│                                                 │
│            [XMLに反映]                           │
└─────────────────────────────────────────────────┘
```

### 3.3 UIコンポーネント仕様

#### タブ切り替えバー
- 2つのタブ: 「構造化」（デフォルト選択）、「XML」
- Tailwind: タブスタイルは `border-b-2 border-gold` でアクティブ表示
- タブ切り替え時にデータの同期を行う（後述: セクション8）

#### テキスト入力フィールド
- **単行フィールド**: title, subtitle, section name → `<input type="text">`
- **複数行フィールド**: charts, images, layout, color_scheme, notes → `<textarea rows="2">`
- **箇条書き**: bullet → `<input type="text">` （行内にフォントサイズ・削除・移動ボタン）

#### フォントサイズセレクタ
- `<select>` ドロップダウン
- 選択肢: 8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36, 42, 48, 54, 60, 72
- デフォルト値は要素種別に応じて設定（2.2節参照）
- Tailwind: `w-16 text-xs` でコンパクト表示

#### セクション操作ボタン
- 「+ セクション追加」: 新しい空セクションを末尾に追加
- 「セクション削除」: 確認ダイアログ後に削除
- セクションヘッダ内にセクション名の入力フィールド

#### 箇条書き操作ボタン
- 「+ 箇条書き追加」: セクション内末尾に新規bullet追加
- 「×」(削除): 該当bulletを削除（確認なし、Undo不要）
- 「↑」「↓」(移動): 箇条書きの順序変更
- ドラッグ&ドロップ: Sortable.jsによるドラッグ並べ替えも対応

### 3.4 デザイントークン

| 項目 | 値 |
|------|-----|
| ラベルテキスト | `text-xs font-medium text-gray-700 dark:text-gray-300` |
| 入力フィールド | `w-full px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200` |
| セクションコンテナ | `ml-2 pl-3 border-l-2 border-gray-200 dark:border-gray-600` |
| 追加ボタン | `text-xs text-blue-600 dark:text-blue-400 hover:underline` |
| 削除ボタン(bullet) | `text-red-400 hover:text-red-600 p-1` |
| 移動ボタン | `text-gray-400 hover:text-gray-600 p-1` |
| タブ(アクティブ) | `border-b-2 border-gold text-navy dark:text-gold font-semibold` |
| タブ(非アクティブ) | `text-gray-500 hover:text-gray-700` |
| セクション区切り | `text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider` |

---

## 4. JavaScript実装仕様

### 4.1 モジュール構造

新規ファイル `static/js/xml-editor.js` を作成する。グローバルオブジェクト `XmlEditor` としてエクスポートし、`ai_workshop.html` から呼び出す。

```javascript
const XmlEditor = (() => {
    // Public API
    return {
        parseXml,           // XML文字列 → データモデル
        renderEditor,       // データモデル → DOM（構造化エディタ）
        collectToXml,       // DOM → XML文字列
        syncFromRawXml,     // 生XMLテキストエリア → 構造化エディタに同期
        syncToRawXml,       // 構造化エディタ → 生XMLテキストエリアに同期
    };
})();
```

### 4.2 データモデル

XMLをパースした後、以下のJavaScriptオブジェクト構造で保持する。

```javascript
/**
 * @typedef {Object} SlideData
 * @property {string} title
 * @property {number} titleFontSize
 * @property {string} subtitle
 * @property {number} subtitleFontSize
 * @property {SectionData[]} sections
 * @property {string} charts
 * @property {number} chartsFontSize
 * @property {string} images
 * @property {string} layout
 * @property {string} colorScheme
 * @property {string} notes
 * @property {number} notesFontSize
 */

/**
 * @typedef {Object} SectionData
 * @property {string} name
 * @property {BulletData[]} bullets
 */

/**
 * @typedef {Object} BulletData
 * @property {string} text
 * @property {number} fontSize
 */
```

### 4.3 XMLパーサー (`parseXml`)

```javascript
function parseXml(xmlString) {
    // 1. DOMParserでパース
    const parser = new DOMParser();
    const doc = parser.parseFromString(xmlString, 'text/xml');

    // 2. パースエラーチェック
    const parseError = doc.querySelector('parsererror');
    if (parseError) {
        throw new Error('XMLパースエラー: ' + parseError.textContent);
    }

    // 3. <slide> ルート要素を取得
    const slide = doc.querySelector('slide');
    if (!slide) {
        throw new Error('<slide>要素が見つかりません');
    }

    // 4. 各要素を抽出
    return {
        title: getTextContent(slide, 'title'),
        titleFontSize: getFontSize(slide, 'title', 28),
        subtitle: getTextContent(slide, 'subtitle'),
        subtitleFontSize: getFontSize(slide, 'subtitle', 18),
        sections: parseSections(slide),
        charts: getTextContent(slide, 'charts'),
        chartsFontSize: getFontSize(slide, 'charts', 12),
        images: getTextContent(slide, 'images'),
        layout: getTextContent(slide, 'layout'),
        colorScheme: getTextContent(slide, 'color_scheme'),
        notes: getTextContent(slide, 'notes'),
        notesFontSize: getFontSize(slide, 'notes', 10),
    };
}
```

ヘルパー関数:

```javascript
function getTextContent(parent, tagName) {
    const el = parent.querySelector(':scope > ' + tagName)
            || parent.querySelector(tagName);
    return el ? el.textContent.trim() : '';
}

function getFontSize(parent, tagName, defaultSize) {
    const el = parent.querySelector(':scope > ' + tagName)
            || parent.querySelector(tagName);
    if (!el) return defaultSize;
    const fs = el.getAttribute('font-size');
    if (!fs) return defaultSize;
    const n = parseInt(fs, 10);
    return (n >= 8 && n <= 72) ? n : defaultSize;
}

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
                if (!fs) return 14;
                const n = parseInt(fs, 10);
                return (n >= 8 && n <= 72) ? n : 14;
            })(),
        })),
    }));
}
```

### 4.4 エディタレンダラー (`renderEditor`)

`renderEditor(data, containerId, pageNum)` は、SlideDataオブジェクトからHTMLフォームを生成し、指定コンテナに描画する。

主要実装方針:
- すべての入力フィールドに `data-page`, `data-field`, `data-section-index`, `data-bullet-index` 属性を付与
- フォントサイズセレクタの生成は共通関数 `buildFontSizeSelect(currentSize, dataAttrs)` で統一
- セクションコンテナには `data-section-index` を付与し、Sortable.jsを初期化
- 箇条書きリストには `.bullet-list` クラスを付与し、各箇条書き行に `.bullet-item` クラスを付与

#### HTML生成テンプレート

タイトル/サブタイトル等の単一フィールド:
```html
<div class="mb-3">
  <div class="flex items-center justify-between mb-1">
    <label class="text-xs font-medium text-gray-700 dark:text-gray-300">タイトル</label>
    <select data-page="1" data-field="titleFontSize" class="w-16 text-xs ...">
      <option value="28" selected>28</option>
      ...
    </select>
  </div>
  <input type="text" data-page="1" data-field="title" value="..." class="w-full px-3 py-2 text-sm ..." />
</div>
```

セクション:
```html
<div class="mb-3" data-section-index="0">
  <div class="flex items-center gap-2 mb-1">
    <span class="text-xs font-semibold text-gray-500">セクション:</span>
    <input type="text" data-page="1" data-field="sectionName" data-section-index="0"
           value="宛先・発信者情報" class="flex-1 px-2 py-1 text-xs ..." />
    <button data-action="deleteSection" data-section-index="0"
            class="text-red-400 hover:text-red-600 text-xs">削除</button>
  </div>
  <div class="ml-2 pl-3 border-l-2 border-gray-200 dark:border-gray-600 bullet-list"
       data-section-index="0">
    <!-- 箇条書き行 -->
    <div class="flex items-center gap-1 mb-1 bullet-item" data-bullet-index="0">
      <select data-field="bulletFontSize" data-section-index="0" data-bullet-index="0"
              class="w-14 text-xs ...">...</select>
      <input type="text" data-field="bulletText" data-section-index="0" data-bullet-index="0"
             value="..." class="flex-1 px-2 py-1 text-sm ..." />
      <button data-action="deleteBullet" data-section-index="0" data-bullet-index="0"
              class="text-red-400 hover:text-red-600" title="削除">×</button>
      <button data-action="moveBulletUp" data-section-index="0" data-bullet-index="0"
              class="text-gray-400 hover:text-gray-600" title="上へ">↑</button>
      <button data-action="moveBulletDown" data-section-index="0" data-bullet-index="0"
              class="text-gray-400 hover:text-gray-600" title="下へ">↓</button>
    </div>
    <!-- ... more bullets ... -->
    <button data-action="addBullet" data-section-index="0"
            class="text-xs text-blue-600 dark:text-blue-400 hover:underline mt-1">
      + 箇条書き追加
    </button>
  </div>
</div>
```

### 4.5 XML再構築 (`collectToXml`)

`collectToXml(containerId, pageNum)` はDOMからフォーム値を収集し、XML文字列を生成する。

```javascript
function collectToXml(containerId, pageNum) {
    const container = document.getElementById(containerId);
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
    const sectionContainers = container.querySelectorAll('[data-section-index]');
    const processedSections = new Set();
    sectionContainers.forEach(el => {
        const si = el.getAttribute('data-section-index');
        if (processedSections.has(si)) return;
        // セクション名を持つ要素のみ処理
        const nameInput = container.querySelector(
            `[data-field="sectionName"][data-section-index="${si}"]`
        );
        if (!nameInput) return;
        processedSections.add(si);

        xml += `    <section name="${escapeXml(nameInput.value)}">\n`;

        const bullets = container.querySelectorAll(
            `.bullet-list[data-section-index="${si}"] .bullet-item`
        );
        bullets.forEach(bulletEl => {
            const bi = bulletEl.getAttribute('data-bullet-index');
            const textEl = bulletEl.querySelector('[data-field="bulletText"]');
            const fsEl = bulletEl.querySelector('[data-field="bulletFontSize"]');
            const text = textEl ? textEl.value : '';
            const fs = fsEl ? fsEl.value : '14';
            xml += `      <bullet font-size="${fs}">${escapeXml(text)}</bullet>\n`;
        });

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

function escapeXml(str) {
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&apos;');
}
```

### 4.6 イベントハンドリング

イベント委譲パターンを使用し、エディタコンテナに単一のイベントリスナーを設置する。

```javascript
function attachEventListeners(containerId, pageNum) {
    const container = document.getElementById(containerId);

    container.addEventListener('click', (e) => {
        const btn = e.target.closest('[data-action]');
        if (!btn) return;

        const action = btn.dataset.action;
        const si = parseInt(btn.dataset.sectionIndex);
        const bi = parseInt(btn.dataset.bulletIndex);

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
    });
}
```

### 4.7 Sortable.js統合

各セクションの `.bullet-list` に対してSortable.jsを初期化する。

```javascript
function initSortable(container) {
    container.querySelectorAll('.bullet-list').forEach(list => {
        new Sortable(list, {
            animation: 150,
            handle: '.bullet-item',
            ghostClass: 'sortable-ghost',
            dragClass: 'sortable-drag',
            filter: '[data-action="addBullet"]',  // 追加ボタンはドラッグ対象外
            onEnd: () => reindexBullets(list),
        });
    });
}

function reindexBullets(listEl) {
    listEl.querySelectorAll('.bullet-item').forEach((item, index) => {
        item.setAttribute('data-bullet-index', index);
        item.querySelectorAll('[data-bullet-index]').forEach(child => {
            child.setAttribute('data-bullet-index', index);
        });
    });
}
```

---

## 5. Geminiプロンプト修正

### 5.1 Vision解析プロンプトの変更

ファイル: `app/routers/ai.py` の `vision_analyze` 関数内プロンプトを以下に変更する。

**変更前（現在）:**
```python
prompt = (
    "このプレゼンテーションスライド画像を詳細に分析し、以下のXML形式で構造化して出力してください。"
    "すべて日本語で記述してください。\n\n"
    "<slide>\n"
    "  <title>スライドのタイトル</title>\n"
    ...
)
```

**変更後:**
```python
prompt = (
    "このプレゼンテーションスライド画像を詳細に分析し、以下のXML形式で構造化して出力してください。"
    "すべて日本語で記述してください。\n"
    "各テキスト要素にはfont-size属性を推定して付与してください（単位: pt）。\n"
    "XMLタグ以外のテキストは出力しないでください。\n\n"
    "<slide>\n"
    "  <title font-size=\"28\">スライドのタイトル</title>\n"
    "  <subtitle font-size=\"18\">サブタイトル（あれば）</subtitle>\n"
    "  <content>\n"
    "    <section name=\"セクション名\">\n"
    "      <bullet font-size=\"14\">箇条書き項目</bullet>\n"
    "    </section>\n"
    "  </content>\n"
    "  <charts font-size=\"12\">グラフ・チャートの詳細説明（種類、データ、ラベル）</charts>\n"
    "  <images>画像・図形の説明（位置、内容）</images>\n"
    "  <layout>レイアウトの特徴（配置、構成）</layout>\n"
    "  <color_scheme>配色（メインカラー、アクセントカラー）</color_scheme>\n"
    "  <notes font-size=\"10\">その他の特記事項</notes>\n"
    "</slide>"
)
```

### 5.2 変更のポイント

1. `font-size` 属性をサンプルXMLに含めることで、Geminiがfont-size付きXMLを返すよう誘導
2. 「XMLタグ以外のテキストは出力しないでください」を追加し、余計な説明文の混入を防止
3. font-sizeの値はGeminiの推定に委ねるが、サンプル値でデフォルトの範囲を示す

### 5.3 画像生成プロンプトの変更

`generate_slide` 関数のプロンプトにfont-size解釈の指示を追加:

```python
prompt = (
    "以下のXMLに基づいて、プロフェッショナルなプレゼンテーションスライド画像を生成してください。\n"
    "- 白背景\n"
    "- 16:9のアスペクト比\n"
    "- クリーンでモダンなデザイン\n"
    "- 日本語テキストを正確に描画\n"
    "- 各要素のfont-size属性をpt単位のフォントサイズとして反映\n\n"
    f"XML:\n{req.xml}"
)
```

---

## 6. フォントサイズ制御の仕様

### 6.1 選択可能なフォントサイズ一覧

```javascript
const FONT_SIZES = [8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36, 42, 48, 54, 60, 72];
```

### 6.2 デフォルト値マッピング

```javascript
const DEFAULT_FONT_SIZES = {
    title: 28,
    subtitle: 18,
    bullet: 14,
    charts: 12,
    notes: 10,
};
```

### 6.3 フォントサイズセレクタ生成関数

```javascript
function buildFontSizeSelect(currentSize, attrs = {}) {
    const select = document.createElement('select');
    select.className = 'w-16 text-xs px-1 py-1 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200';
    Object.entries(attrs).forEach(([k, v]) => select.setAttribute(k, v));

    FONT_SIZES.forEach(size => {
        const opt = document.createElement('option');
        opt.value = size;
        opt.textContent = size;
        if (size === currentSize) opt.selected = true;
        select.appendChild(opt);
    });

    return select;
}
```

### 6.4 フォントサイズ非対応要素

images, layout, color_scheme はフォントサイズセレクタを表示しない。これらはメタデータ/指示情報であり、テキストとして描画されるものではないため。

---

## 7. セクション・箇条書きの動的操作仕様

### 7.1 セクション追加

```javascript
function addSection(container, pageNum) {
    const sections = container.querySelectorAll('[data-section-index]');
    const existingIndices = new Set();
    sections.forEach(el => existingIndices.add(parseInt(el.dataset.sectionIndex)));
    const newIndex = existingIndices.size > 0 ? Math.max(...existingIndices) + 1 : 0;

    const sectionHtml = buildSectionHtml(newIndex, pageNum, {
        name: '新しいセクション',
        bullets: [{ text: '', fontSize: 14 }],
    });

    // 「+ セクション追加」ボタンの直前に挿入
    const addSectionBtn = container.querySelector('[data-action="addSection"]');
    addSectionBtn.insertAdjacentHTML('beforebegin', sectionHtml);

    // Sortable再初期化
    initSortable(container);
}
```

### 7.2 セクション削除

```javascript
function deleteSection(container, sectionIndex) {
    // セクションヘッダーとbullet-listの両方を削除
    container.querySelectorAll(`[data-section-index="${sectionIndex}"]`).forEach(el => {
        // 親がdata-section-index付きでない場合のみ削除（子要素の重複削除防止）
        if (!el.parentElement.hasAttribute('data-section-index') ||
            el.parentElement.dataset.sectionIndex !== String(sectionIndex)) {
            el.remove();
        }
    });
}
```

### 7.3 箇条書き追加

```javascript
function addBullet(container, sectionIndex) {
    const list = container.querySelector(`.bullet-list[data-section-index="${sectionIndex}"]`);
    const bullets = list.querySelectorAll('.bullet-item');
    const newIndex = bullets.length;

    const bulletHtml = buildBulletHtml(sectionIndex, newIndex, { text: '', fontSize: 14 });
    const addBtn = list.querySelector('[data-action="addBullet"]');
    addBtn.insertAdjacentHTML('beforebegin', bulletHtml);
}
```

### 7.4 箇条書き削除

```javascript
function deleteBullet(container, sectionIndex, bulletIndex) {
    const list = container.querySelector(`.bullet-list[data-section-index="${sectionIndex}"]`);
    const item = list.querySelector(`.bullet-item[data-bullet-index="${bulletIndex}"]`);
    if (item) {
        item.remove();
        reindexBullets(list);
    }
}
```

### 7.5 箇条書き移動

```javascript
function moveBullet(container, sectionIndex, bulletIndex, direction) {
    const list = container.querySelector(`.bullet-list[data-section-index="${sectionIndex}"]`);
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
```

---

## 8. XMLプレビューモード切り替え仕様

### 8.1 タブ切り替えの仕組み

各ページ結果の中央カラムに2つのタブを設置:
- **「構造化」タブ**: 構造化エディタフォームを表示
- **「XML」タブ**: 従来の生XMLテキストエリアを表示

### 8.2 同期タイミング

| 操作 | 動作 |
|------|------|
| 構造化 → XML タブ切り替え | `collectToXml()` で構造化エディタの内容をXMLに変換し、テキストエリアに反映 |
| XML → 構造化 タブ切り替え | テキストエリアのXMLを `parseXml()` で解析し、構造化エディタを再描画 |
| XML → 構造化（パースエラー時） | エラーメッセージを表示し、XMLタブに留まる（切り替えを阻止） |
| 「XMLに反映」ボタンクリック | `collectToXml()` で内部XMLデータを更新（`analysisData[pageNum].xml`に保存） |

### 8.3 実装方法

```javascript
function switchTab(pageNum, tabName) {
    const structuredContainer = document.getElementById(`structured-editor-${pageNum}`);
    const xmlContainer = document.getElementById(`xml-container-${pageNum}`);
    const tabStructured = document.getElementById(`tab-structured-${pageNum}`);
    const tabXml = document.getElementById(`tab-xml-${pageNum}`);

    if (tabName === 'structured') {
        // XML → 構造化: パースして再描画
        const textarea = document.getElementById(`xml-editor-${pageNum}`);
        try {
            const data = XmlEditor.parseXml(textarea.value);
            XmlEditor.renderEditor(data, `structured-editor-${pageNum}`, pageNum);
            structuredContainer.classList.remove('hidden');
            xmlContainer.classList.add('hidden');
            tabStructured.classList.add('border-b-2', 'border-gold', 'font-semibold');
            tabStructured.classList.remove('text-gray-500');
            tabXml.classList.remove('border-b-2', 'border-gold', 'font-semibold');
            tabXml.classList.add('text-gray-500');
        } catch (e) {
            EditorUI.showToast('XMLパースエラー: ' + e.message, 'error');
            // 切り替えしない
        }
    } else {
        // 構造化 → XML: collectしてテキストエリアに反映
        const xml = XmlEditor.collectToXml(`structured-editor-${pageNum}`, pageNum);
        const textarea = document.getElementById(`xml-editor-${pageNum}`);
        textarea.value = xml;
        analysisData[pageNum].xml = xml;

        structuredContainer.classList.add('hidden');
        xmlContainer.classList.remove('hidden');
        tabXml.classList.add('border-b-2', 'border-gold', 'font-semibold');
        tabXml.classList.remove('text-gray-500');
        tabStructured.classList.remove('border-b-2', 'border-gold', 'font-semibold');
        tabStructured.classList.add('text-gray-500');
    }
}
```

### 8.4 初期表示

解析完了時のHTML生成で、デフォルトは「構造化」タブを選択状態にする。XMLを `parseXml()` でパースし、成功したら構造化エディタを表示。パースに失敗した場合はフォールバックとして「XML」タブを選択状態にする。

---

## 9. エラー処理仕様

### 9.1 XMLパースエラー

| エラー種別 | 検出方法 | ユーザーへの表示 |
|-----------|---------|----------------|
| XML構文エラー | `DOMParser` の `parsererror` 要素 | トーストで「XMLの構文に誤りがあります」 |
| `<slide>`要素不在 | `querySelector('slide')` が null | トーストで「`<slide>`要素が見つかりません」 |
| Geminiの不正応答 | XMLタグが含まれない文字列 | 生XMLタブにフォールバック表示 |

### 9.2 Gemini応答のXML抽出

Geminiが余計なテキスト（マークダウンコードブロック等）を付加する場合がある。パース前に以下の前処理を行う:

```javascript
function extractXmlFromResponse(rawText) {
    // ```xml ... ``` マークダウンブロックを除去
    let text = rawText.replace(/^```(?:xml)?\s*\n?/gm, '').replace(/\n?```\s*$/gm, '');

    // <slide>...</slide> を抽出
    const match = text.match(/<slide[\s>][\s\S]*<\/slide>/);
    if (match) return match[0];

    // 見つからない場合はそのまま返す（パースエラーで処理）
    return text;
}
```

### 9.3 バリデーションルール

構造化エディタからXMLを生成する際のバリデーション:

| フィールド | ルール | エラー時の動作 |
|-----------|--------|--------------|
| title | 空文字許容 | なし |
| section name | 空文字非推奨 | 「新しいセクション」をデフォルト値として挿入 |
| bullet text | 空文字許容 | 空の`<bullet>`タグを生成（Geminiが解釈） |
| font-size | 8-72の整数 | 範囲外はデフォルト値にクランプ |

### 9.4 ネットワークエラー

既存のtry-catchハンドリング（`analyzeSlides`, `generateSlides`内）をそのまま活用。構造化エディタ固有のネットワークエラーは発生しない（すべてクライアントサイド処理）。

---

## 10. レスポンシブ対応仕様

### 10.1 ブレークポイント戦略

| 画面幅 | レイアウト |
|--------|----------|
| >= 768px (md) | 3カラム: 元画像 | エディタ | 生成結果 |
| < 768px | 1カラム: 縦積み（元画像 → エディタ → 生成結果） |

### 10.2 モバイルでのエディタUI調整

- 箇条書き操作ボタン（×, ↑, ↓）: モバイルでは常に表示（hover不可のため）
- フォントサイズセレクタ: `w-14` に縮小
- セクションの `border-l` インデントを `ml-1 pl-2` に縮小
- 追加ボタンのタッチターゲット: `min-h-[44px]`（base.htmlの既存スタイルに準拠）

### 10.3 タブ切り替えのモバイル対応

タブは横並びのまま。テキストが「構造化」「XML」と短いため、折り返し不要。

---

## 11. アクセシビリティ仕様

### 11.1 セマンティクス

- タブ切り替え: `role="tablist"`, `role="tab"`, `role="tabpanel"`, `aria-selected`, `aria-controls`
- セクションリスト: `role="group"`, `aria-label="セクション: {name}"`
- 箇条書きリスト: 各 `.bullet-item` に `role="listitem"`
- 追加/削除ボタン: `aria-label` を明示的に設定

### 11.2 キーボード操作

| キー | 動作 |
|------|------|
| Tab | フィールド間フォーカス移動 |
| Shift+Tab | 逆方向フォーカス移動 |
| Enter (箇条書きinput内) | 次の箇条書きを追加してフォーカス移動 |
| Delete/Backspace (空の箇条書きinput内) | 該当箇条書きを削除して前のフィールドにフォーカス |
| 矢印キー (タブ内) | タブ切り替え |

### 11.3 スクリーンリーダー対応

- すべてのフォームフィールドに `<label>` または `aria-label` を関連付け
- 動的追加/削除時に `aria-live="polite"` 領域にステータスメッセージを出力
- フォントサイズセレクタに `aria-label="フォントサイズ"` を設定

### 11.4 色・コントラスト

既存のダークモード対応（`dark:` プレフィックス）に準拠。ハイコントラストモードでは `border-width: 2px` を適用（style.cssの既存 `@media (prefers-contrast: high)` に準拠）。

---

## 12. セキュリティ仕様

### 12.1 XSS防止

構造化エディタではすべてのユーザー入力値をDOMのプロパティ経由（`.value`, `.textContent`）で設定する。`innerHTML` は使用しない（テンプレート構築時を除く）。

XMLからの値表示時:
```javascript
// 安全: input.value への代入（HTMLとして解釈されない）
inputEl.value = slideData.title;

// 危険（使用禁止）: innerHTML への挿入
// container.innerHTML = `<div>${slideData.title}</div>`;  // XSSリスク
```

テンプレートHTML構築が必要な場合は、`escapeHtml()` 関数（既存）を使用する。

### 12.2 XML再構築時のエスケープ

`collectToXml()` 内で `escapeXml()` 関数を使用し、`&`, `<`, `>`, `"`, `'` をXMLエンティティにエスケープする（4.5節参照）。

### 12.3 APIキーの取り扱い

既存実装と同様、APIキーはクライアントからサーバーに送信され、サーバー側でGemini APIに転送される。APIキーはサーバー側で保存されない。構造化エディタの実装はAPIキーに関与しない。

---

## 13. パフォーマンス仕様

### 13.1 DOM操作の最小化

- 構造化エディタの初回描画時は、HTMLテンプレートを文字列で構築し、`innerHTML` で一括挿入（DOM操作1回）
- 箇条書き追加/削除は `insertAdjacentHTML` / `element.remove()` で最小限のDOM変更
- タブ切り替え時のみ再描画（リアルタイム同期は行わない）

### 13.2 イベント委譲

各ページのエディタコンテナに対して1つのイベントリスナーのみ設置。個別の箇条書きごとにリスナーを追加しない。

### 13.3 Sortable.js遅延初期化

Sortable.jsは構造化タブが表示された時のみ初期化する。XMLタブ表示時はSortable不要。

### 13.4 メモリ管理

ページ切り替え時やタブ切り替え時にSortableインスタンスを `destroy()` してからGCに任せる。

---

## 14. テスト戦略

### 14.1 ユニットテスト対象

| 関数 | テスト内容 |
|------|-----------|
| `parseXml()` | 正常XML、font-size属性あり/なし、空のcontent、section複数、parsererror |
| `collectToXml()` | 全フィールド入力済み、空フィールド、特殊文字（`<>&"'`）、日本語、複数セクション |
| `extractXmlFromResponse()` | 純粋XML、マークダウンブロック付き、余計なテキスト付き、`<slide>`なし |
| `escapeXml()` | 全エスケープ文字、日本語、空文字列 |
| `buildFontSizeSelect()` | 選択値の反映、範囲外値 |

### 14.2 統合テスト対象

| シナリオ | テスト内容 |
|---------|-----------|
| 解析→構造化表示 | Geminiの応答XMLが構造化エディタに正しく表示されるか |
| 構造化編集→XML反映 | 入力値変更が正しいXMLに変換されるか |
| タブ切り替え往復 | 構造化→XML→構造化でデータが保持されるか |
| セクション追加→XML | 新セクションがXMLに正しく含まれるか |
| 箇条書き並べ替え→XML | 順序変更がXMLに反映されるか |
| 生成フロー | 構造化エディタで編集後、「スライドを生成」が正常動作するか |

### 14.3 エッジケーステスト

| ケース | 期待動作 |
|--------|---------|
| Geminiが空文字列を返す | エラーメッセージ表示、XMLタブにフォールバック |
| Geminiがスキーマ外のタグを返す | 無視（構造化エディタに表示しない）、XMLタブでは表示 |
| font-size="abc" (非数値) | デフォルト値にフォールバック |
| font-size="999" (範囲外) | デフォルト値にフォールバック |
| `<content>` なしのXML | sections空配列、コンテンツセクション非表示 |
| セクション0個のcontent | 空のコンテンツエリア + 「セクション追加」ボタンのみ |
| 箇条書き0個のセクション | セクション名のみ + 「箇条書き追加」ボタン |
| 全セクション削除後にXML生成 | 空の `<content></content>` |
| XSS攻撃文字列 `<script>alert(1)</script>` | エスケープされてXMLに含まれる |
| 日本語混在テキスト | 正常にパース・表示・XML生成 |

### 14.4 モンキーテスト

既存の `tests/monkey_test.py` を拡張し、AI Workshop画面での構造化エディタのランダム操作テストを追加。

---

## 15. 実装計画

### 15.1 実装順序

| ステップ | 内容 | 推定工数 |
|---------|------|---------|
| 1 | `static/js/xml-editor.js` 新規作成（parseXml, collectToXml, escapeXml, extractXmlFromResponse） | 核心ロジック |
| 2 | `static/js/xml-editor.js` にrenderEditor, イベントハンドリング, Sortable統合を追加 | UI生成 |
| 3 | `app/templates/ai_workshop.html` を修正（タブUI追加、構造化エディタコンテナ追加、xml-editor.js読み込み） | テンプレート |
| 4 | `app/routers/ai.py` のプロンプト修正（font-size属性追加） | バックエンド |
| 5 | `static/css/style.css` に構造化エディタ用スタイル追加 | スタイル |
| 6 | テスト作成・実行 | 品質保証 |

### 15.2 ファイル構成

```
static/
  js/
    xml-editor.js       ← 新規作成
    pdf-engine.js       ← 変更なし
    storage.js          ← 変更なし
    editor.js           ← 変更なし
  css/
    style.css           ← 追加修正

app/
  templates/
    ai_workshop.html    ← 大幅修正
    base.html           ← xml-editor.jsのscript読み込み追加
  routers/
    ai.py              ← プロンプト修正
```

---

## 16. 修正対象ファイル一覧

### 16.1 新規作成ファイル

#### `static/js/xml-editor.js`
構造化XMLエディタの全ロジックを含むモジュール。

**エクスポートAPI:**
- `XmlEditor.parseXml(xmlString)` → SlideData
- `XmlEditor.renderEditor(data, containerId, pageNum)` → void
- `XmlEditor.collectToXml(containerId, pageNum)` → string
- `XmlEditor.extractXmlFromResponse(rawText)` → string
- `XmlEditor.initSortable(container)` → void

**内部関数:**
- `getTextContent()`, `getFontSize()`, `parseSections()`
- `buildFontSizeSelect()`, `buildSectionHtml()`, `buildBulletHtml()`
- `attachEventListeners()`, `addSection()`, `deleteSection()`, `addBullet()`, `deleteBullet()`, `moveBullet()`
- `reindexBullets()`, `escapeXml()`, `escapeHtml()`

### 16.2 修正ファイル

#### `app/templates/base.html`
**変更箇所:** `<script>` タグ追加（54行目付近）
```html
<script src="/static/js/xml-editor.js"></script>
```

#### `app/templates/ai_workshop.html`
**変更箇所1:** 中央カラムのHTML生成（159-185行目付近）

現在の中央カラム:
```html
<!-- XMLエディタ -->
<div class="p-3 border-r border-gray-200 dark:border-gray-700">
    <p class="text-xs text-gray-500 mb-1 font-medium">XML構造（編集可能）</p>
    <textarea id="xml-editor-${p}" ...>${escapeHtml(result.xml)}</textarea>
    <button onclick="saveXml(${p})" ...>XML保存</button>
</div>
```

変更後の中央カラム:
```html
<!-- 構造化XMLエディタ -->
<div class="p-3 border-r border-gray-200 dark:border-gray-700">
    <!-- タブ切り替え -->
    <div class="flex gap-2 mb-2" role="tablist">
        <button id="tab-structured-${p}" role="tab"
                aria-selected="true" aria-controls="structured-editor-${p}"
                onclick="switchTab(${p}, 'structured')"
                class="text-xs px-2 py-1 border-b-2 border-gold font-semibold
                       text-navy dark:text-gold">構造化</button>
        <button id="tab-xml-${p}" role="tab"
                aria-selected="false" aria-controls="xml-container-${p}"
                onclick="switchTab(${p}, 'xml')"
                class="text-xs px-2 py-1 text-gray-500 hover:text-gray-700
                       dark:hover:text-gray-300">XML</button>
    </div>

    <!-- 構造化エディタ -->
    <div id="structured-editor-${p}" role="tabpanel"
         class="overflow-y-auto max-h-96" style="scrollbar-width: thin;">
    </div>

    <!-- 生XMLエディタ (デフォルト非表示) -->
    <div id="xml-container-${p}" role="tabpanel" class="hidden">
        <textarea id="xml-editor-${p}"
                  class="w-full h-64 text-xs font-mono bg-gray-900 text-green-400
                         rounded p-2 border border-gray-700 resize-y"
                  spellcheck="false">${escapeHtml(result.xml)}</textarea>
    </div>

    <!-- 保存ボタン -->
    <button onclick="saveXmlFromEditor(${p})"
            class="mt-2 px-3 py-1 bg-navy text-white rounded text-xs
                   hover:bg-navy/90 w-full">XMLに反映</button>
</div>
```

**変更箇所2:** analyzeSlides関数内、HTML生成後に構造化エディタ初期化を追加

```javascript
workspace.innerHTML = html;

// 構造化エディタを初期化
for (const p of Object.keys(analysisData).map(Number)) {
    try {
        const cleanXml = XmlEditor.extractXmlFromResponse(analysisData[p].xml);
        const data = XmlEditor.parseXml(cleanXml);
        XmlEditor.renderEditor(data, `structured-editor-${p}`, p);
    } catch (e) {
        // パース失敗時はXMLタブをデフォルト表示
        switchTab(p, 'xml');
    }
}
```

**変更箇所3:** `saveXml` 関数を `saveXmlFromEditor` に置き換え

```javascript
function saveXmlFromEditor(pageNum) {
    const structuredEditor = document.getElementById(`structured-editor-${pageNum}`);
    const isStructuredVisible = !structuredEditor.classList.contains('hidden');

    if (isStructuredVisible) {
        // 構造化エディタからXMLを生成
        const xml = XmlEditor.collectToXml(`structured-editor-${pageNum}`, pageNum);
        const textarea = document.getElementById(`xml-editor-${pageNum}`);
        textarea.value = xml;
        analysisData[pageNum].xml = xml;
    } else {
        // XMLテキストエリアからの保存（従来動作）
        const textarea = document.getElementById(`xml-editor-${pageNum}`);
        if (textarea && analysisData[pageNum]) {
            analysisData[pageNum].xml = textarea.value;
        }
    }
    analysisData[pageNum].genImage = null;
    EditorUI.showToast(`P${pageNum}: XML保存完了`, 'success');
}
```

**変更箇所4:** `switchTab` 関数を追加（セクション8.3の実装）

**変更箇所5:** `generateSlides` 関数内のXML取得ロジック修正（222-224行目付近）

```javascript
// 最新のXMLを取得（構造化エディタが表示されている場合はそこから）
const structuredEditor = document.getElementById(`structured-editor-${p}`);
if (structuredEditor && !structuredEditor.classList.contains('hidden')) {
    data.xml = XmlEditor.collectToXml(`structured-editor-${p}`, p);
}
const textarea = document.getElementById(`xml-editor-${p}`);
if (textarea) {
    textarea.value = data.xml;
}
```

#### `app/routers/ai.py`
**変更箇所1:** vision_analyzeのプロンプト（52-68行目）を5.1節の内容に置き換え
**変更箇所2:** generate_slideのプロンプト（107-113行目）を5.3節の内容に置き換え

#### `static/css/style.css`
**追加内容:**
```css
/* --------------------------------------------------
   Structured XML Editor
   -------------------------------------------------- */
.bullet-item {
    transition: background-color 0.15s ease;
}

.bullet-item:hover {
    background-color: rgba(207, 174, 112, 0.08);
}

.dark .bullet-item:hover {
    background-color: rgba(207, 174, 112, 0.05);
}

/* Section container */
.section-container {
    border-left: 2px solid;
    border-color: rgba(209, 213, 219, 0.5);
    margin-left: 0.5rem;
    padding-left: 0.75rem;
}

.dark .section-container {
    border-color: rgba(75, 85, 99, 0.5);
}

/* Structured editor scrollbar */
.structured-editor-scroll {
    max-height: 24rem;
    overflow-y: auto;
}

/* Tab active indicator */
.tab-active {
    border-bottom: 2px solid #CFAE70;
    font-weight: 600;
}

/* Font size selector compact */
.font-size-select {
    width: 3.5rem;
    font-size: 0.75rem;
    padding: 0.125rem 0.25rem;
}

@media (max-width: 767px) {
    .structured-editor-scroll {
        max-height: 16rem;
    }

    .font-size-select {
        width: 3rem;
    }

    .bullet-action-btn {
        opacity: 1;
    }
}

@media (pointer: coarse) {
    .bullet-action-btn {
        opacity: 1;
        min-width: 36px;
        min-height: 36px;
    }
}
```

---

## 付録A: 完全なデータフロー図

```
[Gemini Vision API]
        │
        ▼ XML文字列（font-size属性付き）
[extractXmlFromResponse()]  ← マークダウン除去、<slide>抽出
        │
        ▼ クリーンなXML文字列
[parseXml()]  ← DOMParser → SlideDataオブジェクト
        │
        ├──▶ [renderEditor()]  ← SlideData → HTMLフォーム（構造化タブ）
        │         │
        │    ユーザー編集（テキスト入力、フォントサイズ変更、
        │    セクション追加/削除、箇条書き追加/削除/並べ替え）
        │         │
        │         ▼
        │    [collectToXml()]  ← HTMLフォーム → XML文字列
        │         │
        └──▶ [生XMLテキストエリア]  ← XML文字列（XMLタブ）
                  │
                  ▼
        [analysisData[pageNum].xml]  ← 保存
                  │
                  ▼
        [generateSlides()]  → Gemini画像生成API → スライド画像
```

---

## 付録B: 国際化考慮事項

### 日本語テキスト処理
- すべてのラベル文字列はハードコードされた日本語（i18n対象外・MVP）
- 入力フィールドのプレースホルダーは日本語
- XMLコンテンツは任意言語（日本語以外も正常処理）
- フォントファミリー指定なし（ブラウザデフォルトに委任、Geminiへの描画指示はXML経由）

### IME対応
- 箇条書きのEnterキーハンドリングにおいて、`isComposing` フラグを確認し、IME変換確定中のEnterを除外する

```javascript
inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.isComposing) {
        e.preventDefault();
        addBulletAfter(container, sectionIndex, bulletIndex);
    }
});
```

---

この仕様書に基づき、以下の順序で実装を進めること:

1. `static/js/xml-editor.js` の新規作成（コアロジック）
2. `app/templates/base.html` にスクリプト読み込み追加
3. `app/templates/ai_workshop.html` のUI改修
4. `app/routers/ai.py` のプロンプト修正
5. `static/css/style.css` のスタイル追加

すべての変更はクライアントサイドが中心であり、サーバーサイドはプロンプト文字列の変更のみである。新規ライブラリの追加は不要。
