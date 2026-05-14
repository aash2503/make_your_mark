import os
import time
from typing import List, Optional

import google.generativeai as genai

from database import Assignment, Feedback

def _subject_prompt(subject: str) -> str:
    """Return a system prompt tailored to the subject."""
    base = (
        f"SYSTEM PERSONA: {subject.upper()} PRIMARY SCHOOL TEACHER'S ASSISTANT (TA).\n"
        f"Objective: Grade student responses with precision, provide structured pedagogical feedback, "
        f"and adhere strictly to MOE primary-level marking rubrics. Do NOT give sympathy marks.\n"
        f"Respond in raw LaTeX only, using xcolor and tcolorbox. "
        f"Do not provide explanation outside the LaTeX document.\n\n"
    )
    if subject.lower() == "english":
        return base + (
            "Marking Rubrics to Enforce:\n"
            "- AO1, AO2, AO3 applies.\n"
            "- Paper 1 (Situational Writing 15m): Task fulfillment requires all 6 bullet points. Missing one = direct penalty.\n"
            "- Paper 1 (Continuous Writing 40m): Must use at least one picture. Logical plot, climax, resolution.\n"
            "- Paper 2 (Grammar/Vocab/Cloze): Exact matches required.\n"
            "- Paper 2 (Synthesis & Transformation 10m): Meaning completely preserved or 0 marks.\n"
            "- Paper 2 (Comprehension OE): Direct retrieval rules, vocab in context.\n"
        )
    elif subject.lower() == "math" or subject.lower() == "mathematics":
        return base + (
            "Marking Rubrics to Enforce:\n"
            "- Method marks (M): Awarded for correct approach even if final answer is wrong.\n"
            "- Accuracy marks (A): Awarded for correct final answer.\n"
            "- Working must be shown for multi-step problems.\n"
            "- Units must be included where applicable (e.g. cm, kg, $).\n"
            "- Number statements and final answer statements required for word problems.\n"
            "- Common errors: misalignment in column addition, borrowing errors, multiplication table mistakes.\n"
        )
    elif subject.lower() == "science":
        return base + (
            "Marking Rubrics to Enforce:\n"
            "- Knowledge marks (K): Correct scientific facts, terminology, and concepts.\n"
            "- Application marks (A): Applying concepts to new scenarios.\n"
            "- Experimental design: Identifying variables (changed, measured, controlled).\n"
            "- Observation skills: Accurate recording of results, use of scientific vocabulary.\n"
            "- Common errors: Confusing similar concepts, incomplete explanations, missing scientific keywords.\n"
        )
    else:
        return base + (
            "Mark the student's work according to the provided rubric and answer key.\n"
            "Provide structured feedback with Glows (strengths), Grows (improvements), and Action Items.\n"
        )

# Default ranked model list — first choice is tried first, then fallback
# Use only confirmed available models for generateContent
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
    "NOT_FOUND",          # Model not available in this region/account
    "INVALID_ARGUMENT",   # Model name not recognized
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

    def _get_model(self, model_name: str, subject: str = "english"):
        """Get or create a cached GenerativeModel instance for a subject."""
        cache_key = f"{model_name}:{subject}"
        if cache_key not in self._model_cache:
            self._model_cache[cache_key] = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=_subject_prompt(subject),
                generation_config=genai.GenerationConfig(
                    temperature=0.0,
                    top_p=0.8,
                    max_output_tokens=4096,
                ),
            )
        return self._model_cache[cache_key]

    def _call(self, prompt: str, subject: str = "english") -> tuple[str, str]:
        """Call Gemini with ranked fallback. Returns (response_text, model_used)."""
        last_error = None

        for model_name in self.models:
            # Skip models in cooldown
            if model_name in self._cooldown:
                if time.time() < self._cooldown[model_name]:
                    continue
                del self._cooldown[model_name]

            try:
                model = self._get_model(model_name, subject)
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
                model = self._get_model(model_name, "english")
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
        subject: str = "english",
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
        result, _ = self._call(prompt, subject)
        return result

    def generate_answer_key(self, question_paper: str, subject: str = "English") -> str:
        """Auto-generate a marking rubric / answer key from a question paper."""
        prompt = (
            f"Subject: {subject}\n"
            f"Question Paper:\n{question_paper}\n\n"
            "You are an experienced examiner. Generate a detailed answer key and marking rubric "
            "for this question paper. Include:\n"
            "- Model answer for each question\n"
            "- Mark allocation per question\n"
            "- Key points that must appear for full marks\n"
            "- Common mistakes to penalise\n"
            "- Grade boundaries if applicable\n\n"
            "Return the answer key as clear structured text, not LaTeX."
        )
        result, _ = self._call(prompt, subject)
        return result

    def generate_class_report(
        self,
        class_name: str,
        assignment: Assignment,
        feedback_rows: List[Feedback],
        subject: str = "english",
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
        result, _ = self._call(prompt, subject)
        return result
