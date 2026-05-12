import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
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
        @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;700;900&display=swap');

        /* ── Global reset ── */
        html, body, [class*="css"] {{
            font-family: {FONT_STACK};
            background-color: {_C['bg']} !important;
            color: {_C['text']} !important;
        }}
        .stApp {{ background-color: {_C['bg']} !important; }}

        /* ── Hide Streamlit chrome ── */
        #MainMenu, footer, header {{ visibility: hidden; }}

        /* ── Main title ── */
        .main-title {{
            font-size: 2.4rem;
            font-weight: 900;
            letter-spacing: 0.04em;
            color: {_C['text']};
            margin-bottom: 0.1rem;
            line-height: 1.1;
        }}
        .main-title .accent-salmon {{ color: {_C['salmon']}; }}
        .main-title .accent-teal   {{ color: {_C['teal']}; }}

        .subheader-text {{
            font-size: 0.9rem;
            color: {_C['muted']};
            margin-top: 0;
            letter-spacing: 0.02em;
        }}

        /* ── Cards ── */
        .section-card {{
            padding: 1.4rem 1.6rem;
            background: {_C['panel']};
            border: 2px solid {_C['border']};
            box-shadow: 5px 5px 0px 0px {_C['salmon']};
            margin-bottom: 1rem;
        }}
        .small-card {{
            padding: 1rem 1.2rem;
            background: {_C['panel']};
            border: 2px solid {_C['border']};
            box-shadow: 3px 3px 0px 0px {_C['teal']};
            margin-bottom: 0.75rem;
        }}
        .amber-card {{
            padding: 1rem 1.2rem;
            background: {_C['panel']};
            border: 2px solid {_C['border']};
            box-shadow: 3px 3px 0px 0px {_C['amber']};
            margin-bottom: 0.75rem;
        }}

        /* ── Section labels ── */
        .section-label {{
            font-size: 0.65rem;
            font-weight: 900;
            letter-spacing: 0.25em;
            text-transform: uppercase;
            color: {_C['muted']};
            margin-bottom: 0.5rem;
        }}
        .section-label.salmon {{ color: {_C['salmon']}; border-bottom: 2px solid {_C['salmon']}; padding-bottom: 4px; }}
        .section-label.teal   {{ color: {_C['teal']};   border-bottom: 2px solid {_C['teal']};   padding-bottom: 4px; }}
        .section-label.amber  {{ color: {_C['amber']};  border-bottom: 2px solid {_C['amber']};  padding-bottom: 4px; }}

        /* ── Buttons ── */
        .stButton>button {{
            font-family: {FONT_STACK};
            font-weight: 900;
            font-size: 0.75rem;
            letter-spacing: 0.15em;
            text-transform: uppercase;
            background: {_C['panel']};
            color: {_C['text']};
            border: 2px solid {_C['text']};
            box-shadow: 4px 4px 0px 0px {_C['salmon']};
            border-radius: 0;
            height: 46px;
            transition: all 0.1s ease;
        }}
        .stButton>button:hover {{
            background: rgba(250,124,106,0.08);
            border-color: {_C['salmon']};
            color: {_C['salmon']};
        }}
        .stButton>button:active {{
            transform: translate(4px, 4px);
            box-shadow: none !important;
        }}

        /* ── Inputs ── */
        .stTextInput>div>div>input,
        .stTextArea>div>div>textarea,
        .stSelectbox>div>div>div {{
            font-family: {FONT_STACK};
            background: {_C['input_bg']} !important;
            color: {_C['text']} !important;
            border: 2px solid {_C['border']} !important;
            border-radius: 0 !important;
        }}
        .stTextInput>div>div>input:focus,
        .stTextArea>div>div>textarea:focus {{
            border-color: {_C['teal']} !important;
            box-shadow: 0 0 0 2px rgba(20,184,166,0.15) !important;
        }}
        label, .stTextInput label, .stTextArea label, .stSelectbox label {{
            font-family: {FONT_STACK} !important;
            font-size: 0.65rem !important;
            font-weight: 900 !important;
            letter-spacing: 0.2em !important;
            text-transform: uppercase !important;
            color: {_C['muted']} !important;
        }}

        /* ── File uploader ── */
        .stFileUploader>div>label {{
            background: {_C['input_bg']};
            border: 2px dashed {_C['border']};
            border-radius: 0;
            color: {_C['muted']};
        }}

        /* ── Sidebar ── */
        [data-testid="stSidebar"] {{
            background-color: {_C['panel']} !important;
            border-right: 2px solid {_C['border']};
        }}
        [data-testid="stSidebar"] * {{
            color: {_C['text']} !important;
        }}

        /* ── Expander ── */
        .streamlit-expanderHeader {{
            font-family: {FONT_STACK} !important;
            font-weight: 900 !important;
            font-size: 0.75rem !important;
            letter-spacing: 0.1em !important;
            text-transform: uppercase !important;
            color: {_C['teal']} !important;
            background: {_C['panel']} !important;
            border: 1px solid {_C['border']} !important;
        }}

        /* ── Divider stripe ── */
        .auth-stripe {{
            height: 3px;
            background: linear-gradient(90deg, {_C['salmon']} 0%, {_C['teal']} 50%, {_C['amber']} 100%);
            margin-bottom: 1.5rem;
        }}

        /* ── Login page specific ── */
        .login-wordmark {{
            font-size: 1.6rem;
            font-weight: 900;
            letter-spacing: 0.2em;
            text-transform: uppercase;
            color: {_C['text']};
            line-height: 1;
        }}
        .login-wordmark .s {{ color: {_C['salmon']}; }}
        .login-wordmark .t {{ color: {_C['teal']}; }}
        .login-sub {{
            font-size: 0.65rem;
            font-weight: 700;
            letter-spacing: 0.3em;
            text-transform: uppercase;
            color: {_C['muted']};
            margin-top: 4px;
            margin-bottom: 1.5rem;
        }}
        .google-btn {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            width: 100%;
            padding: 11px 16px;
            background: #ffffff;
            border: 2px solid #dadce0;
            color: #3c4043;
            font-family: {FONT_STACK};
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.05em;
            cursor: pointer;
            box-shadow: 3px 3px 0px 0px rgba(66,133,244,0.4);
            text-decoration: none;
            margin-bottom: 0.5rem;
        }}
        .google-btn:hover {{ background: #f8f9fa; }}
        .auth-divider {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin: 1rem 0;
            color: #1e3a5f;
            font-size: 0.65rem;
            font-weight: 700;
            letter-spacing: 0.15em;
            text-transform: uppercase;
        }}
        .auth-divider::before, .auth-divider::after {{
            content: '';
            flex: 1;
            height: 1px;
            background: {_C['border']};
        }}
        .status-ok  {{ color: {_C['teal']};   font-size: 0.75rem; font-weight: 700; }}
        .status-err {{ color: {_C['salmon']}; font-size: 0.75rem; font-weight: 700; }}

        /* ── Avatar chips ── */
        .avatar-row {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin-bottom: 1rem;
        }}
        .avatar-chip {{
            width: 44px; height: 44px;
            background: {_C['input_bg']};
            border: 2px solid {_C['border']};
            display: flex; align-items: center; justify-content: center;
            font-size: 1.4rem;
            cursor: pointer;
            transition: all 0.15s;
        }}
        .avatar-chip.selected {{
            border-color: {_C['salmon']};
            box-shadow: 3px 3px 0px 0px {_C['salmon']};
            background: rgba(250,124,106,0.08);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

@st.cache_resource
def get_database() -> Database:
    return Database(BASE_DIR / "marking_assistant.db")

@st.cache_resource
def get_gemini_client() -> GeminiClient:
    return GeminiClient(
        api_key=os.environ.get("GOOGLE_API_KEY") or st.secrets.get("google_api_key"),
        model=os.environ.get("GEMINI_MODEL") or st.secrets.get("gemini_model", "text-bison-1"),
    )


# ── Google OAuth helper (prototype — swap for real OAuth in production) ────────
def _mock_google_login(db: Database) -> None:
    """Simulate Google OAuth. In production replace with google-auth-oauthlib flow."""
    import random, string
    fake_sub   = "google_" + "".join(random.choices(string.digits, k=10))
    fake_email = f"teacher{random.randint(100,999)}@gmail.com"
    fake_name  = "Google Teacher"

    teacher = db.get_teacher_by_email(fake_email)
    if not teacher:
        db.create_teacher(email=fake_email, display_name=fake_name, google_sub=fake_sub)
        teacher = db.get_teacher_by_email(fake_email)

    st.session_state.authenticated = True
    st.session_state.teacher        = teacher
    st.session_state.needs_setup    = not bool(teacher.get("setup_complete"))
    st.rerun()


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
            "&#x1F4DA;&nbsp; Teacher Portal &nbsp;·&nbsp; Secure Access"
            "</div>",
            unsafe_allow_html=True,
        )

        # ── Google Sign-In ──
        st.markdown(
            """
            <div class='google-btn' onclick='void(0)'>
                <svg width="18" height="18" viewBox="0 0 24 24">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
                Continue with Google
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("▶  Sign in with Google", key="google_btn", use_container_width=True):
            _mock_google_login(db)

        # Divider
        st.markdown("<div class='auth-divider'>or use email &amp; password</div>", unsafe_allow_html=True)

        # Tab state
        if "auth_tab" not in st.session_state:
            st.session_state.auth_tab = "login"

        tab_login, tab_reg = st.tabs(["Sign In", "Register"])

        # ── Sign In tab ──
        with tab_login:
            email_in    = st.text_input("Email", key="li_email",    placeholder="teacher@school.edu")
            password_in = st.text_input("Password", key="li_pw",    placeholder="••••••••", type="password")

            if st.button("Enter Dashboard →", key="li_submit", use_container_width=True):
                if not email_in or not password_in:
                    st.markdown("<p class='status-err'>Please fill in all fields.</p>", unsafe_allow_html=True)
                else:
                    teacher = db.verify_teacher_password(email_in, password_in)
                    if teacher:
                        st.session_state.authenticated = True
                        st.session_state.teacher        = teacher
                        st.session_state.needs_setup    = not bool(teacher.get("setup_complete"))
                        st.rerun()
                    else:
                        st.markdown("<p class='status-err'>Invalid email or password.</p>", unsafe_allow_html=True)

            # Legacy PIN fallback
            with st.expander("Use PIN instead"):
                pin = st.text_input("6-digit teacher PIN", type="password", key="pin_input")
                if st.button("Login with PIN", key="pin_submit"):
                    secret_pin = os.environ.get("STREAMLIT_PIN") or st.secrets.get("pin_code", "")
                    if secret_pin and pin == str(secret_pin):
                        st.session_state.authenticated = True
                        st.session_state.teacher        = {"display_name": "Teacher", "avatar": "🧑‍🏫", "setup_complete": 1}
                        st.session_state.needs_setup    = False
                        st.rerun()
                    else:
                        st.markdown("<p class='status-err'>Invalid PIN.</p>", unsafe_allow_html=True)

        # ── Register tab ──
        with tab_reg:
            reg_name  = st.text_input("Your Name",        key="reg_name",  placeholder="Ms. Chen")
            reg_email = st.text_input("Email",             key="reg_email", placeholder="teacher@school.edu")
            reg_pw    = st.text_input("Password",          key="reg_pw",    placeholder="Min. 6 characters", type="password")
            reg_pw2   = st.text_input("Confirm Password",  key="reg_pw2",   placeholder="Repeat password",   type="password")

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
                    db.create_teacher(email=reg_email, display_name=reg_name, password=reg_pw)
                    teacher = db.get_teacher_by_email(reg_email)
                    st.session_state.authenticated = True
                    st.session_state.teacher        = teacher
                    st.session_state.needs_setup    = True   # new account → go to setup
                    st.markdown("<p class='status-ok'>✓ Account created! Setting up your profile…</p>", unsafe_allow_html=True)
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

    st.sidebar.title("Navigation")
    st.sidebar.markdown("## Classes & Assignments")

    with st.sidebar.expander("Create New Class", expanded=True):
        new_class_name = st.text_input("Class Name", key="new_class_name")
        if st.button("Add Class", key="add_class") and new_class_name:
            db.add_class(new_class_name)
            st.experimental_rerun()

    classes = db.list_classes()
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
            st.experimental_rerun()

        students = db.list_students(class_id)
        st.write(pd.DataFrame([{"ID": s.id, "Name": s.name} for s in students]))

    with st.sidebar.expander("Manage Assignments", expanded=True):
        new_assignment_title = st.text_input("Assignment Title", key="new_assignment_title")
        new_context = st.text_area("Assignment Prompt / Context", key="new_assignment_context")
        new_answer_key = st.text_area("Answer Key / Rubric / Model Answers", key="new_assignment_answer_key")
        if st.button("Add Assignment", key="add_assignment") and new_assignment_title and new_context:
            db.add_assignment(class_id, new_assignment_title, new_context, new_answer_key)
            st.experimental_rerun()

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
