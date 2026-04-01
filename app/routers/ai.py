"""AI router - Gemini API proxy for slide vision analysis and image generation.

PDFs are processed client-side. Only page IMAGES are sent here for AI analysis.
"""
import asyncio
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
            "- 日本語テキストを正確に描画\n"
            "- 各要素のfont-size属性をpt単位のフォントサイズとして反映\n\n"
            f"XML:\n{req.xml}"
        )

        # 画像生成: Gemini 3 Pro Image
        response = await asyncio.wait_for(
            asyncio.to_thread(
                client.models.generate_content,
                model="models/gemini-3-pro-image-preview",
                contents=prompt,
                config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
            ),
            timeout=240,
        )
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    img_base64 = base64.b64encode(part.inline_data.data).decode()
                    return {"image_base64": img_base64, "mime_type": part.inline_data.mime_type}

        raise HTTPException(500, "画像生成に失敗しました。XMLを確認してください。")

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
