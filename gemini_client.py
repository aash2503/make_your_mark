import os
import time
from typing import List, Optional

import google.generativeai as genai

from database import Assignment, Feedback

SYSTEM_INSTRUCTION = (
    "SYSTEM PERSONA: PSLE ENGLISH TEACHER'S ASSISTANT (TA).\n"
    "Role: You are an expert TA specializing in the Singapore MOE PSLE English syllabus.\n"
    "Objective: Grade student responses with absolute precision, provide structured pedagogical feedback, "
    "track development, and adhere strictly to SEAB marking rubrics. Do NOT give sympathy marks.\n\n"
    "Marking Rubrics to Enforce:\n"
    "- AO1, AO2, AO3 applies.\n"
    "- Paper 1 (Situational Writing 15m): Task fulfillment requires all 6 bullet points. "
    "Missing one = direct penalty. Accuracy, tone, and context are paramount.\n"
    "- Paper 1 (Continuous Writing 40m): Must use at least one picture. Logical plot, climax, resolution. "
    "Varied sentences, SVA, past tense consistency, 'show, don't tell' techniques.\n"
    "- Paper 2 (Grammar/Vocab/Cloze): Exact matches required.\n"
    "- Paper 2 (Synthesis & Transformation 10m): CRITICAL STRICTNESS. Meaning completely preserved or 0 marks. "
    "Any grammar/tense error = 0 marks. Missing commas/spelling = -0.5 mark.\n"
    "- Paper 2 (Comprehension OE): Direct retrieval rules, vocab in context, "
    "true/false+reason (both must be correct for marks).\n\n"
    "Respond in raw LaTeX only, using xcolor and tcolorbox. "
    "Do not provide explanation outside the LaTeX document."
)

# Default ranked model list — first choice is tried first, then fallback
DEFAULT_MODEL_RANK = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]

# Errors that should trigger a fallback (rate limiting, overloaded, etc.)
_FALLBACK_ERRORS = (
    "429",                # Rate limit
    "503",                # Service unavailable
    "RESOURCE_EXHAUSTED", # Quota exhausted
    "UNAVAILABLE",        # Temporarily unavailable
    "INTERNAL",           # Internal server error
    "DEADLINE_EXCEEDED",  # Timeout
)


def _is_fallback_error(error: Exception) -> bool:
    """Return True if this error should trigger model fallback."""
    msg = str(error).upper()
    return any(token in msg for token in _FALLBACK_ERRORS)


class GeminiClient:
    def __init__(self, api_key: str, models: Optional[List[str]] = None):
        if not api_key:
            raise ValueError(
                "Gemini API key is required. Set GOOGLE_API_KEY in environment or Streamlit secrets."
            )
        genai.configure(api_key=api_key)
        self.models = models or DEFAULT_MODEL_RANK
        self._model_cache: dict = {}       # model_name → GenerativeModel
        self._cooldown: dict = {}          # model_name → timestamp when cooldown ends
        self._cooldown_seconds = 60        # how long to skip a rate-limited model
        self.last_model_used: Optional[str] = None

    def _get_model(self, model_name: str):
        """Get or create a cached GenerativeModel instance."""
        if model_name not in self._model_cache:
            self._model_cache[model_name] = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=SYSTEM_INSTRUCTION,
                generation_config=genai.GenerationConfig(
                    temperature=0.0,
                    top_p=0.8,
                    max_output_tokens=4096,
                ),
            )
        return self._model_cache[model_name]

    def _call(self, prompt: str) -> tuple[str, str]:
        """Call Gemini with ranked fallback. Returns (response_text, model_used)."""
        last_error = None

        for model_name in self.models:
            # Skip models in cooldown
            if model_name in self._cooldown:
                if time.time() < self._cooldown[model_name]:
                    continue
                del self._cooldown[model_name]

            try:
                model = self._get_model(model_name)
                response = model.generate_content(prompt)
                self.last_model_used = model_name
                return response.text.strip(), model_name

            except Exception as exc:
                last_error = exc
                if _is_fallback_error(exc):
                    self._cooldown[model_name] = time.time() + self._cooldown_seconds
                    continue
                # Non-fallback error — re-raise immediately
                raise

        # All models exhausted
        raise RuntimeError(
            f"All Gemini models exhausted. Last error: {last_error}. "
            f"Models tried: {self.models}"
        )

    @property
    def model_name(self) -> str:
        """Return the primary (first-choice) model name."""
        return self.models[0] if self.models else "unknown"

    def extract_text_from_image(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        """OCR fallback: use Gemini Vision to extract text from an image."""
        prompt = "Extract all text from this image verbatim. Return ONLY the extracted text, no commentary."
        for model_name in self.models:
            if model_name in self._cooldown:
                if time.time() < self._cooldown[model_name]:
                    continue
                del self._cooldown[model_name]
            try:
                model = self._get_model(model_name)
                response = model.generate_content([
                    {"mime_type": mime_type, "data": image_bytes},
                    prompt,
                ])
                self.last_model_used = model_name
                return response.text.strip()
            except Exception as exc:
                if _is_fallback_error(exc):
                    self._cooldown[model_name] = time.time() + self._cooldown_seconds
                    continue
                raise
        raise RuntimeError("All Gemini models exhausted for OCR.")

    def generate_student_feedback(
        self,
        student_name: str,
        class_name: str,
        assignment: Assignment,
        submission_text: str,
        history: str,
    ) -> str:
        prompt = (
            f"Assignment Title: {assignment.title}\n"
            f"Assignment Context:\n{assignment.context}\n"
            f"Answer Key / Rubric:\n{assignment.answer_key}\n"
            f"Student Name: {student_name}\n"
            f"Class Name: {class_name}\n"
            f"Student Submission:\n{submission_text}\n"
            f"Previous feedback history:\n{history or 'None'}\n\n"
            "Produce a clean LaTeX feedback document with a header, inline corrections, "
            "Glows, Grows, and Action Items. "
            "Use xcolor and tcolorbox for styling. Return only raw LaTeX code."
        )
        result, _ = self._call(prompt)
        return result

    def generate_class_report(
        self,
        class_name: str,
        assignment: Assignment,
        feedback_rows: List[Feedback],
    ) -> str:
        history_block = []
        for feedback in feedback_rows:
            student_label = feedback.student_name or str(feedback.student_id)
            feedback_excerpt = feedback.feedback_tex[:600].replace("%", "\\%").replace("\n", " ")
            history_block.append(f"Student {student_label}: {feedback_excerpt}")
        data_block = "\n".join(history_block)

        prompt = (
            f"Class Name: {class_name}\n"
            f"Assignment Title: {assignment.title}\n"
            f"Assignment Context:\n{assignment.context}\n"
            f"Answer Key / Rubric:\n{assignment.answer_key}\n"
            f"Collected graded student feedback excerpts:\n{data_block}\n\n"
            "Generate a raw LaTeX document for a Class Competency Report. "
            "Use xcolor, tcolorbox, geometry, and amssymb. "
            "Include an Executive Summary, Student Tier Breakdown with direct quotes, "
            "Best Techniques Observed, Class-Wide Trends, and a Progression Table comparing Draft 1 vs Draft 2. "
            "Return only LaTeX code and do not include plain text explanation outside LaTeX."
        )
        result, _ = self._call(prompt)
        return result
