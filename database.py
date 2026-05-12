import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ClassRecord:
    id: int
    name: str
    created_at: str


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


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(class_id) REFERENCES classes(id)
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                context TEXT NOT NULL,
                answer_key TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(class_id) REFERENCES classes(id)
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                assignment_id INTEGER NOT NULL,
                draft_number INTEGER NOT NULL,
                feedback_tex TEXT NOT NULL,
                feedback_json TEXT NOT NULL,
                feedback_pdf_path TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(student_id) REFERENCES students(id),
                FOREIGN KEY(assignment_id) REFERENCES assignments(id)
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS teachers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                password_hash TEXT,
                google_sub TEXT,
                school TEXT,
                subject TEXT,
                avatar TEXT DEFAULT '🧑‍🏫',
                setup_complete INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    # ── Teacher account methods ───────────────────────────────────────────────

    @staticmethod
    def _hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def create_teacher(self, email: str, display_name: str, password: str = None, google_sub: str = None) -> int:
        cursor = self.conn.cursor()
        pw_hash = self._hash_password(password) if password else None
        cursor.execute(
            "INSERT INTO teachers (email, display_name, password_hash, google_sub, created_at) VALUES (?, ?, ?, ?, ?)",
            (email.strip().lower(), display_name.strip(), pw_hash, google_sub, datetime.utcnow().isoformat()),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_teacher_by_email(self, email: str):
        cursor = self.conn.cursor()
        row = cursor.execute("SELECT * FROM teachers WHERE email = ?", (email.strip().lower(),)).fetchone()
        return dict(row) if row else None

    def get_teacher_by_google_sub(self, google_sub: str):
        cursor = self.conn.cursor()
        row = cursor.execute("SELECT * FROM teachers WHERE google_sub = ?", (google_sub,)).fetchone()
        return dict(row) if row else None

    def verify_teacher_password(self, email: str, password: str) -> Optional[dict]:
        teacher = self.get_teacher_by_email(email)
        if not teacher:
            return None
        if teacher["password_hash"] == self._hash_password(password):
            return teacher
        return None

    def update_teacher_profile(self, teacher_id: int, display_name: str, school: str, subject: str, avatar: str):
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE teachers SET display_name=?, school=?, subject=?, avatar=?, setup_complete=1 WHERE id=?",
            (display_name.strip(), school.strip(), subject.strip(), avatar, teacher_id),
        )
        self.conn.commit()

    def teacher_exists(self) -> bool:
        cursor = self.conn.cursor()
        row = cursor.execute("SELECT COUNT(*) as cnt FROM teachers").fetchone()
        return row["cnt"] > 0

    def add_class(self, name: str) -> int:
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO classes (name, created_at) VALUES (?, ?)",
            (name.strip(), datetime.utcnow().isoformat()),
        )
        self.conn.commit()
        return cursor.lastrowid

    def list_classes(self) -> List[ClassRecord]:
        cursor = self.conn.cursor()
        rows = cursor.execute("SELECT * FROM classes ORDER BY name").fetchall()
        return [ClassRecord(**row) for row in rows]

    def get_class(self, class_id: int) -> ClassRecord:
        cursor = self.conn.cursor()
        row = cursor.execute("SELECT * FROM classes WHERE id = ?", (class_id,)).fetchone()
        return ClassRecord(**row)

    def add_student(self, class_id: int, name: str) -> int:
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO students (class_id, name, created_at) VALUES (?, ?, ?)",
            (class_id, name.strip(), datetime.utcnow().isoformat()),
        )
        self.conn.commit()
        return cursor.lastrowid

    def list_students(self, class_id: int) -> List[Student]:
        cursor = self.conn.cursor()
        rows = cursor.execute(
            "SELECT * FROM students WHERE class_id = ? ORDER BY name", (class_id,)).fetchall()
        return [Student(**row) for row in rows]

    def get_student(self, student_id: int) -> Student:
        cursor = self.conn.cursor()
        row = cursor.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
        return Student(**row)

    def add_assignment(self, class_id: int, title: str, context: str, answer_key: str) -> int:
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO assignments (class_id, title, context, answer_key, created_at) VALUES (?, ?, ?, ?, ?)",
            (class_id, title.strip(), context.strip(), answer_key.strip(), datetime.utcnow().isoformat()),
        )
        self.conn.commit()
        return cursor.lastrowid

    def list_assignments(self, class_id: int) -> List[Assignment]:
        cursor = self.conn.cursor()
        rows = cursor.execute("SELECT * FROM assignments WHERE class_id = ? ORDER BY created_at DESC", (class_id,)).fetchall()
        return [Assignment(**row) for row in rows]

    def get_assignment(self, assignment_id: int) -> Assignment:
        cursor = self.conn.cursor()
        row = cursor.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,)).fetchone()
        return Assignment(**row)

    def add_feedback(self, student_id: int, assignment_id: int, draft_number: int, feedback_tex: str, feedback_json: Any, feedback_pdf_path: str = None) -> int:
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO feedback (student_id, assignment_id, draft_number, feedback_tex, feedback_json, feedback_pdf_path, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (student_id, assignment_id, draft_number, feedback_tex, json.dumps(feedback_json), feedback_pdf_path, datetime.utcnow().isoformat()),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_feedback_history(self, student_id: int, assignment_id: int) -> List[Feedback]:
        cursor = self.conn.cursor()
        rows = cursor.execute(
            "SELECT * FROM feedback WHERE student_id = ? AND assignment_id = ? ORDER BY draft_number",
            (student_id, assignment_id),
        ).fetchall()
        feedback_history = []
        for row in rows:
            data = dict(row)
            data["feedback_json"] = json.loads(data["feedback_json"])
            feedback_history.append(Feedback(**data))
        return feedback_history

    def get_feedback_for_class_assignment(self, class_id: int, assignment_id: int) -> List[Feedback]:
        cursor = self.conn.cursor()
        rows = cursor.execute(
            "SELECT f.*, s.name AS student_name FROM feedback f JOIN students s ON s.id = f.student_id WHERE f.assignment_id = ? AND s.class_id = ? ORDER BY f.draft_number",
            (assignment_id, class_id),
        ).fetchall()
        feedback_list = []
        for row in rows:
            data = dict(row)
            data["feedback_json"] = json.loads(data["feedback_json"])
            feedback_list.append(Feedback(**data))
        return feedback_list
