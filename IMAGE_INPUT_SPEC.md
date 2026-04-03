# AI Workshop - マルチフォーマット画像入力仕様書

**作成日**: 2026-04-03
**ステータス**: 実装準備完了

---

## 1. 概要

現在のAIワークショップはPDFページのみを入力ソースとしている。本仕様では、ユーザーが**JPG/JPEG、WebP、PSD、PNG画像ファイルを直接アップロード**して、PDFページと同様にGemini Vision AIで解析→構造化XML編集→スライド再生成できるようにする。

### 現行フロー
```
PDF読み込み → ページをCanvas描画 → PNG化 → Gemini Vision解析 → XML編集 → 画像生成
```

### 新フロー（追加）
```
画像ファイル(JPG/WebP/PSD/PNG)ドロップ → ブラウザ内でデコード → Gemini Vision解析 → XML編集 → 画像生成
                                         ↓
                                    PDFに変換して取り込み（オプション）
```

---

## 2. 対応フォーマット

| フォーマット | MIME Type | ブラウザネイティブ | 追加処理 |
|-------------|-----------|:-:|---------|
| PNG | image/png | ✓ | なし |
| JPEG/JPG | image/jpeg | ✓ | なし |
| WebP | image/webp | ✓ | なし |
| PSD | image/vnd.adobe.photoshop | ✗ | JSライブラリでデコード→Canvas→PNG変換 |

### PSDデコード
- **ライブラリ**: `psd.js` (CDN: https://cdn.jsdelivr.net/npm/psd.js@3.4.0/dist/psd.min.js)
- PSDファイルを読み込み → 合成済み（flatten）画像をCanvas描画 → PNG Blobに変換
- レイヤー情報は使用しない（合成結果のみ）

---

## 3. UI設計

### 3.1 画像アップロードエリア（AI Workshop サイドバー）

既存のPDFベースのUI（APIキー、対象ページ、解析ボタン）の**上部に**画像アップロードセクションを追加。

```
┌─────────────────────────────────┐
│  AIワークショップ                  │
│                                 │
│  ── 画像から解析 ──────────────  │
│  ┌─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┐   │
│  │  📎 画像をドロップ         │   │
│  │  またはクリックで選択      │   │
│  │  JPG/PNG/WebP/PSD対応    │   │
│  └─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┘   │
│  [アップロードした画像を解析]     │
│                                 │
│  ── PDFから解析 ──────────────  │
│  (既存のUI: ページ選択等)        │
│                                 │
│  Gemini APIキー [............]  │
│  ...                            │
└─────────────────────────────────┘
```

### 3.2 ドラッグ&ドロップゾーン
- 点線ボーダーのドロップエリア
- クリックで `<input type="file" multiple accept=".jpg,.jpeg,.png,.webp,.psd">` を発火
- 複数ファイル対応
- ファイル追加後、サムネイルプレビューをドロップゾーン下に表示
- 各サムネイルに「×」削除ボタン
- ドラッグ中のビジュアルフィードバック（ボーダー色変更、アイコン拡大）

### 3.3 画像プレビューリスト
```
┌────┐ ┌────┐ ┌────┐
│img1│ │img2│ │img3│  ← サムネイル（80x60px）
│  × │ │  × │ │  × │  ← 削除ボタン
└────┘ └────┘ └────┘
slide1.jpg  logo.png  design.psd
```

### 3.4 解析結果の表示
- PDFページの解析結果と**同じ3カラムレイアウト**を使用:
  - 左: 元画像（アップロードされた画像）
  - 中: 構造化XMLエディタ（既存のXmlEditor）
  - 右: 生成結果（候補画像）
- 画像のページ番号は `img-1`, `img-2` のように表示

---

## 4. バックエンド変更

### 4.1 `/api/ai/vision-analyze` エンドポイント変更
- 対応MIMEタイプを拡張: `image/png`, `image/jpeg`, `image/webp`
- PSDはクライアント側でPNG変換後に送信するため、サーバー側の変更不要
- ファイルサイズ上限: 10MB（画像ファイルはPDFレンダリング画像より大きい可能性）

### 4.2 SSE `/api/ai/start-task` 変更
- `image_mime` パラメータが `image/webp` も受け付けるように
- 既存の `image/png`, `image/jpeg` に加えて `image/webp` を許可

### 4.3 新エンドポイント（不要）
- 画像デコード・変換はすべてクライアント側で行う
- サーバーは受信したPNG/JPEG/WebP画像をGemini APIに転送するだけ

---

## 5. クライアント実装

### 5.1 新モジュール: `static/js/image-input.js`

画像入力を管理するIIFEモジュール。

```javascript
const ImageInput = (() => {
    // Public API
    return {
        init(dropZoneId, previewContainerId),  // ドロップゾーン初期化
        getImages(),           // アップロード済み画像リスト取得
        removeImage(index),    // 画像を削除
        clearAll(),            // 全画像クリア
        decodePsd(file),       // PSDファイルをPNG Blobに変換
        prepareForAnalysis(file),  // 任意の画像をBlob(PNG/JPG/WebP)に正規化
    };
})();
```

### 5.2 画像正規化フロー

```
入力ファイル
  ├─ PNG/JPG/WebP → そのまま Blob として保持
  └─ PSD → psd.js でデコード → Canvas描画 → PNG Blobに変換
                               ↓
                        全フォーマット共通: Blob + dataURL(サムネイル用)
```

### 5.3 解析フロー（既存`analyzeSlides`を拡張）

新関数 `analyzeImages()`:
1. `ImageInput.getImages()` で画像リスト取得
2. 各画像について:
   a. Blobをbase64化
   b. SSE経由で `/api/ai/start-task` (vision-analyze) に送信
   c. XMLレスポンスを受信
3. 3カラムレイアウトで結果表示（既存HTMLテンプレートを再利用）
4. 構造化エディタ初期化
5. 「② 画像を生成」ボタン表示

### 5.4 生成結果のPDF適用

画像から解析した場合、生成結果をPDFに適用するには:
- **PDFが読み込み済み**: 指定ページの画像を生成画像で置換（`replacePageWithImage`）
- **PDFなし**: 生成画像からA4サイズの新規PDFを作成

---

## 6. PSDデコード詳細

### psd.js の利用
```javascript
async function decodePsd(file) {
    const arrayBuffer = await file.arrayBuffer();
    const psd = new PSD(new Uint8Array(arrayBuffer));
    psd.parse();
    const canvas = psd.image.toCanvas();  // 合成済み画像をCanvas化
    return new Promise(resolve => {
        canvas.toBlob(resolve, 'image/png');
    });
}
```

### 制約
- PSD.jsはレイヤー合成をサポート
- 大きなPSD（100MB超）はブラウザのメモリ制約で失敗する可能性
- CMYK/Lab色空間はsRGBに変換される
- Smart Objectの埋め込み内容は合成結果に含まれない場合がある

---

## 7. エラーハンドリング

| エラーケース | 対応 |
|------------|------|
| 非対応フォーマット | "対応形式: JPG, PNG, WebP, PSD" トースト表示 |
| ファイルサイズ超過（>10MB） | "ファイルサイズが大きすぎます（上限10MB）" |
| PSDデコード失敗 | "PSDファイルの読み込みに失敗しました" + フォールバック提案 |
| 画像が0枚で解析ボタン押下 | "画像を1枚以上アップロードしてください" |
| APIキー未入力 | "APIキーを入力してください"（既存） |
| Gemini API解析失敗 | 既存のエラーハンドリング |

---

## 8. テスト計画

### 8.1 ユニットテスト（Playwright E2E）

| # | テスト | 検証内容 |
|---|-------|---------|
| T01 | PNGアップロード→解析→生成 | 基本フロー完走 |
| T02 | JPEGアップロード→解析→生成 | JPEG対応 |
| T03 | WebPアップロード→解析→生成 | WebP対応 |
| T04 | PSDアップロード→PNG変換→解析 | PSDデコードフロー |
| T05 | 複数画像一括アップロード | 複数ファイル処理 |
| T06 | ドラッグ&ドロップ | D&Dイベント処理 |
| T07 | 非対応フォーマット拒否 | .gif, .bmp, .tiff 等 |
| T08 | 10MB超ファイル拒否 | サイズ制限 |
| T09 | 画像削除 | サムネイル削除UI |
| T10 | PSD + PNG混在アップロード | 異フォーマット混在 |
| T11 | 画像解析→XML編集→再生成 | 編集フロー |
| T12 | 画像解析→PDFに変換 | PDF出力 |
| T13 | 空画像リストで解析試行 | エラーハンドリング |
| T14 | 大量画像（10枚）アップロード | パフォーマンス |
| T15 | APIサーバーのMIMEタイプ検証 | バックエンド |
| T16 | SSE経由での画像解析 | SSEフロー |
| T17 | 解析結果の構造化エディタ動作 | エディタ連携 |
| T18 | 画像から生成→PDFに適用 | 適用フロー |
| T19 | PSDデコードのメモリ制約テスト | 大PSDハンドリング |
| T20 | ファイル名表示・日本語ファイル名 | UI表示 |

---

## 9. 実装タスク分割（20エージェント用）

| # | タスク | 変更ファイル |
|---|-------|-------------|
| 1 | `image-input.js` 基本モジュール（init, getImages, removeImage, clearAll） | static/js/image-input.js (new) |
| 2 | ドラッグ&ドロップUI（ドロップゾーンHTML + CSS） | ai_workshop.html, style.css |
| 3 | ファイル選択ダイアログ連携 | image-input.js |
| 4 | 画像サムネイルプレビュー表示 | image-input.js, ai_workshop.html |
| 5 | PSDデコード機能（psd.js統合） | image-input.js, base.html |
| 6 | 画像フォーマットバリデーション | image-input.js |
| 7 | ファイルサイズバリデーション（10MB上限） | image-input.js |
| 8 | `analyzeImages()` 関数（画像リスト→Vision API→XML） | ai_workshop.html |
| 9 | バックエンド: vision-analyze MIMEタイプ拡張（WebP追加） | ai.py |
| 10 | バックエンド: start-task MIMEタイプ拡張 | ai.py |
| 11 | 画像解析結果の3カラム表示（既存HTMLテンプレート再利用） | ai_workshop.html |
| 12 | 画像解析→構造化エディタ連携 | ai_workshop.html |
| 13 | 画像解析→スライド生成フロー | ai_workshop.html |
| 14 | 生成画像→新規PDF作成機能 | pdf-engine.js |
| 15 | 生成画像→既存PDFページ置換連携 | ai_workshop.html |
| 16 | エラーハンドリング（全エラーケース） | image-input.js, ai_workshop.html |
| 17 | レスポンシブ対応（モバイルUI） | style.css |
| 18 | アクセシビリティ（ARIA、キーボード操作） | ai_workshop.html |
| 19 | base.htmlにpsd.js CDNリンク追加 | base.html |
| 20 | E2Eテスト作成（20テストケース） | tests/test_e2e_image_input.py |

---

## 10. 制約・注意事項

- PSDファイルは**クライアント側でPNG変換**してからサーバーに送信（PSDバイナリはサーバーに送らない）
- 画像ファイルはIndexedDBに保存しない（一時的にメモリ上のみ）
- Gemini Vision APIのimage入力上限は20MB/リクエスト（個別画像は10MBに制限）
- WebP animated（アニメーション）は最初のフレームのみ使用
- HEIF/HEICは将来対応検討（現在非対応）
