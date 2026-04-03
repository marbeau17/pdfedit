"""AI router - Gemini API proxy for slide vision analysis and image generation.

PDFs are processed client-side. Only page IMAGES are sent here for AI analysis.
"""
import asyncio
import base64
import json
import time
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Form, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/ai", tags=["ai"])

# ---------------------------------------------------------------------------
# In-memory task store for SSE progress tracking
# ---------------------------------------------------------------------------
_tasks: dict[str, dict] = {}
_TASK_TTL = 300  # 5 minutes


def _cleanup_tasks():
    """Remove completed/errored tasks older than TTL."""
    now = time.time()
    expired = [
        tid for tid, t in _tasks.items()
        if t.get("finished_at") and now - t["finished_at"] > _TASK_TTL
    ]
    for tid in expired:
        del _tasks[tid]


def _update_task(task_id: str, *, status: str, progress: int, message: str,
                 result: Optional[dict] = None, error: Optional[str] = None):
    """Update a task's state."""
    if task_id not in _tasks:
        return
    t = _tasks[task_id]
    t["status"] = status
    t["progress"] = progress
    t["message"] = message
    if result is not None:
        t["result"] = result
    if error is not None:
        t["error"] = error
    if status in ("complete", "error"):
        t["finished_at"] = time.time()


class GenerateSlideRequest(BaseModel):
    xml: str
    api_key: str
    number_of_images: int = 4
    model: str = "nano-banana-pro-preview"


class GenerateTextRequest(BaseModel):
    prompt: str
    api_key: str


class AnalyzeChunkRequest(BaseModel):
    text: str
    api_key: str
    chunk_index: int = 0
    total_chunks: int = 1
    previous_summary: str = ""


class AnalyzeSummaryRequest(BaseModel):
    chunk_results: list[str]
    api_key: str


class StartTaskRequest(BaseModel):
    task_type: str  # "vision-analyze" or "generate-slide"
    api_key: str
    # vision-analyze fields
    image_base64: Optional[str] = None
    image_mime: Optional[str] = "image/png"  # image/png, image/jpeg, or image/webp
    page_num: Optional[int] = 1
    # generate-slide fields
    xml: Optional[str] = None
    number_of_images: Optional[int] = 4
    model: Optional[str] = "nano-banana-pro-preview"


# ---------------------------------------------------------------------------
# SSE endpoints
# ---------------------------------------------------------------------------

@router.post("/start-task")
async def start_task(req: StartTaskRequest):
    """Start an AI task in background, return task_id for SSE tracking."""
    _cleanup_tasks()

    if not req.api_key.strip():
        raise HTTPException(400, "APIキーを入力してください")

    task_id = str(uuid.uuid4())
    _tasks[task_id] = {
        "status": "queued",
        "progress": 0,
        "message": "タスクをキューに追加しました",
        "result": None,
        "error": None,
        "finished_at": None,
        "created_at": time.time(),
    }

    if req.task_type == "vision-analyze":
        if not req.image_base64:
            raise HTTPException(400, "image_base64が必要です")
        asyncio.create_task(_run_vision_analyze(task_id, req))
    elif req.task_type == "generate-slide":
        if not req.xml or not req.xml.strip():
            raise HTTPException(400, "XMLが空です")
        asyncio.create_task(_run_generate_slide(task_id, req))
    else:
        raise HTTPException(400, f"不明なtask_type: {req.task_type}")

    return {"task_id": task_id}


@router.get("/status/{task_id}")
async def task_status_sse(task_id: str):
    """SSE endpoint that streams task progress events."""
    if task_id not in _tasks:
        raise HTTPException(404, "タスクが見つかりません")

    async def event_stream():
        last_status = None
        while True:
            task = _tasks.get(task_id)
            if not task:
                yield _sse_event("error", {"message": "タスクが消失しました"})
                break

            current = (task["status"], task["progress"], task["message"])
            if current != last_status:
                last_status = current
                payload = {
                    "status": task["status"],
                    "progress": task["progress"],
                    "message": task["message"],
                }
                if task["status"] == "complete" and task["result"]:
                    payload["result"] = task["result"]
                if task["status"] == "error" and task["error"]:
                    payload["error"] = task["error"]

                yield _sse_event(task["status"], payload)

            if task["status"] in ("complete", "error"):
                break

            await asyncio.sleep(0.3)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse_event(event: str, data: dict) -> str:
    """Format a single SSE event."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ---------------------------------------------------------------------------
# Background task runners
# ---------------------------------------------------------------------------

async def _run_vision_analyze(task_id: str, req: StartTaskRequest):
    """Background: run vision analysis and update task store."""
    try:
        _update_task(task_id, status="processing", progress=10,
                     message="画像をデコード中...")

        image_bytes = base64.b64decode(req.image_base64)
        if len(image_bytes) > 10 * 1024 * 1024:
            _update_task(task_id, status="error", progress=0,
                         message="画像サイズが大きすぎます（上限10MB）",
                         error="画像サイズが大きすぎます（上限10MB）")
            return

        content_type = req.image_mime or "image/png"

        _update_task(task_id, status="processing", progress=30,
                     message="Gemini Vision APIに送信中...")

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=req.api_key.strip())

        prompt = (
            "このプレゼンテーションスライド画像を詳細に分析し、以下のXML形式で構造化して出力してください。"
            "すべて日本語で記述してください。\n\n"
            "【重要】font-size属性のルール（単位: pt）:\n"
            "- タイトル: 36〜44pt（スライド内で最も大きい文字）\n"
            "- サブタイトル: 20〜28pt\n"
            "- 本文・箇条書き: 14〜18pt\n"
            "- グラフ注釈・補足: 10〜14pt\n"
            "- フッター・会社名・日付: 8〜12pt\n"
            "- 備考: 8〜10pt\n"
            "- 必ず「タイトル > サブタイトル > 本文 > 補足 > フッター」の大小関係を守ること\n\n"
            "セクションにはtype属性を付けてください:\n"
            "- type=\"main\": メインコンテンツ（箇条書きfont-size: 14-18pt）\n"
            "- type=\"footer\": フッター・宛先・発信者情報（箇条書きfont-size: 8-12pt）\n\n"
            "XMLタグ以外のテキストは出力しないでください。\n\n"
            "<slide>\n"
            "  <title font-size=\"36\">スライドのタイトル</title>\n"
            "  <subtitle font-size=\"24\">サブタイトル（あれば）</subtitle>\n"
            "  <content>\n"
            "    <section name=\"主要内容\" type=\"main\">\n"
            "      <bullet font-size=\"16\">本文の箇条書き項目</bullet>\n"
            "    </section>\n"
            "    <section name=\"発信者情報\" type=\"footer\">\n"
            "      <bullet font-size=\"10\">会社名・日付など</bullet>\n"
            "    </section>\n"
            "  </content>\n"
            "  <charts font-size=\"12\">グラフ・チャートの詳細説明（種類、データ、ラベル）</charts>\n"
            "  <images>画像・図形の説明（位置、内容）</images>\n"
            "  <layout>レイアウトの特徴（配置、構成）</layout>\n"
            "  <color_scheme>配色（メインカラー、アクセントカラー）</color_scheme>\n"
            "  <notes font-size=\"9\">その他の特記事項</notes>\n"
            "</slide>"
        )

        _update_task(task_id, status="processing", progress=50,
                     message="AIが画像を解析中...")

        response = await asyncio.to_thread(
            client.models.generate_content,
            model="models/nano-banana-pro-preview",
            contents=[
                prompt,
                types.Part.from_bytes(data=image_bytes, mime_type=content_type),
            ],
        )

        _update_task(task_id, status="complete", progress=100,
                     message="解析完了",
                     result={"page": req.page_num, "xml": response.text or ""})

    except Exception as e:
        _update_task(task_id, status="error", progress=0,
                     message=f"解析エラー: {str(e)}",
                     error=str(e))


async def _run_generate_slide(task_id: str, req: StartTaskRequest):
    """Background: run slide generation and update task store."""
    try:
        _update_task(task_id, status="processing", progress=10,
                     message="画像生成を準備中...")

        num_images = max(1, min(4, req.number_of_images or 4))
        model = req.model or "nano-banana-pro-preview"

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=req.api_key.strip())

        prompt = (
            "以下のXMLに基づいて、プロフェッショナルなプレゼンテーションスライド画像を生成してください。\n"
            "- 白背景\n"
            "- 16:9のアスペクト比\n"
            "- クリーンでモダンなデザイン\n"
            "- 日本語テキストを正確に描画\n"
            "- 各要素のfont-size属性をpt単位のフォントサイズとして反映\n\n"
            f"XML:\n{req.xml}"
        )

        _update_task(task_id, status="generating", progress=30,
                     message=f"{model}で画像を生成中...")

        images = []

        if model.startswith("imagen"):
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    client.models.generate_images,
                    model=model,
                    prompt=prompt,
                    config=types.GenerateImagesConfig(
                        number_of_images=num_images,
                        aspect_ratio="16:9",
                    ),
                ),
                timeout=240,
            )

            _update_task(task_id, status="generating", progress=80,
                         message="画像データを処理中...")

            if response.generated_images:
                for gen_img in response.generated_images:
                    img_bytes = gen_img.image.image_bytes
                    img_base64 = base64.b64encode(img_bytes).decode()
                    images.append({
                        "image_base64": img_base64,
                        "mime_type": "image/png",
                    })
        else:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    client.models.generate_content,
                    model=f"models/{model}",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                    ),
                ),
                timeout=240,
            )

            _update_task(task_id, status="generating", progress=80,
                         message="画像データを処理中...")

            if response.candidates:
                for candidate in response.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if part.inline_data and part.inline_data.data:
                                img_base64 = base64.b64encode(
                                    part.inline_data.data
                                ).decode()
                                mime_type = part.inline_data.mime_type or "image/png"
                                images.append({
                                    "image_base64": img_base64,
                                    "mime_type": mime_type,
                                })

        if not images:
            _update_task(task_id, status="error", progress=0,
                         message="画像生成に失敗しました。XMLを確認してください。",
                         error="画像生成に失敗しました")
            return

        _update_task(task_id, status="complete", progress=100,
                     message="生成完了",
                     result={"images": images})

    except asyncio.TimeoutError:
        _update_task(task_id, status="error", progress=0,
                     message="タイムアウト: 再試行してください。",
                     error="タイムアウト")
    except Exception as e:
        _update_task(task_id, status="error", progress=0,
                     message=f"生成エラー: {str(e)}",
                     error=str(e))


@router.post("/vision-analyze")
async def vision_analyze(
    image: UploadFile = File(...),
    api_key: str = Form(...),
    page_num: int = Form(1),
):
    """スライド画像をGemini Vision APIで解析し、構造化XMLを返す。

    クライアントがPDF.jsでページをCanvas描画→PNG化した画像を受信。
    PDFファイル全体はサーバーに送信されない。
    """
    if not api_key.strip():
        raise HTTPException(400, "APIキーを入力してください")

    image_bytes = await image.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(413, "画像サイズが大きすぎます（上限10MB）")

    content_type = image.content_type or "image/png"
    if content_type not in ("image/png", "image/jpeg", "image/webp"):
        raise HTTPException(400, "PNG、JPEG、またはWebP画像のみ対応しています")

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key.strip())

        prompt = (
            "このプレゼンテーションスライド画像を詳細に分析し、以下のXML形式で構造化して出力してください。"
            "すべて日本語で記述してください。\n\n"
            "【重要】font-size属性のルール（単位: pt）:\n"
            "- タイトル: 36〜44pt（スライド内で最も大きい文字）\n"
            "- サブタイトル: 20〜28pt\n"
            "- 本文・箇条書き: 14〜18pt\n"
            "- グラフ注釈・補足: 10〜14pt\n"
            "- フッター・会社名・日付: 8〜12pt\n"
            "- 備考: 8〜10pt\n"
            "- 必ず「タイトル > サブタイトル > 本文 > 補足 > フッター」の大小関係を守ること\n\n"
            "セクションにはtype属性を付けてください:\n"
            "- type=\"main\": メインコンテンツ（箇条書きfont-size: 14-18pt）\n"
            "- type=\"footer\": フッター・宛先・発信者情報（箇条書きfont-size: 8-12pt）\n\n"
            "XMLタグ以外のテキストは出力しないでください。\n\n"
            "<slide>\n"
            "  <title font-size=\"36\">スライドのタイトル</title>\n"
            "  <subtitle font-size=\"24\">サブタイトル（あれば）</subtitle>\n"
            "  <content>\n"
            "    <section name=\"主要内容\" type=\"main\">\n"
            "      <bullet font-size=\"16\">本文の箇条書き項目</bullet>\n"
            "    </section>\n"
            "    <section name=\"発信者情報\" type=\"footer\">\n"
            "      <bullet font-size=\"10\">会社名・日付など</bullet>\n"
            "    </section>\n"
            "  </content>\n"
            "  <charts font-size=\"12\">グラフ・チャートの詳細説明（種類、データ、ラベル）</charts>\n"
            "  <images>画像・図形の説明（位置、内容）</images>\n"
            "  <layout>レイアウトの特徴（配置、構成）</layout>\n"
            "  <color_scheme>配色（メインカラー、アクセントカラー）</color_scheme>\n"
            "  <notes font-size=\"9\">その他の特記事項</notes>\n"
            "</slide>"
        )

        # Vision解析にはNano Banana Proを使用
        response = client.models.generate_content(
            model="models/nano-banana-pro-preview",
            contents=[
                prompt,
                types.Part.from_bytes(data=image_bytes, mime_type=content_type),
            ],
        )

        xml_result = response.text if response.text else ""
        return {"page": page_num, "xml": xml_result}

    except ImportError:
        raise HTTPException(500, "google-genai ライブラリが利用できません")
    except Exception as e:
        raise HTTPException(500, f"解析エラー: {str(e)}")


@router.post("/generate-slide")
async def generate_slide(req: GenerateSlideRequest):
    """XMLからスライド画像を生成する（Gemini / Imagen 対応）。

    編集済みXMLをAI画像生成APIに送信し、候補画像を返す。
    Geminiモデル: generate_content API（1画像）
    Imagenモデル: generate_images API（複数候補）
    """
    if not req.api_key.strip():
        raise HTTPException(400, "APIキーを入力してください")

    if not req.xml.strip():
        raise HTTPException(400, "XMLが空です")

    num_images = max(1, min(4, req.number_of_images))

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=req.api_key.strip())

        prompt = (
            "以下のXMLに基づいて、プロフェッショナルなプレゼンテーションスライド画像を生成してください。\n"
            "- 白背景\n"
            "- 16:9のアスペクト比\n"
            "- クリーンでモダンなデザイン\n"
            "- 日本語テキストを正確に描画\n"
            "- 各要素のfont-size属性をpt単位のフォントサイズとして反映\n\n"
            f"XML:\n{req.xml}"
        )

        images = []

        if req.model.startswith("imagen"):
            # Imagen models: generate_images API (複数候補)
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    client.models.generate_images,
                    model=req.model,
                    prompt=prompt,
                    config=types.GenerateImagesConfig(
                        number_of_images=num_images,
                        aspect_ratio="16:9",
                    ),
                ),
                timeout=240,
            )

            if response.generated_images:
                for gen_img in response.generated_images:
                    img_bytes = gen_img.image.image_bytes
                    img_base64 = base64.b64encode(img_bytes).decode()
                    images.append({
                        "image_base64": img_base64,
                        "mime_type": "image/png",
                    })
        else:
            # Gemini models: generate_content API (1画像)
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    client.models.generate_content,
                    model=f"models/{req.model}",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                    ),
                ),
                timeout=240,
            )

            if response.candidates:
                for candidate in response.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if part.inline_data and part.inline_data.data:
                                img_base64 = base64.b64encode(
                                    part.inline_data.data
                                ).decode()
                                mime_type = part.inline_data.mime_type or "image/png"
                                images.append({
                                    "image_base64": img_base64,
                                    "mime_type": mime_type,
                                })

        if not images:
            raise HTTPException(500, "画像生成に失敗しました。XMLを確認してください。")

        return {"images": images}

    except ImportError:
        raise HTTPException(500, "google-genai ライブラリが利用できません")
    except asyncio.TimeoutError:
        raise HTTPException(504, "画像生成がタイムアウトしました。再試行してください。")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"生成エラー: {str(e)}")


@router.post("/analyze")
async def analyze_text(req: GenerateTextRequest):
    """テキストベースの汎用AI分析（後方互換）。"""
    if not req.api_key.strip():
        raise HTTPException(400, "APIキーを入力してください")

    try:
        from google import genai
        client = genai.Client(api_key=req.api_key.strip())
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=req.prompt,
        )
        return {"result": response.text if response.text else ""}
    except Exception as e:
        raise HTTPException(500, f"エラー: {str(e)}")


class AnalyzeTextTypeRequest(BaseModel):
    text: str
    api_key: str
    analysis_type: str = "summarize"


@router.post("/analyze-text")
async def analyze_text_typed(req: AnalyzeTextTypeRequest):
    """PDFテキストを指定タイプで解析する（要約・改善・翻訳・データ抽出）。"""

    if not req.api_key.strip():
        raise HTTPException(400, "APIキーを入力してください")

    if not req.text or not req.text.strip():
        raise HTTPException(400, "テキストが空です。PDFからテキストを抽出してください。")

    ANALYSIS_PROMPTS = {
        "summarize": (
            "以下のPDFドキュメントから抽出されたテキストを詳細に要約してください。\n\n"
            "以下の構成で出力してください:\n"
            "## 概要\n"
            "全体の概要を2〜3文で記述\n\n"
            "## 主要ポイント\n"
            "- 重要なポイントを箇条書き\n\n"
            "## 結論\n"
            "結論や次のステップがあれば記述\n\n"
            "すべて日本語で回答してください。\n\n"
            "【テキスト】\n"
        ),
        "improve": (
            "以下のPDFドキュメントから抽出されたテキストを分析し、改善提案を行ってください。\n\n"
            "以下の観点で評価・提案してください:\n"
            "## 構成の改善\n"
            "文書の構成や論理的な流れについて\n\n"
            "## 表現の改善\n"
            "文章の明瞭さ、簡潔さ、専門性について\n\n"
            "## 不足している内容\n"
            "追加すべき情報やデータについて\n\n"
            "## 具体的な修正案\n"
            "改善前→改善後の具体例を示してください\n\n"
            "すべて日本語で回答してください。\n\n"
            "【テキスト】\n"
        ),
        "translate": (
            "以下のPDFドキュメントから抽出されたテキストを英語に翻訳してください。\n\n"
            "ルール:\n"
            "- 自然で読みやすい英語にすること\n"
            "- 専門用語は適切に翻訳すること\n"
            "- 原文の構成を維持すること\n"
            "- 図表の参照なども適切に翻訳すること\n\n"
            "【テキスト】\n"
        ),
        "extract_data": (
            "以下のPDFドキュメントから抽出されたテキストから、構造化データを抽出してください。\n\n"
            "以下を抽出・整理してください:\n"
            "## 数値データ\n"
            "日付、金額、パーセンテージ、統計値など\n\n"
            "## 固有名詞\n"
            "人名、組織名、地名、製品名など\n\n"
            "## キーワード\n"
            "文書の主要キーワードをリストアップ\n\n"
            "## 表形式データ\n"
            "表やリストがあればMarkdownテーブルで再構成\n\n"
            "すべて日本語で回答してください。\n\n"
            "【テキスト】\n"
        ),
    }

    analysis_type = req.analysis_type if req.analysis_type in ANALYSIS_PROMPTS else "summarize"
    prompt = ANALYSIS_PROMPTS[analysis_type] + req.text

    try:
        from google import genai
        client = genai.Client(api_key=req.api_key.strip())
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.0-flash",
            contents=prompt,
        )
        result_text = response.text if response.text else ""
        return {"result": result_text, "analysis_type": analysis_type}
    except ImportError:
        raise HTTPException(500, "google-genai ライブラリが利用できません")
    except Exception as e:
        raise HTTPException(500, f"解析エラー: {str(e)}")


@router.post("/analyze-chunk")
async def analyze_chunk(req: AnalyzeChunkRequest):
    """チャンク単位でPDFテキストをAI分析する。

    大きなPDFテキストをチャンク分割して順次送信する際に使用。
    previous_summaryで前チャンクの要約を引き継ぎ、文脈を維持する。
    """
    if not req.api_key.strip():
        raise HTTPException(400, "APIキーを入力してください")

    if not req.text.strip():
        return {"result": "", "summary": "（テキストなし）"}

    try:
        from google import genai
        client = genai.Client(api_key=req.api_key.strip())

        # Build context-aware prompt
        context_part = ""
        if req.previous_summary.strip():
            context_part = (
                f"\n\n【前のチャンクまでの要約】\n{req.previous_summary}\n\n"
                "上記の文脈を踏まえて、以下のテキストを分析してください。\n"
            )

        chunk_label = ""
        if req.total_chunks > 1:
            chunk_label = f"（チャンク {req.chunk_index + 1}/{req.total_chunks}）"

        prompt = (
            f"以下はPDFドキュメントから抽出されたテキストです{chunk_label}。"
            "内容を詳細に分析し、以下の観点でまとめてください:\n"
            "1. 主要なトピックと要点\n"
            "2. 重要なデータ・数値\n"
            "3. 結論・提案事項\n"
            "4. 注意すべき点\n\n"
            "すべて日本語で回答してください。"
            f"{context_part}\n\n"
            f"【テキスト】\n{req.text}"
        )

        response = await asyncio.wait_for(
            asyncio.to_thread(
                client.models.generate_content,
                model="gemini-2.0-flash",
                contents=prompt,
            ),
            timeout=120,
        )

        result_text = response.text if response.text else ""

        # Generate a brief summary for context continuity
        summary = ""
        if req.total_chunks > 1:
            summary_prompt = (
                "以下の分析結果を3〜5文で簡潔に要約してください。"
                "次のチャンク分析の文脈として使います。\n\n"
                f"{result_text}"
            )
            summary_resp = await asyncio.wait_for(
                asyncio.to_thread(
                    client.models.generate_content,
                    model="gemini-2.0-flash",
                    contents=summary_prompt,
                ),
                timeout=60,
            )
            summary = summary_resp.text if summary_resp.text else ""

        return {"result": result_text, "summary": summary}

    except asyncio.TimeoutError:
        raise HTTPException(504, "分析がタイムアウトしました。再試行してください。")
    except ImportError:
        raise HTTPException(500, "google-genai ライブラリが利用できません")
    except Exception as e:
        raise HTTPException(500, f"分析エラー: {str(e)}")


@router.post("/analyze-summary")
async def analyze_summary(req: AnalyzeSummaryRequest):
    """複数チャンクの分析結果を統合し、統一サマリーを生成する。"""
    if not req.api_key.strip():
        raise HTTPException(400, "APIキーを入力してください")

    if not req.chunk_results or len(req.chunk_results) == 0:
        return {"result": ""}

    # Single chunk - no need to summarize
    if len(req.chunk_results) == 1:
        return {"result": req.chunk_results[0]}

    try:
        from google import genai
        client = genai.Client(api_key=req.api_key.strip())

        combined = "\n\n---\n\n".join(
            f"【パート {i+1}/{len(req.chunk_results)}】\n{r}"
            for i, r in enumerate(req.chunk_results)
        )

        prompt = (
            "以下は大きなPDFドキュメントを複数パートに分割してAI分析した結果です。\n"
            "これらを統合し、ドキュメント全体の包括的な分析レポートを作成してください。\n\n"
            "以下の構成で出力してください:\n"
            "## 全体概要\n"
            "## 主要な発見・要点\n"
            "## 重要なデータ・数値\n"
            "## 結論・提案事項\n"
            "## 注意すべき点\n\n"
            "重複を排除し、すべて日本語で回答してください。\n\n"
            f"{combined}"
        )

        response = await asyncio.wait_for(
            asyncio.to_thread(
                client.models.generate_content,
                model="gemini-2.0-flash",
                contents=prompt,
            ),
            timeout=120,
        )

        return {"result": response.text if response.text else ""}

    except asyncio.TimeoutError:
        raise HTTPException(504, "統合分析がタイムアウトしました。再試行してください。")
    except ImportError:
        raise HTTPException(500, "google-genai ライブラリが利用できません")
    except Exception as e:
        raise HTTPException(500, f"統合エラー: {str(e)}")
