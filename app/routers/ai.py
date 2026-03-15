"""AI router - Gemini API proxy for slide vision analysis and image generation.

PDFs are processed client-side. Only page IMAGES are sent here for AI analysis.
"""
import base64

from fastapi import APIRouter, HTTPException, Form, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/ai", tags=["ai"])


class GenerateSlideRequest(BaseModel):
    xml: str
    api_key: str


class GenerateTextRequest(BaseModel):
    prompt: str
    api_key: str


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
    if len(image_bytes) > 5 * 1024 * 1024:
        raise HTTPException(413, "画像サイズが大きすぎます（上限5MB）")

    content_type = image.content_type or "image/png"
    if content_type not in ("image/png", "image/jpeg"):
        raise HTTPException(400, "PNGまたはJPEG画像のみ対応しています")

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key.strip())

        prompt = (
            "このプレゼンテーションスライド画像を詳細に分析し、以下のXML形式で構造化して出力してください。"
            "すべて日本語で記述してください。\n\n"
            "<slide>\n"
            "  <title>スライドのタイトル</title>\n"
            "  <subtitle>サブタイトル（あれば）</subtitle>\n"
            "  <content>\n"
            "    <section name=\"セクション名\">\n"
            "      <bullet>箇条書き項目</bullet>\n"
            "    </section>\n"
            "  </content>\n"
            "  <charts>グラフ・チャートの詳細説明（種類、データ、ラベル）</charts>\n"
            "  <images>画像・図形の説明（位置、内容）</images>\n"
            "  <layout>レイアウトの特徴（配置、構成）</layout>\n"
            "  <color_scheme>配色（メインカラー、アクセントカラー）</color_scheme>\n"
            "  <notes>その他の特記事項</notes>\n"
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
    """XMLからスライド画像を生成する。

    編集済みXMLをGemini画像生成APIに送信し、新しいスライド画像を返す。
    """
    if not req.api_key.strip():
        raise HTTPException(400, "APIキーを入力してください")

    if not req.xml.strip():
        raise HTTPException(400, "XMLが空です")

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=req.api_key.strip())

        prompt = (
            "以下のXMLに基づいて、プロフェッショナルなプレゼンテーションスライド画像を生成してください。\n"
            "- 白背景\n"
            "- 16:9のアスペクト比\n"
            "- クリーンでモダンなデザイン\n"
            "- 日本語テキストを正確に描画\n\n"
            f"XML:\n{req.xml}"
        )

        # 画像生成: Nano Banana Pro → Gemini 3 Pro のフォールバック
        generation_models = [
            "models/nano-banana-pro-preview",
            "models/gemini-3-pro-preview",
        ]

        for model_name in generation_models:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
                )
                if response.candidates:
                    for part in response.candidates[0].content.parts:
                        if part.inline_data:
                            img_base64 = base64.b64encode(part.inline_data.data).decode()
                            return {"image_base64": img_base64, "mime_type": part.inline_data.mime_type}
            except Exception:
                continue

        raise HTTPException(500, "画像生成に失敗しました。XMLを確認してください。")

    except ImportError:
        raise HTTPException(500, "google-genai ライブラリが利用できません")
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
