"""AI router - Gemini API proxy for text analysis.

PDFs are processed client-side. Only extracted text is sent here.
"""
import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/ai", tags=["ai"])


class PageText(BaseModel):
    page: int
    text: str


class AnalyzeRequest(BaseModel):
    pages: list[PageText]
    api_key: str


class GenerateRequest(BaseModel):
    prompt: str
    api_key: str


@router.post("/analyze")
async def analyze_text(req: AnalyzeRequest):
    """Analyze extracted text using Gemini API.

    Receives pre-extracted text from client-side PDF.js.
    No PDF files are uploaded or processed server-side.
    """
    if not req.api_key.strip():
        raise HTTPException(400, "API key is required")

    try:
        from google import genai
        client = genai.Client(api_key=req.api_key.strip())

        results = []
        for page_text in req.pages:
            prompt = (
                f"Analyze this presentation slide text. Provide a structured analysis in Japanese. "
                f"Include: summary, key points, suggestions for improvement.\n\n"
                f"Page {page_text.page} text:\n{page_text.text}"
            )
            try:
                response = client.models.generate_content(
                    model="models/gemini-2.0-flash",
                    contents=prompt,
                )
                analysis = response.text if response.text else "Analysis not available"
            except Exception as e:
                analysis = f"Error: {str(e)}"

            results.append({
                "page": page_text.page,
                "analysis": analysis,
            })

        return {"results": results}

    except ImportError:
        raise HTTPException(500, "google-genai library not available")
    except Exception as e:
        raise HTTPException(500, f"AI processing error: {str(e)}")


@router.post("/generate")
async def generate_content(req: GenerateRequest):
    """Generate content using Gemini API."""
    if not req.api_key.strip():
        raise HTTPException(400, "API key is required")

    try:
        from google import genai
        client = genai.Client(api_key=req.api_key.strip())

        response = client.models.generate_content(
            model="models/gemini-2.0-flash",
            contents=req.prompt,
        )
        return {"result": response.text if response.text else ""}
    except Exception as e:
        raise HTTPException(500, f"Generation error: {str(e)}")
