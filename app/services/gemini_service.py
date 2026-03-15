"""Gemini AI integration service for slide analysis and generation."""
import asyncio
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class AITask:
    """Represents an async AI task with progress tracking."""

    def __init__(self, task_id: str, task_type: str):
        self.task_id = task_id
        self.task_type = task_type
        self.status = TaskStatus.PENDING
        self.progress: int = 0
        self.result: dict | None = None
        self.error: str | None = None
        self.total_pages: int = 0
        self.completed_pages: int = 0


# In-memory task store
_tasks: dict[str, AITask] = {}


VISION_MODEL = "models/gemini-2.0-flash"
GENERATION_MODELS = [
    "models/gemini-2.0-flash",
]


class GeminiService:
    """Gemini API integration for slide analysis and image generation."""

    def __init__(self, api_key: str):
        from google import genai
        self.client = genai.Client(api_key=api_key)
        self._genai_types = None

    @property
    def types(self):
        if self._genai_types is None:
            from google.genai import types
            self._genai_types = types
        return self._genai_types

    def analyze_slide(self, image_bytes: bytes) -> str | None:
        """Analyze a slide image and convert to structured XML.

        Args:
            image_bytes: PNG image bytes of the slide

        Returns:
            XML string describing the slide content, or None on failure
        """
        prompt = (
            "Analyze this presentation slide image in detail and convert it to structured XML. "
            "Include all elements: title, subtitle, body text, bullet points, charts, tables, "
            "images (describe them), layout information. Output JAPANESE text only. "
            "Wrap everything in <slide> root element."
        )
        try:
            response = self.client.models.generate_content(
                model=VISION_MODEL,
                contents=[
                    prompt,
                    self.types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                ],
            )
            return response.text if response.text else None
        except Exception as e:
            print(f"Vision API error: {e}")
            return None

    def generate_slide_image(self, xml_content: str) -> bytes | None:
        """Generate a slide image from XML description.

        Args:
            xml_content: XML describing the slide content

        Returns:
            Image bytes (PNG/JPEG), or None on failure
        """
        prompt = (
            f"Create a professional presentation slide image based on this XML description. "
            f"Use a clean WHITE background, professional typography, and modern design. "
            f"The slide should be in 16:9 aspect ratio. "
            f"XML:\n{xml_content}"
        )
        for model in GENERATION_MODELS:
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt,
                )
                if response.candidates:
                    for part in response.candidates[0].content.parts:
                        if part.inline_data:
                            return part.inline_data.data
            except Exception as e:
                print(f"Generation API error with {model}: {e}")
                continue
        return None

    def analyze_and_suggest(self, image_bytes: bytes, instruction: str = "") -> str | None:
        """Analyze a slide and suggest improvements.

        Args:
            image_bytes: PNG image bytes
            instruction: Optional user instruction for modifications

        Returns:
            Modified XML string, or None on failure
        """
        base_prompt = (
            "Analyze this presentation slide. Output structured XML with <slide> root element. "
            "Include all visual elements. JAPANESE text only."
        )
        if instruction:
            base_prompt += f"\n\nAdditional instruction from user: {instruction}"

        try:
            response = self.client.models.generate_content(
                model=VISION_MODEL,
                contents=[
                    base_prompt,
                    self.types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                ],
            )
            return response.text if response.text else None
        except Exception as e:
            print(f"Analyze API error: {e}")
            return None


def get_task(task_id: str) -> AITask | None:
    """Get an AI task by ID."""
    return _tasks.get(task_id)


def create_task(task_id: str, task_type: str) -> AITask:
    """Create a new AI task."""
    task = AITask(task_id, task_type)
    _tasks[task_id] = task
    return task


def cleanup_tasks():
    """Remove completed/failed tasks older than 10 minutes."""
    # Simple cleanup - in production use TTL
    if len(_tasks) > 100:
        completed = [tid for tid, t in _tasks.items()
                     if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)]
        for tid in completed[:50]:
            _tasks.pop(tid, None)
