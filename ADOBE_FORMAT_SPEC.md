# Adobe フォーマット対応仕様書

**作成日**: 2026-04-03
**ステータス**: 実装準備完了

---

## 1. 概要

AI WorkshopおよびPDFエディタ全体で、Adobe Photoshop/Illustratorのファイルフォーマットを追加対応する。

### 新規対応フォーマット

| フォーマット | 拡張子 | デコード方法 | ライブラリ |
|-------------|--------|-------------|----------|
| Adobe Illustrator | .ai | PDF.jsで直接開く（内部がPDF互換） | PDF.js（既存） |
| SVG | .svg | ブラウザネイティブ → Canvas → PNG変換 | なし（ネイティブ） |
| TIFF | .tif, .tiff | UTIF.js でデコード → Canvas → PNG変換 | UTIF.js (CDN) |
| EPS | .eps | サーバーサイド変換（将来対応） | 非対応（注記のみ） |

### 既存対応フォーマット
- PSD (.psd) — psd.js
- PNG (.png) — ネイティブ
- JPEG (.jpg, .jpeg) — ネイティブ
- WebP (.webp) — ネイティブ
- PDF (.pdf) — PDF.js + pdf-lib

---

## 2. AI ファイル対応

### 2.1 技術的背景
Adobe Illustrator 9以降（2000年〜）の.aiファイルは**内部的にPDF 1.5形式**。デフォルトの「PDF互換ファイルを作成」オプションが有効な場合、完全なPDFストリームを含む。

### 2.2 実装方針
- .aiファイルを**PDF として直接PDF.jsに渡す**
- ファイル選択ダイアログのacceptに `.ai` を追加
- MIMEタイプ: `application/postscript` または `application/illustrator`
- PDF.jsがパース失敗した場合 → 「PDF互換モードで保存されていないAIファイルです」エラー表示

### 2.3 対応範囲

#### PDFエディタ（メイン）
- ホームページのファイル入力: `.ai` 追加
- `PdfEngine.loadFromFile()`: .aiファイルをPDFとして読み込み
- エディタ: 通常のPDFと同様に全機能使用可能

#### AI Workshop
- 画像入力ドロップゾーン: `.ai` 追加
- .aiファイル → PDF.jsでレンダリング → Canvas → PNG → Vision API

---

## 3. SVG ファイル対応

### 3.1 デコード方法
```javascript
async function decodeSvg(file) {
    const text = await file.text();
    // SVGをImage要素で読み込み
    const img = new Image();
    const blob = new Blob([text], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    
    return new Promise((resolve, reject) => {
        img.onload = () => {
            // Canvas に描画して PNG に変換
            const canvas = document.createElement('canvas');
            // SVGのviewBox/width/heightから寸法取得
            canvas.width = img.naturalWidth || 960;
            canvas.height = img.naturalHeight || 540;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
            canvas.toBlob(blob => {
                URL.revokeObjectURL(url);
                resolve(blob);
            }, 'image/png');
        };
        img.onerror = () => {
            URL.revokeObjectURL(url);
            reject(new Error('SVGの読み込みに失敗しました'));
        };
        img.src = url;
    });
}
```

### 3.2 SVG寸法の取得
- `viewBox` 属性からwidth/height算出
- viewBoxがない場合: `width`/`height` 属性を使用
- どちらもない場合: デフォルト 960x540 (16:9)

### 3.3 制約
- 外部リソース参照（`<image href="external.png">`）は読み込み不可
- CSSアニメーションは静止画として描画
- テキストのフォントはシステムフォントにフォールバック

---

## 4. TIFF ファイル対応

### 4.1 ライブラリ
- **UTIF.js**: 軽量TIFF デコーダ（~30KB）
- CDN: `https://cdn.jsdelivr.net/npm/utif@3.1.0/UTIF.js`

### 4.2 デコード方法
```javascript
async function decodeTiff(file) {
    const arrayBuffer = await file.arrayBuffer();
    const ifds = UTIF.decode(arrayBuffer);
    UTIF.decodeImage(arrayBuffer, ifds[0]); // 最初のページをデコード
    const rgba = UTIF.toRGBA8(ifds[0]);
    
    const canvas = document.createElement('canvas');
    canvas.width = ifds[0].width;
    canvas.height = ifds[0].height;
    const ctx = canvas.getContext('2d');
    const imageData = new ImageData(new Uint8ClampedArray(rgba), ifds[0].width, ifds[0].height);
    ctx.putImageData(imageData, 0, 0);
    
    return new Promise(resolve => {
        canvas.toBlob(resolve, 'image/png');
    });
}
```

### 4.3 対応TIFFバリアント
- LZW圧縮 ✓
- ZIP圧縮 ✓
- JPEG圧縮 ✓
- マルチページTIFF: 最初のページのみ
- CMYK: UTIF.jsがRGB変換

---

## 5. UI変更

### 5.1 ファイル選択ダイアログ

#### ホームページ（PDFエディタ）
```
accept=".pdf,.ai"
```
- .ai は PDF として読み込み

#### AI Workshop 画像入力
```
accept=".jpg,.jpeg,.png,.webp,.psd,.ai,.svg,.tif,.tiff"
```

### 5.2 ドロップゾーンのラベル更新
```
JPG / PNG / WebP / PSD / AI / SVG / TIFF
```

### 5.3 ファイルタイプ表示
各ファイルのサムネイルにフォーマットバッジ表示:
- AI: 紫バッジ「AI」
- SVG: 緑バッジ「SVG」
- TIFF: 青バッジ「TIFF」
- PSD: 赤バッジ「PSD」

---

## 6. バックエンド変更

### 6.1 vision-analyze エンドポイント
- 変更不要: AI/SVG/TIFFはクライアント側でPNG変換後に送信
- 受信するのは常にPNG/JPEG/WebP

### 6.2 ホームページのPDF読み込み
- `.ai` ファイルを受け付ける（内部でPDFとして処理）
- `app/main.py` のページルートに変更不要（クライアント側のみ）

---

## 7. エラーハンドリング

| ケース | メッセージ |
|--------|----------|
| AI: PDF互換なし | 「このAIファイルはPDF互換モードで保存されていません。Illustratorで「PDF互換ファイルを作成」を有効にして再保存してください。」 |
| SVG: パースエラー | 「SVGファイルの読み込みに失敗しました。」 |
| SVG: 寸法不明 | デフォルト960x540で処理（警告なし） |
| TIFF: デコード失敗 | 「TIFFファイルの読み込みに失敗しました。」 |
| TIFF: CMYK | 自動RGB変換（警告なし） |
| EPS | 「EPSファイルは現在非対応です。SVGまたはPDFに変換してからアップロードしてください。」 |

---

## 8. 実装タスク分割（20エージェント）

| # | タスク | ファイル |
|---|-------|---------|
| 1 | image-input.js: AI(.ai)ファイル対応 — PDF.jsパイプライン連携 | image-input.js |
| 2 | image-input.js: SVGデコード機能 (decodeSvg) | image-input.js |
| 3 | image-input.js: TIFFデコード機能 (decodeTiff) | image-input.js |
| 4 | base.html: UTIF.js CDNリンク追加 | base.html |
| 5 | image-input.js: ファイルバリデーション拡張（AI/SVG/TIFF追加） | image-input.js |
| 6 | ai_workshop.html: ドロップゾーンUI更新（ラベル、accept属性） | ai_workshop.html |
| 7 | ai_workshop.html: AIファイルの解析フロー（PDF.js→Canvas→PNG→API） | ai_workshop.html |
| 8 | index.html: ホームページのaccept属性に.ai追加 | index.html |
| 9 | editor.html: エディタのaccept属性に.ai追加 | editor.html |
| 10 | pdf-engine.js: loadFromFile()で.ai拡張子をPDFとして処理 | pdf-engine.js |
| 11 | image-input.js: フォーマットバッジ表示（AI/SVG/TIFF/PSD） | image-input.js |
| 12 | image-input.js: EPSファイルの非対応エラー表示 | image-input.js |
| 13 | ai_workshop.html: SVGファイルの解析フロー | ai_workshop.html |
| 14 | ai_workshop.html: TIFFファイルの解析フロー | ai_workshop.html |
| 15 | style.css: フォーマットバッジのスタイル | style.css |
| 16 | エラーハンドリング: AI PDF互換エラー処理 | image-input.js, pdf-engine.js |
| 17 | merge.html: マージ画面のaccept属性に.ai追加 | merge.html |
| 18 | E2Eテスト: AIファイル読み込み（PDF.jsパイプライン） | test_e2e_adobe_formats.py |
| 19 | E2Eテスト: SVG/TIFF画像入力テスト | test_e2e_adobe_formats.py |
| 20 | E2Eテスト: バリデーション・エラーハンドリング | test_e2e_adobe_formats.py |

---

## 9. 対応フォーマット一覧（最終）

| フォーマット | 拡張子 | PDFエディタ | AI Workshop | 方法 |
|-------------|--------|:-----------:|:-----------:|------|
| PDF | .pdf | ✅ | ✅ | PDF.js + pdf-lib |
| AI | .ai | ✅ | ✅ | PDF.jsで直接読み込み |
| PSD | .psd | - | ✅ | psd.js → PNG |
| SVG | .svg | - | ✅ | ネイティブ → Canvas → PNG |
| TIFF | .tif/.tiff | - | ✅ | UTIF.js → Canvas → PNG |
| PNG | .png | - | ✅ | ネイティブ |
| JPEG | .jpg/.jpeg | - | ✅ | ネイティブ |
| WebP | .webp | - | ✅ | ネイティブ |
| EPS | .eps | ❌ | ❌ | 非対応（エラー表示） |
