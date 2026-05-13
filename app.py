import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image
from pypdf import PdfReader
from pytesseract import image_to_string

from database import Assignment, Database, Feedback, Student
from gemini_client import GeminiClient
from latex_utils import compile_latex, merge_pdfs, write_tex_file

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="AI Marking Assistant", layout="wide")


# ── Colour tokens ─────────────────────────────────────────────────────────────
_C = {
    "bg":       "#071020",   # deep dark blue page background
    "panel":    "#0d1e3a",   # card / panel background
    "border":   "#1e3a5f",   # subtle border
    "text":     "#e8edf5",   # primary text
    "muted":    "#4a7aaa",   # secondary / muted text
    "salmon":   "#fa7c6a",   # salmon accent
    "teal":     "#14b8a6",   # teal accent
    "amber":    "#f59e0b",   # amber accent
    "input_bg": "#060e1a",   # input field background
}

FONT_STACK = "'Century Gothic', CenturyGothic, AppleGothic, 'Trebuchet MS', sans-serif"


def inject_css() -> None:
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] {{
            font-family: 'Inter', sans-serif;
            background-color: {_C['bg']} !important;
            color: {_C['text']} !important;
        }}
        .stApp {{ background-color: {_C['bg']} !important; }}
        #MainMenu, footer, header {{ visibility: hidden; }}

        .main-title {{
            font-size: 2.5rem;
            font-weight: 800;
            color: {_C['text']};
            margin-bottom: 0.25rem;
        }}
        .subheader-text {{
            font-size: 1rem;
            color: {_C['muted']};
            margin-top: 0.2rem;
            margin-bottom: 1.2rem;
            max-width: 720px;
        }}

        .section-card, .small-card, .amber-card {{
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 22px;
            padding: 1.25rem 1.4rem;
            box-shadow: 0 24px 55px rgba(0, 0, 0, 0.14);
            margin-bottom: 1rem;
        }}

        .small-card {{
            padding: 1rem 1.2rem;
        }}

        .section-label {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.16em;
            text-transform: uppercase;
            color: {_C['muted']};
            margin-bottom: 0.75rem;
        }}
        .section-label.salmon {{ color: {_C['salmon']}; }}
        .section-label.teal   {{ color: {_C['teal']}; }}
        .section-label.amber  {{ color: {_C['amber']}; }}

        .stButton>button {{
            font-family: 'Inter', sans-serif;
            font-weight: 700;
            font-size: 0.85rem;
            line-height: 1.1;
            border-radius: 16px;
            color: #ffffff;
            background: linear-gradient(135deg, {_C['teal']}, {_C['salmon']});
            border: none;
            min-height: 48px;
            box-shadow: 0 18px 32px rgba(20,184,166,0.18);
            transition: transform 0.16s ease, opacity 0.16s ease;
        }}
        .stButton>button:hover {{ transform: translateY(-1px); opacity: 0.96; }}

        .stTextInput>div>div>input,
        .stTextArea>div>div>textarea,
        .stSelectbox>div>div>div {{
            background: rgba(255, 255, 255, 0.05) !important;
            color: {_C['text']} !important;
            border: 1px solid rgba(255,255,255,0.12) !important;
            border-radius: 16px !important;
            padding: 0.9rem !important;
        }}
        .stTextInput>div>div>input:focus,
        .stTextArea>div>div>textarea:focus {{
            border-color: {_C['teal']} !important;
            box-shadow: 0 0 0 2px rgba(20,184,166,0.16) !important;
        }}

        .stFileUploader>div>label {{
            border-radius: 18px;
            border: 1px dashed rgba(255,255,255,0.16);
            background: rgba(255,255,255,0.03);
        }}

        [data-testid="stSidebar"] {{
            background-color: rgba(255,255,255,0.04) !important;
            border-right: 1px solid rgba(255,255,255,0.08);
        }}
        [data-testid="stSidebar"] * {{ color: {_C['text']} !important; }}

        .streamlit-expanderHeader {{
            background: rgba(255,255,255,0.04) !important;
            border: 1px solid rgba(255,255,255,0.08) !important;
            border-radius: 16px !important;
        }}

        .auth-stripe {{
            height: 4px;
            background: linear-gradient(90deg, {_C['teal']} 0%, {_C['salmon']} 50%, {_C['amber']} 100%);
            border-radius: 99px;
            margin-bottom: 1.5rem;
        }}

        .login-wordmark {{
            font-size: 2rem;
            font-weight: 800;
            letter-spacing: 0.04em;
            color: {_C['text']};
            line-height: 1.05;
        }}
        .login-wordmark .s {{ color: {_C['salmon']}; }}
        .login-wordmark .t {{ color: {_C['teal']}; }}
        .login-sub {{
            font-size: 0.75rem;
            letter-spacing: 0.18em;
            text-transform: uppercase;
            color: {_C['muted']};
            margin-top: 0.75rem;
            margin-bottom: 1.5rem;
        }}

        .google-btn {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            width: 100%;
            padding: 12px 18px;
            background: #ffffff;
            border-radius: 16px;
            border: 1px solid rgba(0,0,0,0.08);
            color: #202124;
            font-weight: 700;
            text-decoration: none;
            transition: transform 0.16s ease, box-shadow 0.16s ease;
        }}
        .google-btn:hover {{ transform: translateY(-1px); box-shadow: 0 16px 32px rgba(0,0,0,0.08); }}

        .auth-divider {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin: 1rem 0;
            color: {_C['muted']};
            font-size: 0.8rem;
            text-transform: uppercase;
        }}
        .auth-divider::before, .auth-divider::after {{
            content: '';
            flex: 1;
            height: 1px;
            background: rgba(255,255,255,0.12);
        }}

        .status-ok {{ color: {_C['teal']}; font-size: 0.85rem; }}
        .status-err {{ color: {_C['salmon']}; font-size: 0.85rem; }}
        .avatar-row {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 1rem; }}
        .avatar-chip {{
            width: 44px; height: 44px;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 14px;
            display: flex; align-items: center; justify-content: center;
            font-size: 1.4rem;
            cursor: pointer;
            transition: transform 0.16s ease, border-color 0.16s ease;
        }}
        .avatar-chip.selected {{
            border-color: {_C['salmon']};
            transform: translateY(-1px);
            background: rgba(250,124,106,0.15);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    inject_pwa_meta()

@st.cache_resource
def get_database() -> Database:
    return Database(BASE_DIR / "marking_assistant.db")

@st.cache_resource
def get_gemini_client() -> GeminiClient:
    return GeminiClient(
        api_key=os.environ.get("GOOGLE_API_KEY") or st.secrets.get("google_api_key"),
    )


def inject_pwa_meta() -> None:
    components.html(
        """
        <script>
          const manifestLink = document.createElement('link');
          manifestLink.rel = 'manifest';
          manifestLink.href = '/static/manifest.json';
          document.head.appendChild(manifestLink);

          const themeMeta = document.createElement('meta');
          themeMeta.name = 'theme-color';
          themeMeta.content = '#0d1e3a';
          document.head.appendChild(themeMeta);

          if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/static/sw.js')
              .then(() => console.log('Service worker registered.'))
              .catch(err => console.warn('SW registration failed:', err));
          }
        </script>
        """,
        height=0,
        width=0,
        scrolling=False,
    )


# ── Login / Register page ─────────────────────────────────────────────────────
def render_login(db: Database) -> None:
    inject_css()

    # Centred narrow column
    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        # Colour stripe
        st.markdown("<div class='auth-stripe'></div>", unsafe_allow_html=True)

        # Wordmark
        st.markdown(
            "<div class='login-wordmark'>"
            "<span class='s'>AI</span> <span class='t'>Marking</span> Assistant"
            "</div>"
            "<div class='login-sub'>"
            "&#x1F4DA;&nbsp; Teacher Portal &nbsp;·&nbsp; Your Data, Any Device"
            "</div>",
            unsafe_allow_html=True,
        )

        # ── Teacher Code login (simplest, works across devices) ──
        st.markdown("<div class='section-label teal'>Quick Access</div>", unsafe_allow_html=True)
        teacher_code = st.text_input(
            "Teacher Code",
            key="teacher_code",
            placeholder="e.g. A1B2C3 — use this on any device",
            max_chars=6,
        ).strip().upper()

        if st.button("Enter with Code →", key="code_submit", use_container_width=True):
            if not teacher_code:
                st.markdown("<p class='status-err'>Please enter your teacher code.</p>", unsafe_allow_html=True)
            else:
                teacher = db.get_teacher_by_code(teacher_code)
                if teacher:
                    st.session_state.authenticated = True
                    st.session_state.teacher = teacher
                    st.session_state.needs_setup = not bool(teacher.get("setup_complete"))
                    st.rerun()
                else:
                    st.markdown("<p class='status-err'>Invalid teacher code.</p>", unsafe_allow_html=True)

        # Divider
        st.markdown("<div class='auth-divider'>or sign in with email</div>", unsafe_allow_html=True)

        # Tab state
        if "auth_tab" not in st.session_state:
            st.session_state.auth_tab = "login"

        tab_login, tab_reg = st.tabs(["Sign In", "Register"])

        # ── Sign In tab ──
        with tab_login:
            email_in = st.text_input("Email", key="li_email", placeholder="teacher@school.edu")
            password_in = st.text_input("Password", key="li_pw", placeholder="••••••••", type="password")

            if st.button("Enter Dashboard →", key="li_submit", use_container_width=True):
                if not email_in or not password_in:
                    st.markdown("<p class='status-err'>Please fill in all fields.</p>", unsafe_allow_html=True)
                else:
                    teacher = db.verify_teacher_password(email_in, password_in)
                    if teacher:
                        st.session_state.authenticated = True
                        st.session_state.teacher = teacher
                        st.session_state.needs_setup = not bool(teacher.get("setup_complete"))
                        st.rerun()
                    else:
                        st.markdown("<p class='status-err'>Invalid email or password.</p>", unsafe_allow_html=True)

            # Show teacher code for logged-in users
            teacher = db.get_teacher_by_email(email_in) if email_in else None
            if teacher and teacher.get("teacher_code"):
                st.info(f"Your teacher code: **{teacher['teacher_code']}** — use this on any device.")

        # ── Register tab ──
        with tab_reg:
            reg_name = st.text_input("Your Name", key="reg_name", placeholder="Ms. Chen")
            reg_email = st.text_input("Email", key="reg_email", placeholder="teacher@school.edu")
            reg_pw = st.text_input("Password", key="reg_pw", placeholder="Min. 6 characters", type="password")
            reg_pw2 = st.text_input("Confirm Password", key="reg_pw2", placeholder="Repeat password", type="password")

            if st.button("Create Account →", key="reg_submit", use_container_width=True):
                err = None
                if not all([reg_name, reg_email, reg_pw, reg_pw2]):
                    err = "Please fill in all fields."
                elif len(reg_pw) < 6:
                    err = "Password must be at least 6 characters."
                elif reg_pw != reg_pw2:
                    err = "Passwords do not match."
                elif db.get_teacher_by_email(reg_email):
                    err = "An account with that email already exists."

                if err:
                    st.markdown(f"<p class='status-err'>{err}</p>", unsafe_allow_html=True)
                else:
                    teacher_id = db.create_teacher(email=reg_email, display_name=reg_name, password=reg_pw)
                    teacher = db.get_teacher_by_email(reg_email)
                    st.session_state.authenticated = True
                    st.session_state.teacher = teacher
                    st.session_state.needs_setup = True
                    st.markdown(
                        f"<p class='status-ok'>✓ Account created! "
                        f"Your teacher code is: <strong>{teacher['teacher_code']}</strong> "
                        f"— save this to log in from any device.</p>",
                        unsafe_allow_html=True,
                    )
                    st.rerun()


# ── Account Setup page ────────────────────────────────────────────────────────
def render_account_setup(db: Database) -> None:
    inject_css()
    teacher = st.session_state.get("teacher", {})

    _, col, _ = st.columns([1, 1.6, 1])
    with col:
        st.markdown("<div class='auth-stripe'></div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='login-wordmark'>"
            "🧑‍🏫 &nbsp;<span class='t'>Trainer</span> Setup"
            "</div>"
            "<div class='login-sub'>Customise your teacher profile before you begin</div>",
            unsafe_allow_html=True,
        )

        # ── Display name ──
        st.markdown("<div class='section-label salmon'>Display Name</div>", unsafe_allow_html=True)
        display_name = st.text_input(
            "Display Name",
            value=teacher.get("display_name", ""),
            key="setup_name",
            label_visibility="collapsed",
            placeholder="How should students see you?",
        )

        # ── School ──
        st.markdown("<div class='section-label teal'>School</div>", unsafe_allow_html=True)
        school = st.text_input(
            "School",
            key="setup_school",
            label_visibility="collapsed",
            placeholder="e.g. Greenfield Primary School",
        )

        # ── Subject ──
        st.markdown("<div class='section-label teal'>Subject / Year Level</div>", unsafe_allow_html=True)
        subject = st.text_input(
            "Subject",
            key="setup_subject",
            label_visibility="collapsed",
            placeholder="e.g. English · Year 5",
        )

        # ── Avatar ──
        st.markdown("<div class='section-label amber'>Choose Avatar</div>", unsafe_allow_html=True)
        avatars = ["🧑‍🏫", "👩‍🏫", "👨‍🏫", "🦉", "📚", "✏️", "🎓", "⭐"]
        selected_avatar = st.session_state.get("setup_avatar", avatars[0])

        # Render avatar chips as radio via columns
        avatar_cols = st.columns(len(avatars))
        for i, (av, acol) in enumerate(zip(avatars, avatar_cols)):
            with acol:
                label = f"{'✓ ' if av == selected_avatar else ''}{av}"
                if st.button(label, key=f"av_{i}"):
                    st.session_state.setup_avatar = av
                    st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        col_save, col_skip = st.columns([2, 1])
        with col_save:
            if st.button("Begin Marking →", key="setup_save", use_container_width=True):
                if not display_name.strip():
                    st.markdown("<p class='status-err'>Please enter a display name.</p>", unsafe_allow_html=True)
                else:
                    db.update_teacher_profile(
                        teacher_id=teacher["id"],
                        display_name=display_name,
                        school=school or "",
                        subject=subject or "",
                        avatar=st.session_state.get("setup_avatar", avatars[0]),
                    )
                    st.session_state.needs_setup = False
                    st.session_state.teacher = db.get_teacher_by_email(teacher["email"])
                    st.rerun()
        with col_skip:
            if st.button("Skip", key="setup_skip", use_container_width=True):
                st.session_state.needs_setup = False
                st.rerun()


def extract_submission_text(uploaded_file) -> str:
    if uploaded_file.type.startswith("image/"):
        image = Image.open(uploaded_file)
        return image_to_string(image, lang="eng")

    if uploaded_file.type == "text/plain":
        return uploaded_file.read().decode("utf-8")

    if uploaded_file.type == "application/pdf":
        reader = PdfReader(uploaded_file)
        text = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            text.append(page_text)
        return "\n".join(text).strip()

    return ""


def student_upload_area(db: Database, class_id: int, assignment_id: int, student_id: int):
    st.header("Upload Student Work")

    with st.form(key="student_submission_form"):
        uploaded_file = st.file_uploader("Upload handwritten image or text file", type=["png", "jpg", "jpeg", "pdf", "txt"])
        raw_text = st.text_area("OR paste student text here", height=220)
        submit = st.form_submit_button("Grade Submission")

    if not submit:
        return

    submission_text = raw_text.strip()
    if uploaded_file and not submission_text:
        with st.spinner("Extracting text from the uploaded file..."):
            submission_text = extract_submission_text(uploaded_file)

    if not submission_text:
        st.error("No extractable submission text found. Please paste the text directly or upload a clearer image/pdf.")
        return

    assignment = db.get_assignment(assignment_id)
    student = db.get_student(student_id)
    history = db.get_feedback_history(student_id, assignment_id)
    previous_feedback = "\n\n".join([f"Draft {item.draft_number}: {item.feedback_json}" for item in history]) or "None"

    gemini = get_gemini_client()
    with st.spinner("Sending to Gemini and generating feedback..."):
        try:
            latex_result = gemini.generate_student_feedback(
                student_name=student.name,
                class_name=db.get_class(class_id).name,
                assignment=assignment,
                submission_text=submission_text,
                history=previous_feedback,
            )
        except Exception as exc:
            st.error(f"Grading failed: {exc}")
            return

    st.subheader("Generated LaTeX")
    st.code(latex_result, language="latex")

    tex_file = OUTPUT_DIR / f"feedback_{student_id}_{assignment_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.tex"
    write_tex_file(tex_file, latex_result)

    try:
        pdf_file = compile_latex(tex_file, OUTPUT_DIR)
    except Exception as exc:
        st.error(f"LaTeX compilation failed: {exc}")
        return

    st.success("PDF generated successfully.")
    with open(pdf_file, "rb") as f:
        st.download_button("Download feedback PDF", f, file_name=pdf_file.name, mime="application/pdf")

    db.add_feedback(
        student_id=student_id,
        assignment_id=assignment_id,
        draft_number=len(history) + 1,
        feedback_tex=latex_result,
        feedback_json={
            "generated_at": datetime.utcnow().isoformat(),
            "student_text": submission_text[:1000],
            "history": previous_feedback,
        },
        feedback_pdf_path=str(pdf_file),
    )


def render_feedback_history(db: Database, student_id: int, assignment_id: int):
    history = db.get_feedback_history(student_id, assignment_id)
    if not history:
        st.info("No previous feedback found for this student and assignment.")
        return

    st.subheader("Feedback History")
    for item in history:
        with st.expander(f"Draft {item.draft_number} — {item.created_at}"):
            st.write(item.feedback_json)
            st.code(item.feedback_tex, language="latex")


def render_class_report(db: Database, class_id: int, assignment_id: int):
    st.header("Class Competency Report")
    if st.button("Generate Class Report"):
        assignment = db.get_assignment(assignment_id)
        feedback_rows = db.get_feedback_for_class_assignment(class_id, assignment_id)
        if not feedback_rows:
            st.warning("No graded submissions found for this assignment.")
            return

        gemini = get_gemini_client()
        with st.spinner("Generating the class report from Gemini..."):
            try:
                report_tex = gemini.generate_class_report(
                    class_name=db.get_class(class_id).name,
                    assignment=assignment,
                    feedback_rows=feedback_rows,
                )
            except Exception as exc:
                st.error(f"Class report generation failed: {exc}")
                return

        st.subheader("Class Report LaTeX")
        st.code(report_tex, language="latex")

        report_file = OUTPUT_DIR / f"class_report_{class_id}_{assignment_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.tex"
        write_tex_file(report_file, report_tex)
        try:
            pdf_file = compile_latex(report_file, OUTPUT_DIR)
        except Exception as exc:
            st.error(f"LaTeX compilation failed: {exc}")
            return

        st.success("Class report PDF generated successfully.")
        with open(pdf_file, "rb") as f:
            st.download_button("Download class report PDF", f, file_name=pdf_file.name, mime="application/pdf")

        student_pdf_paths = [row.feedback_pdf_path for row in feedback_rows if row.feedback_pdf_path and Path(row.feedback_pdf_path).exists()]
        if student_pdf_paths:
            merged_path = OUTPUT_DIR / f"merged_{class_id}_{assignment_id}.pdf"
            merge_pdfs(student_pdf_paths, merged_path)
            with open(merged_path, "rb") as f:
                st.download_button("Download merged class PDFs", f, file_name=merged_path.name, mime="application/pdf")
        else:
            st.info("No existing student PDF files were found to merge.")


def main():
    db = get_database()

    # ── Auth gate ──
    if not st.session_state.get("authenticated"):
        render_login(db)
        return

    # ── Account setup gate (new accounts) ──
    if st.session_state.get("needs_setup"):
        render_account_setup(db)
        return

    inject_css()

    # ── Teacher greeting in sidebar ──
    teacher = st.session_state.get("teacher", {})
    avatar  = teacher.get("avatar", "🧑‍🏫") if isinstance(teacher, dict) else "🧑‍🏫"
    name    = teacher.get("display_name", "Teacher") if isinstance(teacher, dict) else "Teacher"
    teacher_id = teacher.get("id") if isinstance(teacher, dict) else None

    st.sidebar.markdown(
        f"<div style='padding:0.6rem 0; border-bottom:1px solid #1e3a5f; margin-bottom:0.8rem;'>"
        f"<span style='font-size:1.4rem;'>{avatar}</span>&nbsp;"
        f"<span style='font-weight:900; font-size:0.8rem; color:#e8edf5;'>{name}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )
    if st.sidebar.button("Sign Out", key="signout"):
        for k in ["authenticated", "teacher", "needs_setup"]:
            st.session_state.pop(k, None)
        st.rerun()

    # Show teacher code for cross-device access
    teacher_code = teacher.get("teacher_code", "")
    if teacher_code:
        st.sidebar.caption(f"Your code: **{teacher_code}**")

    # Show active Gemini model
    gemini = get_gemini_client()
    if gemini.last_model_used:
        st.sidebar.caption(f"🧠 Model: `{gemini.last_model_used}`")

    st.sidebar.title("Navigation")
    st.sidebar.markdown("## Classes & Assignments")

    with st.sidebar.expander("Create New Class", expanded=True):
        new_class_name = st.text_input("Class Name", key="new_class_name")
        if st.button("Add Class", key="add_class") and new_class_name:
            db.add_class(new_class_name, teacher_id=teacher_id)
            st.rerun()

    classes = db.list_classes(teacher_id=teacher_id)
    class_options = {c.name: c.id for c in classes}
    selected_class_name = st.sidebar.selectbox("Select Class", ["Choose a class"] + list(class_options.keys()), key="selected_class")
    class_id = class_options.get(selected_class_name)

    if not class_id:
        st.markdown("<div class='main-title'>Welcome to the AI Marking Assistant</div>", unsafe_allow_html=True)
        st.markdown("<p class='subheader-text'>Start by creating or selecting a class from the sidebar.</p>", unsafe_allow_html=True)
        return

    selected_class = db.get_class(class_id)

    with st.sidebar.expander("Manage Students", expanded=True):
        new_student_name = st.text_input("Student Name", key="new_student_name")
        if st.button("Add Student", key="add_student") and new_student_name:
            db.add_student(class_id, new_student_name)
            st.rerun()

        students = db.list_students(class_id)
        st.write(pd.DataFrame([{"ID": s.id, "Name": s.name} for s in students]))

    with st.sidebar.expander("Manage Assignments", expanded=True):
        new_assignment_title = st.text_input("Assignment Title", key="new_assignment_title")
        new_context = st.text_area("Assignment Prompt / Context", key="new_assignment_context")
        new_answer_key = st.text_area("Answer Key / Rubric / Model Answers", key="new_assignment_answer_key")
        if st.button("Add Assignment", key="add_assignment") and new_assignment_title and new_context:
            db.add_assignment(class_id, new_assignment_title, new_context, new_answer_key)
            st.rerun()

        assignments = db.list_assignments(class_id)
        st.write(pd.DataFrame([{"ID": a.id, "Title": a.title} for a in assignments]))

    assignment_options = {a.title: a.id for a in assignments}
    selected_assignment_title = st.sidebar.selectbox("Select Assignment", ["Choose an assignment"] + list(assignment_options.keys()), key="selected_assignment")
    assignment_id = assignment_options.get(selected_assignment_title)

    student_options = {s.name: s.id for s in students}
    selected_student_name = st.sidebar.selectbox("Select Student", ["Choose a student"] + list(student_options.keys()), key="selected_student")
    student_id = student_options.get(selected_student_name)

    st.markdown("<div class='main-title'>Teacher Dashboard</div>", unsafe_allow_html=True)
    st.markdown("<p class='subheader-text'>Select an assignment and student to grade work, review past feedback, and produce PDF reports.</p>", unsafe_allow_html=True)

    left, right = st.columns([2, 1])
    with left:
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.subheader("Selected Class & Assignment")
        st.markdown(f"**Class:** {selected_class.name}")
        if assignment_id:
            selected_assignment = db.get_assignment(assignment_id)
            st.markdown(f"**Assignment:** {selected_assignment.title}")
            st.markdown(f"**Prompt:** {selected_assignment.context[:180]}...")
        else:
            st.info("Please select an assignment from the sidebar.")
        st.markdown("</div>", unsafe_allow_html=True)

        if assignment_id and not student_id:
            st.warning("Select a student from the sidebar to proceed.")

        if assignment_id and student_id:
            selected_student = db.get_student(student_id)
            st.markdown("<div class='section-card'>", unsafe_allow_html=True)
            st.subheader("Selected Student")
            st.markdown(f"**Name:** {selected_student.name}")
            st.markdown(f"**Class:** {selected_class.name}")
            st.markdown(f"**Assignment:** {selected_assignment_title}")
            st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown("<div class='small-card'>", unsafe_allow_html=True)
        st.subheader("Quick Actions")
        st.markdown("- Upload student work\n- Generate feedback PDF\n- Create class competency report")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='small-card'>", unsafe_allow_html=True)
        st.subheader("Status")
        st.markdown(f"**Students:** {len(students)}")
        st.markdown(f"**Assignments:** {len(assignments)}")
        if student_id and assignment_id:
            history = db.get_feedback_history(student_id, assignment_id)
            st.markdown(f"**Drafts saved:** {len(history)}")
        st.markdown("</div>", unsafe_allow_html=True)

    if not assignment_id:
        st.warning("Select an assignment before grading.")
        return

    if not student_id:
        st.warning("Select a student before uploading work.")
        return

    render_feedback_history(db, student_id, assignment_id)
    student_upload_area(db, class_id, assignment_id, student_id)
    render_class_report(db, class_id, assignment_id)


if __name__ == "__main__":
    main()
