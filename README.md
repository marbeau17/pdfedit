# PDF Workshop Pro

ブラウザ内でPDFを編集するWebアプリケーション。ファイルはサーバーに送信されず、すべての処理がブラウザ内で完結します。

**本番URL**: https://pdfedit-livid.vercel.app

## アーキテクチャ

**ローカルファースト** — PDFファイルはブラウザ内で処理。サーバーはHTML配信とGemini AIプロキシのみ。

```
ブラウザ: PDF.js (表示) + pdf-lib (編集) + IndexedDB (保存)
サーバー: FastAPI (HTML配信) + Gemini API (AIプロキシ)
```

## 機能

| # | 機能 | 処理場所 |
|---|------|---------|
| 1 | PDF結合 | ブラウザ |
| 2 | ページ削除 | ブラウザ |
| 3 | ページ並び替え (D&D) | ブラウザ |
| 4 | ファイル最適化 | ブラウザ |
| 5 | ブランディング (ロゴ+ページ番号+フッター) | ブラウザ |
| 6 | ページサイズ統一 | ブラウザ |
| 7 | エリア画像置換 (Canvas) | ブラウザ |
| 8 | AIスライド解析 (Gemini Vision) | ブラウザ→サーバー→Gemini |
| 9 | AIスライド生成 (Gemini) | ブラウザ→サーバー→Gemini |

## セットアップ

### 必要条件
- Python 3.12+
- pip

### インストール

```bash
git clone https://github.com/marbeau17/pdfedit.git
cd pdfedit
pip install -r requirements.txt
```

### ローカル起動

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

http://127.0.0.1:8000 でアクセス

### テスト実行

```bash
# ユニットテスト
python -m pytest tests/ -v

# Playwrightテスト (要 playwright install chromium)
pip install playwright
python -m playwright install chromium
python tests/monkey_test.py
python tests/test_e2e_xml_editor.py
```

### Vercelデプロイ

```bash
npm i -g vercel
vercel login
vercel deploy --prod
```

## AI機能の設定

AI Workshop (Gemini Vision解析 + スライド生成) を使用するには:

1. https://aistudio.google.com/apikey でGemini APIキーを取得
2. AI Workshopページでキーを入力 (ブラウザに自動保存されます)

使用モデル:
- Vision解析: `models/nano-banana-pro-preview`
- 画像生成: `models/nano-banana-pro-preview` → `models/gemini-3-pro-preview` (フォールバック)

## ブランディング

デフォルトロゴ: `logo/MeetsConsulting_tt_2 (1).png`

エディタのブランディングパネルで:
- ロゴ挿入 (右上、アスペクト比保持)
- ページ番号挿入
- フッターテキスト ("Strictly Private & Confidential")
- Copyright ("©2026 Meets Consulting Inc.")

## 技術スタック

| カテゴリ | 技術 |
|---------|------|
| PDF表示 | PDF.js v2.16.105 |
| PDF編集 | pdf-lib v1.17.1 |
| ストレージ | IndexedDB (Dexie.js v4) |
| UI | Alpine.js, Tailwind CSS (CDN), Sortable.js |
| サーバー | FastAPI, Jinja2 |
| AI | Google Gemini (google-genai) |
| デプロイ | Vercel |

## ファイル構成

```
pdfedit/
├── api/index.py                 # Vercelエントリーポイント
├── app/
│   ├── main.py                  # FastAPI (ルート定義)
│   ├── routers/
│   │   ├── ai.py                # Gemini APIプロキシ
│   │   └── health.py            # ヘルスチェック
│   └── templates/               # Jinja2テンプレート (7ページ)
├── static/
│   ├── js/
│   │   ├── pdf.min.js           # PDF.js (ローカルホスト)
│   │   ├── pdf.worker.min.js    # PDF.js Worker
│   │   ├── pdf-engine.js        # PDFエンジン (コア)
│   │   ├── storage.js           # IndexedDB
│   │   ├── editor.js            # エディタUI
│   │   └── xml-editor.js        # 構造化XMLエディタ
│   ├── css/style.css
│   └── img/default_logo.png
├── logo/                        # ロゴ画像ファイル
├── tests/                       # テストスイート
├── requirements.txt
├── pyproject.toml
└── vercel.json
```
