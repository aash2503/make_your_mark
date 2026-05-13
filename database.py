import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from supabase import Client, create_client


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class ClassRecord:
    id: int
    name: str
    created_at: str
    teacher_id: Optional[int] = None


@dataclass
class Student:
    id: int
    class_id: int
    name: str
    created_at: str


@dataclass
class Assignment:
    id: int
    class_id: int
    title: str
    context: str
    answer_key: str
    created_at: str
    answer_key_source: str = "manual"
    context_files: str = "[]"
    answer_key_files: str = "[]"


@dataclass
class Submission:
    id: int
    student_id: int
    assignment_id: int
    submission_text: str
    status: str
    created_at: str
    file_paths: str = "[]"


@dataclass
class Feedback:
    id: int
    student_id: int
    assignment_id: int
    draft_number: int
    feedback_tex: str
    feedback_json: Dict[str, Any]
    created_at: str
    feedback_pdf_path: Optional[str] = None
    student_name: Optional[str] = None


# ── Database — Supabase-backed ────────────────────────────────────────────────

class Database:
    def __init__(self, url: str = None, key: str = None):
        self.url = url or os.environ.get("SUPABASE_URL") or ""
        self.key = key or os.environ.get("SUPABASE_KEY") or ""
        if not self.url or not self.key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_KEY are required. "
                "Set them in .streamlit/secrets.toml or environment variables."
            )
        self.client: Client = create_client(self.url, self.key)
        self._ensure_tables()

    def _ensure_tables(self):
        """Verify Supabase connectivity — run supabase_schema.sql first."""
        try:
            self.client.table("teachers").select("id", count="exact").limit(0).execute()
        except Exception as exc:
            raise RuntimeError(
                f"Supabase connection failed or tables not set up. "
                f"Run supabase_schema.sql in the Supabase SQL Editor first.\n"
                f"Error: {exc}"
            )

    @staticmethod
    def _hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    @staticmethod
    def _generate_teacher_code() -> str:
        import random, string
        return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _row_to_dict(row) -> dict:
        if hasattr(row, "model_dump"):
            return row.model_dump()
        if isinstance(row, dict):
            return row
        return dict(row)

    # ── Teacher methods ───────────────────────────────────────────────────────

    def create_teacher(self, email: str, display_name: str, password: str = None) -> int:
        pw_hash = self._hash_password(password) if password else None
        for _ in range(5):
            code = self._generate_teacher_code()
            existing = self.client.table("teachers").select("id").eq("teacher_code", code).execute()
            if existing.data:
                continue
            result = self.client.table("teachers").insert({
                "email": email.strip().lower(),
                "display_name": display_name.strip(),
                "password_hash": pw_hash,
                "teacher_code": code,
                "created_at": self._now(),
            }).execute()
            return result.data[0]["id"]
        raise RuntimeError("Failed to generate a unique teacher code.")

    def get_teacher_by_email(self, email: str):
        result = self.client.table("teachers").select("*").eq("email", email.strip().lower()).execute()
        return self._row_to_dict(result.data[0]) if result.data else None

    def get_teacher_by_code(self, code: str):
        result = self.client.table("teachers").select("*").eq("teacher_code", code.strip().upper()).execute()
        return self._row_to_dict(result.data[0]) if result.data else None

    def verify_teacher_password(self, email: str, password: str) -> Optional[dict]:
        teacher = self.get_teacher_by_email(email)
        if not teacher or not teacher.get("password_hash"):
            return None
        if teacher["password_hash"] == self._hash_password(password):
            return teacher
        return None

    def update_teacher_profile(self, teacher_id: int, display_name: str, school: str, subject: str, avatar: str):
        self.client.table("teachers").update({
            "display_name": display_name.strip(),
            "school": school.strip(),
            "subject": subject.strip(),
            "avatar": avatar,
            "setup_complete": True,
        }).eq("id", teacher_id).execute()

    # ── Class methods ─────────────────────────────────────────────────────────

    def add_class(self, name: str, teacher_id: int = None) -> int:
        result = self.client.table("classes").insert({
            "name": name.strip(),
            "teacher_id": teacher_id,
            "created_at": self._now(),
        }).execute()
        return result.data[0]["id"]

    def list_classes(self, teacher_id: int = None) -> List[ClassRecord]:
        query = self.client.table("classes").select("*").order("name")
        if teacher_id:
            query = query.eq("teacher_id", teacher_id)
        result = query.execute()
        return [ClassRecord(**self._row_to_dict(r)) for r in (result.data or [])]

    def get_class(self, class_id: int) -> ClassRecord:
        result = self.client.table("classes").select("*").eq("id", class_id).single().execute()
        return ClassRecord(**self._row_to_dict(result.data))

    # ── Student methods ───────────────────────────────────────────────────────

    def add_student(self, class_id: int, name: str) -> int:
        result = self.client.table("students").insert({
            "class_id": class_id,
            "name": name.strip(),
            "created_at": self._now(),
        }).execute()
        return result.data[0]["id"]

    def list_students(self, class_id: int) -> List[Student]:
        result = self.client.table("students").select("*").eq("class_id", class_id).order("name").execute()
        return [Student(**self._row_to_dict(r)) for r in (result.data or [])]

    def get_student(self, student_id: int) -> Student:
        result = self.client.table("students").select("*").eq("id", student_id).single().execute()
        return Student(**self._row_to_dict(result.data))

    # ── Assignment methods ────────────────────────────────────────────────────

    def add_assignment(self, class_id: int, title: str, context: str, answer_key: str,
                        answer_key_source: str = "manual") -> int:
        result = self.client.table("assignments").insert({
            "class_id": class_id,
            "title": title.strip(),
            "context": context.strip(),
            "answer_key": answer_key.strip(),
            "answer_key_source": answer_key_source,
            "created_at": self._now(),
        }).execute()
        return result.data[0]["id"]

    def list_assignments(self, class_id: int) -> List[Assignment]:
        result = self.client.table("assignments").select("*").eq("class_id", class_id).order("created_at", desc=True).execute()
        return [Assignment(**self._row_to_dict(r)) for r in (result.data or [])]

    def get_assignment(self, assignment_id: int) -> Assignment:
        result = self.client.table("assignments").select("*").eq("id", assignment_id).single().execute()
        return Assignment(**self._row_to_dict(result.data))

    # ── Feedback methods ──────────────────────────────────────────────────────

    def add_feedback(self, student_id: int, assignment_id: int, draft_number: int,
                     feedback_tex: str, feedback_json: Any, feedback_pdf_path: str = None) -> int:
        result = self.client.table("feedback").insert({
            "student_id": student_id,
            "assignment_id": assignment_id,
            "draft_number": draft_number,
            "feedback_tex": feedback_tex,
            "feedback_json": json.dumps(feedback_json),
            "feedback_pdf_path": feedback_pdf_path,
            "created_at": self._now(),
        }).execute()
        return result.data[0]["id"]

    def get_feedback_history(self, student_id: int, assignment_id: int) -> List[Feedback]:
        result = self.client.table("feedback").select("*") \
            .eq("student_id", student_id) \
            .eq("assignment_id", assignment_id) \
            .order("draft_number") \
            .execute()
        feedback_list = []
        for row in (result.data or []):
            data = self._row_to_dict(row)
            if isinstance(data.get("feedback_json"), str):
                data["feedback_json"] = json.loads(data["feedback_json"])
            feedback_list.append(Feedback(**data))
        return feedback_list

    def get_feedback_for_class_assignment(self, class_id: int, assignment_id: int) -> List[Feedback]:
        result = self.client.table("feedback").select("*, students!inner(name)") \
            .eq("assignment_id", assignment_id) \
            .eq("students.class_id", class_id) \
            .order("draft_number") \
            .execute()
        feedback_list = []
        for row in (result.data or []):
            data = self._row_to_dict(row)
            students_data = data.pop("students", None)
            if isinstance(students_data, dict):
                data["student_name"] = students_data.get("name")
            elif isinstance(students_data, list) and students_data:
                data["student_name"] = students_data[0].get("name")
            if isinstance(data.get("feedback_json"), str):
                data["feedback_json"] = json.loads(data["feedback_json"])
            feedback_list.append(Feedback(**data))
        return feedback_list

    # ── Submission methods (batch grading queue) ───────────────────────────────

    def add_submission(self, student_id: int, assignment_id: int, text: str,
                       file_paths: list = None) -> int:
        result = self.client.table("submissions").insert({
            "student_id": student_id,
            "assignment_id": assignment_id,
            "submission_text": text,
            "file_paths": json.dumps(file_paths or []),
            "status": "pending",
            "created_at": self._now(),
        }).execute()
        return result.data[0]["id"]

    def list_pending_submissions(self, assignment_id: int) -> List[Submission]:
        result = self.client.table("submissions").select("*, students!inner(name)") \
            .eq("assignment_id", assignment_id) \
            .eq("status", "pending") \
            .order("created_at") \
            .execute()
        subs = []
        for row in (result.data or []):
            data = self._row_to_dict(row)
            students_data = data.pop("students", None)
            if isinstance(students_data, dict):
                data["student_name"] = students_data.get("name")
            subs.append(Submission(**data))
        return subs

    def mark_submission_graded(self, submission_id: int):
        self.client.table("submissions").update({"status": "graded"}).eq("id", submission_id).execute()

    def get_pending_count(self, assignment_id: int) -> int:
        result = self.client.table("submissions").select("id", count="exact") \
            .eq("assignment_id", assignment_id).eq("status", "pending").execute()
        return result.count or 0

    # ── PDF Storage ───────────────────────────────────────────────────────────

    def upload_pdf(self, file_path: Path, bucket: str = "pdfs") -> str:
        self._ensure_bucket(bucket)
        file_name = file_path.name
        with open(file_path, "rb") as f:
            self.client.storage.from_(bucket).upload(
                path=file_name,
                file=f,
                file_options={"content-type": "application/pdf", "upsert": "true"},
            )
        return self.client.storage.from_(bucket).get_public_url(file_name)

    def _ensure_bucket(self, bucket: str):
        try:
            self.client.storage.create_bucket(bucket, {"public": True})
        except Exception:
            pass

    def download_pdf(self, file_name: str, output_dir: Path, bucket: str = "pdfs") -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / file_name
        file_data = self.client.storage.from_(bucket).download(file_name)
        output_path.write_bytes(file_data)
        return output_path
