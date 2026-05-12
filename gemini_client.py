import os
from typing import List

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


class GeminiClient:
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        if not api_key:
            raise ValueError(
                "Gemini API key is required. Set GOOGLE_API_KEY in environment or Streamlit secrets."
            )
        genai.configure(api_key=api_key)
        # Normalise legacy model names
        if model in ("text-bison-1", "text-bison-001", "gemini-pro"):
            model = "gemini-1.5-flash"
        self.model_name = model
        self._model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=SYSTEM_INSTRUCTION,
            generation_config=genai.GenerationConfig(
                temperature=0.0,
                top_p=0.8,
                max_output_tokens=4096,
            ),
        )

    def _call(self, prompt: str) -> str:
        response = self._model.generate_content(prompt)
        return response.text.strip()

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
        return self._call(prompt)

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
        return self._call(prompt)
