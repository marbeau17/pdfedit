# PDF Workshop Pro - 統合仕様書 v1.0

**作成日**: 2026-03-15
**技術スタック**: FastAPI / Jinja2 / HTMX / Vercel / Gemini Banana Pro / Python

---

## 7-Agent Discussion (設計議論)

### 参加エージェント

| # | Role | Name | Focus |
|---|------|------|-------|
| 1 | **Director** | Dir. Tanaka | 全体方針・優先順位・ビジネス要件 |
| 2 | **UI/UX Engineer** | UX Suzuki | ユーザー体験・操作フロー・アクセシビリティ |
| 3 | **Designer** | Des. Yamamoto | ビジュアル・レイアウト・ブランディング |
| 4 | **Python Expert** | Py. Sato | Python最適化・ライブラリ選定・パフォーマンス |
| 5 | **Software Engineer** | SE Nakamura | アーキテクチャ・API設計・インフラ |
| 6 | **Security Engineer** | Sec. Watanabe | セキュリティ・認証・データ保護 |
| 7 | **QA Engineer** | QA Ito | テスト戦略・品質保証・エッジケース |

---

### Round 1: 全体方針

**Dir. Tanaka**: 現在5つのバラバラなスクリプト（bittrim, combinepdf, changeorder, overwritepdf, removePDF）がある。これを統合した1つのWebアプリにしたい。Streamlitは社内では良いが、外部展開にはFastAPIベースのプロダクション品質が必要。

**SE Nakamura**: 同意。Streamlitはプロトタイプには最適だが、カスタムUI制御やパフォーマンスチューニングに限界がある。FastAPI + Jinja2 + HTMX構成なら、SPAフレームワーク不要でリアクティブなUIが構築でき、Vercelへのデプロイも容易。

**Py. Sato**: 既存コードはPyMuPDF(fitz)とpypdfの2つのPDFライブラリを混在使用している。統一すべき。PyMuPDF(fitz)の方が高機能で、画像処理・描画・最適化すべてに対応できる。pypdfは軽量だが機能不足。

**UX Suzuki**: 現在のoverwritepdf.pyはStreamlitベースで操作手順が多すぎる。HTMXなら部分更新で、ユーザーは「PDF投入 → 操作選択 → 即プレビュー → ダウンロード」の直感的フローが実現できる。

**Des. Yamamoto**: 現行UIにはデザインシステムがない。Tailwind CSSを採用し、一貫したビジュアルを構築すべき。ダークモード対応もマスト。

**Sec. Watanabe**: PDFアップロードは攻撃ベクトルになり得る。ファイルサイズ制限、MIMEタイプ検証、一時ファイルの自動削除が必須。APIキーのサーバーサイド管理も重要。

**QA Ito**: 各PDF操作は独立してテスト可能な設計にすべき。エッジケース（0ページPDF、暗号化PDF、巨大ファイル）への対応を仕様に含めたい。

---

### Round 2: アーキテクチャ決定

**SE Nakamura**: 以下の構成を提案する。

```
┌─────────────────────────────────────────────────┐
│                   Vercel Edge                    │
│              (Static + Serverless)               │
├─────────────────────────────────────────────────┤
│              FastAPI Application                 │
│  ┌───────────┐  ┌───────────┐  ┌─────────────┐ │
│  │  Jinja2   │  │   HTMX    │  │ Tailwind CSS│ │
│  │ Templates │  │ Fragments │  │   + Alpine  │ │
│  └───────────┘  └───────────┘  └─────────────┘ │
├─────────────────────────────────────────────────┤
│              API Layer (FastAPI)                  │
│  ┌─────┐ ┌────────┐ ┌───────┐ ┌─────────────┐  │
│  │Merge│ │Reorder │ │Remove │ │  Optimize   │  │
│  └─────┘ └────────┘ └───────┘ └─────────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌─────────────────┐  │
│  │Watermark │ │Branding  │ │ AI Generation   │  │
│  │ Removal  │ │ Overlay  │ │(Gemini Banana)  │  │
│  └──────────┘ └──────────┘ └─────────────────┘  │
├─────────────────────────────────────────────────┤
│              Core Libraries                      │
│  PyMuPDF(fitz) │ Pillow │ google-genai          │
└─────────────────────────────────────────────────┘
```

**Dir. Tanaka**: Serverless Functionの5秒タイムアウト制限は？大きなPDFの処理は間に合うか？

**SE Nakamura**: Vercel Serverless Functionsは最大300秒（Proプラン）。ただし、Gemini API呼び出しを含む重い処理はバックグラウンドタスク化し、HTMXのポーリングで進捗表示する設計にする。軽い操作（ページ削除・並び替え）はインスタントレスポンスで返す。

**Py. Sato**: Vercelのサーバーレス環境ではファイルシステムが一時的。アップロードされたPDFはメモリ上（BytesIO）で処理し、ディスクI/Oを最小化する。PyMuPDFはストリーム処理に対応しているので問題ない。

**UX Suzuki**: 処理の重さに応じてUI応答を分けるべき。

| 操作 | 想定処理時間 | UI応答方式 |
|------|-------------|-----------|
| ページ削除/並び替え | <1秒 | HTMX即時swap |
| PDF結合 | 1-5秒 | HTMX + ローディングインジケータ |
| ファイル最適化 | 2-10秒 | プログレスバー |
| AI画像生成 | 10-60秒 | SSE(Server-Sent Events) + 進捗表示 |

**Sec. Watanabe**: メモリ上での処理は良い。ただし、アップロードサイズ上限（50MB推奨）とリクエストレート制限を設けるべき。

---

### Round 3: 機能仕様

**Dir. Tanaka**: 統合する機能と優先度を整理する。

#### 機能一覧

| # | 機能名 | 元ソース | 優先度 | 説明 |
|---|--------|---------|-------|------|
| F1 | PDF結合 | combinepdf.py | P0 | 複数PDFを順序指定で結合 |
| F2 | ページ削除 | removePDF.py | P0 | 指定ページの削除 |
| F3 | ページ並び替え | changeorder.py | P0 | ドラッグ&ドロップでページ順序変更 |
| F4 | ファイル最適化 | bittrim.py | P1 | PDF/画像の圧縮・メタデータ削除 |
| F5 | 透かし除去 | overwritepdf.py | P1 | 指定エリアの色合わせ塗りつぶし |
| F6 | ブランディング | overwritepdf.py | P1 | ロゴ・ページ番号・フッター挿入 |
| F7 | ページサイズ統一 | overwritepdf.py | P2 | 全ページを1ページ目サイズに統一 |
| F8 | エリア画像置換 | overwritepdf.py | P2 | 指定範囲を画像で置換 |
| F9 | AI解析・生成 | overwritepdf.py | P2 | Gemini BananaProでスライド解析・再生成 |

---

### Round 4: API設計

**SE Nakamura**: RESTful APIエンドポイント設計。

#### ページルート（HTML応答 - Jinja2 + HTMX）

```
GET  /                          → ダッシュボード（メインUI）
GET  /upload                    → アップロードフォーム
GET  /editor/{session_id}       → PDFエディタ画面
GET  /preview/{session_id}      → ページプレビュー（HTMX fragment）
```

#### API エンドポイント（JSON/HTML fragment応答）

```
# セッション管理
POST   /api/upload              → PDFアップロード → session_id返却
DELETE /api/session/{id}        → セッション削除（ファイルクリーンアップ）

# ページ操作（即時応答）
POST   /api/pages/remove        → ページ削除
POST   /api/pages/reorder       → ページ並び替え
POST   /api/pages/resize        → ページサイズ統一

# PDF操作（処理時間あり）
POST   /api/merge               → 複数PDF結合
POST   /api/optimize            → ファイル最適化
POST   /api/watermark/remove    → 透かし除去
POST   /api/branding/apply      → ブランディング適用
POST   /api/area/replace        → エリア画像置換

# AI機能（非同期・SSE）
POST   /api/ai/analyze          → スライド解析（Vision API）
POST   /api/ai/generate         → スライド画像生成
GET    /api/ai/status/{task_id} → AI処理ステータス（SSE）

# エクスポート
GET    /api/download/{id}       → 処理済みPDFダウンロード
GET    /api/preview/{id}/{page} → ページサムネイル取得
```

**Py. Sato**: リクエスト/レスポンスモデルはPydanticで厳密に定義する。

```python
# --- Models ---
from pydantic import BaseModel, Field
from typing import Optional

class PageRemoveRequest(BaseModel):
    session_id: str
    pages: str = Field(..., example="1,3-5", description="削除対象ページ（1始まり）")

class PageReorderRequest(BaseModel):
    session_id: str
    order: list[int] = Field(..., example=[3,1,2], description="新しいページ順序（1始まり）")

class MergeRequest(BaseModel):
    session_ids: list[str] = Field(..., description="結合するPDFのセッションID群")

class BrandingRequest(BaseModel):
    session_id: str
    target_pages: Optional[str] = None
    enable_logo: bool = True
    enable_page_num: bool = True
    skip_first_logo: bool = True
    skip_first_num: bool = True
    logo_right_margin: int = 30
    logo_top_margin: int = 20
    logo_width: int = 100
    logo_height: int = 50
    page_num_right: int = 50
    page_num_bottom: int = 30

class WatermarkRemoveRequest(BaseModel):
    session_id: str
    margin_x: int = 106
    margin_y: int = 21
    special_pages: list[int] = []

class OptimizeRequest(BaseModel):
    session_id: str
    target_types: list[str] = ["pdf"]  # "pdf", "image", "json"

class AreaReplaceRequest(BaseModel):
    session_id: str
    page: int
    x: int
    y: int
    width: int
    height: int
    keep_aspect: bool = False

class AIAnalyzeRequest(BaseModel):
    session_id: str
    pages: str
    api_key: str  # クライアントサイドで入力

class AIGenerateRequest(BaseModel):
    session_id: str
    page: int
    xml_content: str
    api_key: str
```

**Sec. Watanabe**: `api_key` をリクエストボディで送るのはHTTPSであれば許容するが、可能なら環境変数での管理を推奨。ユーザーが自分のキーを使うケースでは、リクエストボディ経由をフォールバックとする。

---

### Round 5: フロントエンド設計

**UX Suzuki**: HTMXを中心としたインタラクション設計。JavaScriptは最小限に抑える。

#### 画面構成

```
┌─────────────────────────────────────────────────────┐
│  Header: PDF Workshop Pro           [Dark/Light] ☰  │
├────────────┬────────────────────────────────────────┤
│            │                                        │
│  Sidebar   │           Main Content                 │
│            │                                        │
│ ┌────────┐ │  ┌──────────────────────────────────┐  │
│ │Upload  │ │  │     PDF Preview Grid             │  │
│ │Zone    │ │  │  ┌────┐ ┌────┐ ┌────┐ ┌────┐    │  │
│ └────────┘ │  │  │ P1 │ │ P2 │ │ P3 │ │ P4 │    │  │
│            │  │  └────┘ └────┘ └────┘ └────┘    │  │
│ ┌────────┐ │  │  ┌────┐ ┌────┐                   │  │
│ │Tools   │ │  │  │ P5 │ │ P6 │                   │  │
│ │Panel   │ │  │  └────┘ └────┘                   │  │
│ │        │ │  └──────────────────────────────────┘  │
│ │[結合]  │ │                                        │
│ │[削除]  │ │  ┌──────────────────────────────────┐  │
│ │[並替]  │ │  │     Detail / Editor Panel         │  │
│ │[最適化]│ │  │  (HTMX swap target)              │  │
│ │[透かし]│ │  └──────────────────────────────────┘  │
│ │[AI]    │ │                                        │
│ └────────┘ │                                        │
│            │  ┌──────────────────────────────────┐  │
│ ┌────────┐ │  │     Status / Log Bar             │  │
│ │Settings│ │  └──────────────────────────────────┘  │
│ └────────┘ │                                        │
├────────────┴────────────────────────────────────────┤
│  Footer: Status Bar      [Download] [Reset]         │
└─────────────────────────────────────────────────────┘
```

**Des. Yamamoto**: デザイントークン定義。

```css
/* カラーパレット */
:root {
  --color-navy:    #1C3058;   /* メインブランドカラー */
  --color-gold:    #CFAE70;   /* アクセントカラー */
  --color-bg:      #F8FAFC;   /* 背景 */
  --color-surface: #FFFFFF;   /* カード背景 */
  --color-text:    #1E293B;   /* テキスト */
  --color-muted:   #64748B;   /* サブテキスト */
  --color-danger:  #EF4444;   /* 削除・エラー */
  --color-success: #22C55E;   /* 成功 */
}

/* ダークモード */
[data-theme="dark"] {
  --color-bg:      #0F172A;
  --color-surface: #1E293B;
  --color-text:    #F1F5F9;
  --color-muted:   #94A3B8;
}
```

**UX Suzuki**: HTMX主要インタラクション。

```html
<!-- ページ削除: クリックで即削除、サーバー側で処理してプレビュー更新 -->
<button hx-post="/api/pages/remove"
        hx-vals='{"session_id": "{{session_id}}", "pages": "{{page_num}}"}'
        hx-target="#preview-grid"
        hx-swap="innerHTML"
        hx-confirm="ページ {{page_num}} を削除しますか？"
        hx-indicator="#loading">
  削除
</button>

<!-- ページ並び替え: Sortable.jsと連携 -->
<div id="page-grid"
     hx-post="/api/pages/reorder"
     hx-trigger="sortable:end"
     hx-target="#preview-grid"
     hx-swap="innerHTML"
     hx-include="[name='page-order']">
  <!-- サムネイルグリッド -->
</div>

<!-- AI生成: SSEで進捗受信 -->
<div hx-ext="sse"
     sse-connect="/api/ai/status/{{task_id}}"
     sse-swap="message"
     hx-target="#ai-result">
</div>

<!-- ファイルアップロード: ドラッグ&ドロップ対応 -->
<form hx-post="/api/upload"
      hx-target="#editor-panel"
      hx-swap="innerHTML"
      hx-encoding="multipart/form-data"
      hx-indicator="#upload-spinner">
  <input type="file" name="pdf" accept=".pdf" multiple />
</form>
```

**Des. Yamamoto**: Alpine.jsを補助的に使い、クライアント側のUI状態（タブ切り替え、モーダル、トースト通知）を管理する。HTMX + Alpine.js の組み合わせは、React/Vue不要で十分なインタラクティビティを実現する。

---

### Round 6: Gemini Banana Pro統合

**Py. Sato**: AI機能の設計。

```python
from google import genai
from google.genai import types

# モデル定義
VISION_MODEL = "models/nano-banana-pro-preview"
GENERATION_MODELS = [
    "models/nano-banana-pro-preview",
    "models/gemini-3-pro-preview",
]

class GeminiService:
    """Gemini API統合サービス"""

    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    async def analyze_slide(self, image_bytes: bytes) -> str | None:
        """スライド画像をXMLに変換（Vision API）"""
        prompt = (
            "Analyze this slide image and convert to structured XML. "
            "Include title, body text, charts, tables. JAPANESE ONLY."
        )
        response = self.client.models.generate_content(
            model=VISION_MODEL,
            contents=[
                prompt,
                types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
            ],
        )
        return response.text if response.text else None

    async def generate_slide_image(self, xml_content: str) -> bytes | None:
        """XMLからスライド画像を生成"""
        prompt = (
            f"Create a professional slide image based on this XML. "
            f"WHITE background, clean design. XML:\n{xml_content}"
        )
        for model in GENERATION_MODELS:
            try:
                response = self.client.models.generate_content(
                    model=model, contents=prompt
                )
                if response.candidates:
                    for part in response.candidates[0].content.parts:
                        if part.inline_data:
                            return part.inline_data.data
            except Exception:
                continue
        return None
```

**SE Nakamura**: AI処理は非同期で実行し、SSE（Server-Sent Events）で進捗をクライアントに通知する。

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import asyncio

app = FastAPI()

async def ai_task_stream(task_id: str):
    """SSEストリームでAI処理進捗を送信"""
    while True:
        status = get_task_status(task_id)
        yield f"data: {status.model_dump_json()}\n\n"
        if status.completed:
            break
        await asyncio.sleep(1)

@app.get("/api/ai/status/{task_id}")
async def ai_status_sse(task_id: str):
    return StreamingResponse(
        ai_task_stream(task_id),
        media_type="text/event-stream",
    )
```

**Dir. Tanaka**: Gemini APIのコスト管理は？

**Py. Sato**: Vision解析（nano-banana-pro）は低コスト。画像生成はモデルサイズに応じてコスト増。ユーザーごとのAPI呼び出し回数を記録し、UIに表示することで透明性を確保する。サーバー側のキー使用時はレート制限を設ける。

---

### Round 7: Vercelデプロイ設計

**SE Nakamura**: Vercel + FastAPI構成。

```
pdfedit/
├── api/
│   └── index.py            # FastAPI エントリーポイント (Vercel Serverless)
├── app/
│   ├── main.py              # FastAPI アプリケーション定義
│   ├── routers/
│   │   ├── pages.py         # ページ操作API
│   │   ├── merge.py         # PDF結合API
│   │   ├── optimize.py      # 最適化API
│   │   ├── branding.py      # ブランディングAPI
│   │   ├── watermark.py     # 透かし除去API
│   │   ├── ai.py            # AI機能API
│   │   └── upload.py        # アップロードAPI
│   ├── services/
│   │   ├── pdf_service.py   # PDF操作コアロジック
│   │   ├── optimize_service.py  # 最適化ロジック
│   │   ├── branding_service.py  # ブランディングロジック
│   │   ├── gemini_service.py    # Gemini API統合
│   │   └── session_service.py   # セッション管理
│   ├── models/
│   │   ├── requests.py      # Pydanticリクエストモデル
│   │   └── responses.py     # Pydanticレスポンスモデル
│   └── templates/
│       ├── base.html         # ベーステンプレート
│       ├── index.html        # ダッシュボード
│       ├── editor.html       # エディタ画面
│       └── fragments/        # HTMX部分テンプレート
│           ├── preview_grid.html
│           ├── page_card.html
│           ├── tool_panel.html
│           ├── ai_result.html
│           └── status_bar.html
├── static/
│   ├── css/
│   │   └── style.css         # Tailwind CSS出力
│   ├── js/
│   │   ├── htmx.min.js       # HTMX
│   │   ├── alpine.min.js     # Alpine.js
│   │   └── sortable.min.js   # Sortable.js（D&D用）
│   └── img/
│       └── logo.png
├── tests/
│   ├── test_pdf_service.py
│   ├── test_optimize.py
│   ├── test_branding.py
│   └── test_api.py
├── vercel.json
├── requirements.txt
├── tailwind.config.js
└── pyproject.toml
```

**SE Nakamura**: `vercel.json` 設定。

```json
{
  "builds": [
    {
      "src": "api/index.py",
      "use": "@vercel/python",
      "config": {
        "maxLambdaSize": "50mb",
        "runtime": "python3.12"
      }
    },
    {
      "src": "static/**",
      "use": "@vercel/static"
    }
  ],
  "routes": [
    { "src": "/static/(.*)", "dest": "/static/$1" },
    { "src": "/(.*)", "dest": "/api/index.py" }
  ],
  "functions": {
    "api/index.py": {
      "memory": 1024,
      "maxDuration": 300
    }
  }
}
```

**Sec. Watanabe**: 環境変数管理。

```
# Vercel Environment Variables
GEMINI_API_KEY=        # オプション（サーバー共有キー）
SESSION_SECRET=        # セッション暗号化キー
MAX_UPLOAD_SIZE_MB=50  # アップロード上限
RATE_LIMIT_PER_MIN=30  # API呼び出しレート制限
```

---

### Round 8: セッション管理とデータフロー

**SE Nakamura**: サーバーレス環境ではファイルシステムが揮発的。セッション管理にはVercel KV（Redis互換）を使用する。

```python
from datetime import datetime, timedelta
import uuid
import io

class SessionService:
    """PDFセッション管理"""

    # メモリ内ストア (開発用) / Vercel KV (本番用)
    _store: dict[str, dict] = {}
    SESSION_TTL = timedelta(hours=1)

    @classmethod
    def create(cls, pdf_bytes: bytes, filename: str) -> str:
        session_id = uuid.uuid4().hex[:12]
        cls._store[session_id] = {
            "pdf_bytes": pdf_bytes,
            "original_filename": filename,
            "created_at": datetime.utcnow(),
            "history": [],  # 操作履歴（Undo用）
        }
        return session_id

    @classmethod
    def get_pdf(cls, session_id: str) -> bytes | None:
        session = cls._store.get(session_id)
        if not session:
            return None
        if datetime.utcnow() - session["created_at"] > cls.SESSION_TTL:
            cls.delete(session_id)
            return None
        return session["pdf_bytes"]

    @classmethod
    def update_pdf(cls, session_id: str, new_bytes: bytes, operation: str):
        session = cls._store.get(session_id)
        if session:
            # 現在の状態を履歴に保存（Undo対応）
            session["history"].append(session["pdf_bytes"])
            session["pdf_bytes"] = new_bytes

    @classmethod
    def undo(cls, session_id: str) -> bool:
        session = cls._store.get(session_id)
        if session and session["history"]:
            session["pdf_bytes"] = session["history"].pop()
            return True
        return False

    @classmethod
    def delete(cls, session_id: str):
        cls._store.pop(session_id, None)
```

**UX Suzuki**: Undo機能は必須。各操作前に状態を保存し、「元に戻す」ボタンで1ステップ戻れるようにする。操作履歴は最大10件保持。

**QA Ito**: セッションTTL（1時間）は妥当。ただし大きなPDFの場合メモリ圧迫するため、本番ではVercel Blob Storageに逃がすべき。

---

### Round 9: コア処理サービス

**Py. Sato**: 既存ロジックをサービス層に統合。

```python
import fitz
import io
from PIL import Image

class PDFService:
    """PDF操作のコアサービス"""

    @staticmethod
    def get_page_count(pdf_bytes: bytes) -> int:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        count = len(doc)
        doc.close()
        return count

    @staticmethod
    def get_page_thumbnail(pdf_bytes: bytes, page_num: int, dpi: int = 72) -> bytes:
        """ページのサムネイル画像を生成"""
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[page_num - 1]
        pix = page.get_pixmap(dpi=dpi)
        img_bytes = pix.tobytes("png")
        doc.close()
        return img_bytes

    @staticmethod
    def remove_pages(pdf_bytes: bytes, pages_to_remove: set[int]) -> bytes:
        """指定ページを削除（1始まり）"""
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        # 逆順で削除（インデックスずれ防止）
        for p in sorted(pages_to_remove, reverse=True):
            if 1 <= p <= len(doc):
                doc.delete_page(p - 1)
        result = doc.tobytes(garbage=4, deflate=True)
        doc.close()
        return result

    @staticmethod
    def reorder_pages(pdf_bytes: bytes, new_order: list[int]) -> bytes:
        """ページを指定順序に並び替え（1始まり）"""
        src = fitz.open(stream=pdf_bytes, filetype="pdf")
        dst = fitz.open()
        for p in new_order:
            if 1 <= p <= len(src):
                dst.insert_pdf(src, from_page=p-1, to_page=p-1)
        result = dst.tobytes(garbage=4, deflate=True)
        src.close()
        dst.close()
        return result

    @staticmethod
    def merge_pdfs(pdf_bytes_list: list[bytes]) -> bytes:
        """複数PDFを結合"""
        dst = fitz.open()
        for pdf_bytes in pdf_bytes_list:
            src = fitz.open(stream=pdf_bytes, filetype="pdf")
            dst.insert_pdf(src)
            src.close()
        result = dst.tobytes(garbage=4, deflate=True)
        dst.close()
        return result

    @staticmethod
    def optimize(pdf_bytes: bytes) -> tuple[bytes, int, int]:
        """PDF最適化: 不要オブジェクト削除・ストリーム圧縮"""
        original_size = len(pdf_bytes)
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        result = doc.tobytes(garbage=4, deflate=True)
        doc.close()
        return result, original_size, len(result)

    @staticmethod
    def resize_to_first_page(pdf_bytes: bytes) -> bytes:
        """全ページを1ページ目サイズに統一"""
        src = fitz.open(stream=pdf_bytes, filetype="pdf")
        if len(src) < 1:
            return pdf_bytes
        target_rect = src[0].rect
        dst = fitz.open()
        for i, page in enumerate(src):
            new_page = dst.new_page(width=target_rect.width, height=target_rect.height)
            new_page.show_pdf_page(target_rect, src, i)
        result = dst.tobytes(garbage=4, deflate=True)
        src.close()
        dst.close()
        return result

    @staticmethod
    def remove_watermark(
        pdf_bytes: bytes,
        margin_x: int = 106,
        margin_y: int = 21,
        special_pages: list[int] = [],
    ) -> bytes:
        """透かし除去（周囲色で塗りつぶし）"""
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for i, page in enumerate(doc):
            p_num = i + 1
            r = page.rect
            target_rect = fitz.Rect(r.width - margin_x, r.height - margin_y, r.width, r.height)

            if p_num in special_pages:
                probe_x, probe_y = r.width - 5, 5
            else:
                probe_x = max(0, target_rect.x0 - 2)
                probe_y = target_rect.y0 + 2

            probe_rect = fitz.Rect(probe_x, probe_y, probe_x + 1, probe_y + 1)
            pix = page.get_pixmap(clip=probe_rect, alpha=False)
            fill_color = (1, 1, 1)
            if pix.width > 0 and pix.height > 0:
                try:
                    rgb = pix.pixel(0, 0)
                    fill_color = (rgb[0]/255, rgb[1]/255, rgb[2]/255)
                except:
                    pass
            page.add_redact_annot(target_rect, fill=fill_color)
            page.apply_redactions()

        result = doc.tobytes(garbage=4, deflate=True)
        doc.close()
        return result
```

---

### Round 10: テンプレート設計（Jinja2 + HTMX）

**UX Suzuki + Des. Yamamoto**: ベーステンプレート構造。

```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html lang="ja" x-data="{ darkMode: false }" :class="{ 'dark': darkMode }">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}PDF Workshop Pro{% endblock %}</title>
    <script src="/static/js/htmx.min.js"></script>
    <script src="/static/js/htmx-ext-sse.js"></script>
    <script src="/static/js/alpine.min.js" defer></script>
    <link href="/static/css/style.css" rel="stylesheet">
</head>
<body class="bg-slate-50 dark:bg-slate-900 text-slate-800 dark:text-slate-200
             min-h-screen flex flex-col"
      hx-boost="true">

    <!-- Header -->
    <header class="bg-navy-800 text-white px-6 py-3 flex items-center justify-between">
        <h1 class="text-lg font-bold tracking-wide">PDF Workshop Pro</h1>
        <div class="flex items-center gap-4">
            <button @click="darkMode = !darkMode" class="text-sm">
                <span x-text="darkMode ? 'Light' : 'Dark'"></span>
            </button>
        </div>
    </header>

    <!-- Main -->
    <div class="flex flex-1 overflow-hidden">
        <!-- Sidebar -->
        <aside class="w-72 bg-white dark:bg-slate-800 border-r p-4 overflow-y-auto">
            {% block sidebar %}{% endblock %}
        </aside>

        <!-- Content -->
        <main class="flex-1 p-6 overflow-y-auto">
            {% block content %}{% endblock %}
        </main>
    </div>

    <!-- Toast Notifications -->
    <div id="toast-container"
         class="fixed bottom-4 right-4 flex flex-col gap-2 z-50"
         x-data="{ toasts: [] }">
    </div>

    <!-- Global Loading Indicator -->
    <div id="loading" class="htmx-indicator fixed top-0 left-0 w-full h-1 bg-gold-500
                              animate-pulse z-50"></div>
</body>
</html>
```

```html
<!-- templates/fragments/page_card.html -->
<!-- 各ページのサムネイルカード（HTMX fragmentとして返却） -->
<div class="page-card group relative rounded-lg overflow-hidden shadow-md
            hover:shadow-xl transition-shadow cursor-move border-2 border-transparent
            hover:border-gold-400"
     data-page="{{ page_num }}"
     draggable="true">

    <img src="/api/preview/{{ session_id }}/{{ page_num }}"
         alt="Page {{ page_num }}"
         class="w-full h-auto" loading="lazy" />

    <div class="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60
                to-transparent p-2 flex justify-between items-end">
        <span class="text-white text-sm font-bold">P{{ page_num }}</span>
        <div class="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <button hx-post="/api/pages/remove"
                    hx-vals='{"session_id":"{{ session_id }}","pages":"{{ page_num }}"}'
                    hx-target="#preview-grid"
                    hx-swap="innerHTML"
                    hx-confirm="ページ {{ page_num }} を削除しますか？"
                    class="bg-red-500 text-white rounded p-1 text-xs">
                Del
            </button>
        </div>
    </div>
</div>
```

---

### Round 11: 技術要件

**Py. Sato**: `requirements.txt`

```
# Core
fastapi>=0.115.0
uvicorn[standard]>=0.34.0
python-multipart>=0.0.18
jinja2>=3.1.5

# PDF Processing
PyMuPDF>=1.25.0
Pillow>=11.0.0

# AI
google-genai>=1.5.0

# Utilities
pydantic>=2.10.0
python-dotenv>=1.0.0

# Development
pytest>=8.3.0
httpx>=0.28.0  # テスト用AsyncClient
ruff>=0.9.0    # Linter/Formatter
```

**QA Ito**: テスト戦略。

```python
# tests/test_pdf_service.py
import pytest
from app.services.pdf_service import PDFService

@pytest.fixture
def sample_pdf():
    """テスト用の2ページPDFを生成"""
    import fitz
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page()
        page.insert_text((50, 50), f"Page {i+1}")
    return doc.tobytes()

class TestRemovePages:
    def test_remove_single_page(self, sample_pdf):
        result = PDFService.remove_pages(sample_pdf, {2})
        doc = fitz.open(stream=result, filetype="pdf")
        assert len(doc) == 2

    def test_remove_all_pages_returns_empty(self, sample_pdf):
        result = PDFService.remove_pages(sample_pdf, {1, 2, 3})
        doc = fitz.open(stream=result, filetype="pdf")
        assert len(doc) == 0

    def test_remove_invalid_page_ignored(self, sample_pdf):
        result = PDFService.remove_pages(sample_pdf, {99})
        doc = fitz.open(stream=result, filetype="pdf")
        assert len(doc) == 3

class TestReorderPages:
    def test_reverse_order(self, sample_pdf):
        result = PDFService.reorder_pages(sample_pdf, [3, 2, 1])
        doc = fitz.open(stream=result, filetype="pdf")
        assert len(doc) == 3

class TestMerge:
    def test_merge_two_pdfs(self, sample_pdf):
        result = PDFService.merge_pdfs([sample_pdf, sample_pdf])
        doc = fitz.open(stream=result, filetype="pdf")
        assert len(doc) == 6

class TestOptimize:
    def test_optimize_reduces_size(self, sample_pdf):
        result, orig, optimized = PDFService.optimize(sample_pdf)
        assert optimized <= orig
```

---

### Round 12: セキュリティ要件

**Sec. Watanabe**: セキュリティチェックリスト。

| # | 項目 | 対策 |
|---|------|------|
| S1 | ファイルアップロード検証 | MIMEタイプチェック + マジックバイト検証 (`%PDF-`) |
| S2 | ファイルサイズ制限 | 50MB上限（環境変数で設定可能） |
| S3 | レート制限 | IP単位で30リクエスト/分 |
| S4 | セッション有効期限 | 1時間で自動削除 |
| S5 | APIキー保護 | HTTPS必須、ログへの出力禁止 |
| S6 | CORS設定 | 本番ドメインのみ許可 |
| S7 | 入力バリデーション | Pydanticで全入力を型チェック |
| S8 | 一時ファイル管理 | メモリ上処理、ディスク書き込み最小化 |
| S9 | エラーメッセージ | 内部エラー詳細を外部に漏らさない |
| S10 | 依存関係監査 | `pip-audit` を CI に組み込み |

```python
# セキュリティミドルウェア
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # ファイルサイズチェック
        content_length = request.headers.get("content-length")
        max_size = int(os.getenv("MAX_UPLOAD_SIZE_MB", 50)) * 1024 * 1024
        if content_length and int(content_length) > max_size:
            raise HTTPException(413, "File too large")

        response = await call_next(request)

        # セキュリティヘッダー
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response
```

---

### 最終合意 (All Agents)

**Dir. Tanaka**: 全エージェントの議論を踏まえ、以下の実装フェーズで進める。

#### Phase 1 (MVP) - 1週目
- [ ] FastAPI + Jinja2 + HTMX基盤構築
- [ ] PDFアップロード・セッション管理
- [ ] ページプレビュー（サムネイルグリッド）
- [ ] ページ削除 (F2)
- [ ] ページ並び替え - ドラッグ&ドロップ (F3)
- [ ] PDFダウンロード
- [ ] Vercel初回デプロイ

#### Phase 2 (Core Features) - 2週目
- [ ] PDF結合 (F1) - 複数ファイルアップロード対応
- [ ] ファイル最適化 (F4)
- [ ] 透かし除去 (F5)
- [ ] ブランディング適用 (F6)
- [ ] Undo機能
- [ ] ダークモード

#### Phase 3 (AI Integration) - 3週目
- [ ] Gemini Banana Pro接続
- [ ] スライド解析 - Vision API (F9)
- [ ] スライド画像生成 (F9)
- [ ] SSEによるリアルタイム進捗表示
- [ ] ページサイズ統一 (F7)
- [ ] エリア画像置換 (F8)

#### Phase 4 (Polish) - 4週目
- [ ] レスポンシブ対応（モバイル）
- [ ] アクセシビリティ改善
- [ ] パフォーマンス最適化
- [ ] E2Eテスト
- [ ] セキュリティ監査
- [ ] 本番デプロイ・ドメイン設定

---

## 技術スタック最終版

| カテゴリ | 技術 | バージョン | 用途 |
|---------|------|-----------|------|
| Backend | FastAPI | 0.115+ | APIサーバー |
| Template | Jinja2 | 3.1+ | サーバーサイドHTML生成 |
| Frontend | HTMX | 2.0+ | 部分的DOM更新・AJAX |
| Frontend | Alpine.js | 3.14+ | クライアント状態管理 |
| CSS | Tailwind CSS | 4.0+ | ユーティリティCSS |
| Deploy | Vercel | - | サーバーレスホスティング |
| PDF | PyMuPDF (fitz) | 1.25+ | PDF操作全般 |
| Image | Pillow | 11.0+ | 画像処理 |
| AI | google-genai | 1.5+ | Gemini Banana Pro統合 |
| Validation | Pydantic | 2.10+ | データバリデーション |
| D&D | Sortable.js | 1.15+ | ドラッグ&ドロップ |
| Runtime | Python | 3.12+ | サーバーサイド言語 |

---

*本仕様書は7人のエージェント（Director, UI/UX Engineer, Designer, Python Expert, Software Engineer, Security Engineer, QA Engineer）による設計議論に基づき策定されました。*
