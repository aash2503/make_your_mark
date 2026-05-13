-- ── AI Marking Assistant — Supabase Schema ────────────────────────────────
-- Run this once in the Supabase SQL Editor (https://app.supabase.com)
-- before starting the app.

-- Teachers
CREATE TABLE IF NOT EXISTS teachers (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    password_hash TEXT,
    teacher_code TEXT UNIQUE,
    school TEXT,
    subject TEXT,
    avatar TEXT DEFAULT '🧑‍🏫',
    setup_complete BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Classes (scoped to teacher)
CREATE TABLE IF NOT EXISTS classes (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL,
    teacher_id BIGINT REFERENCES teachers(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(name, teacher_id)
);

-- Students
CREATE TABLE IF NOT EXISTS students (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    class_id BIGINT NOT NULL REFERENCES classes(id),
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Assignments
CREATE TABLE IF NOT EXISTS assignments (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    class_id BIGINT NOT NULL REFERENCES classes(id),
    title TEXT NOT NULL,
    context TEXT NOT NULL,
    answer_key TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Feedback
CREATE TABLE IF NOT EXISTS feedback (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_id BIGINT NOT NULL REFERENCES students(id),
    assignment_id BIGINT NOT NULL REFERENCES assignments(id),
    draft_number INTEGER NOT NULL,
    feedback_tex TEXT NOT NULL,
    feedback_json TEXT NOT NULL,
    feedback_pdf_path TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Enable real-time (optional — for live updates between devices)
ALTER PUBLICATION supabase_realtime ADD TABLE classes;
ALTER PUBLICATION supabase_realtime ADD TABLE students;
ALTER PUBLICATION supabase_realtime ADD TABLE feedback;
