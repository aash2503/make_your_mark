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
from latex_utils import compile_latex, compile_latex_online, merge_pdfs, write_tex_file

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="MY-Mark", layout="wide")


# ── Colour tokens ─────────────────────────────────────────────────────────────
_C = {
    "bg":       "#0a1128",   # deep navy background
    "panel":    "#111d3b",   # lighter navy for cards/panels
    "border":   "#f8fafc",   # off-white — main border colour
    "text":     "#f8fafc",   # off-white — primary text
    "muted":    "#94a3b8",   # slate-400 — secondary text
    "salmon":   "#ff7f50",   # coral/salmon accent
    "teal":     "#14b8a6",   # teal accent
    "amber":    "#f59e0b",   # amber — primary highlight
    "gold":     "#fbbf24",   # lighter gold
    "success":  "#10b981",   # emerald — success indicators
    "input_bg": "#0d1635",   # input field background
}

def inject_css() -> None:
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap');

        html, body, [class*="css"] {{
            font-family: 'Century Gothic', CenturyGothic, AppleGothic, sans-serif !important;
            background-color: {_C['bg']} !important;
            color: {_C['text']} !important;
        }}
        .stApp {{ 
            background-color: {_C['bg']} !important;
            background-image: radial-gradient(ellipse at 50% 0%, rgba(245,158,11,0.04) 0%, transparent 60%);
        }}
        #MainMenu, footer, header {{ visibility: hidden; }}

        /* Input fields use monospace */
        .stTextInput input, .stTextArea textarea, .stSelectbox [role="listbox"] {{
            font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace !important;
        }}

        .main-title {{
            font-size: 2.5rem;
            font-weight: 900;
            color: {_C['text']};
            margin-bottom: 0.25rem;
            letter-spacing: -0.02em;
        }}
        .subheader-text {{
            font-size: 1rem;
            color: {_C['muted']};
            margin-top: 0.2rem;
            margin-bottom: 1.2rem;
            max-width: 720px;
        }}

        /* ── Cards with glassmorphism ── */
        .section-card, .small-card, .amber-card {{
            background: rgba(17, 29, 59, 0.85);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 2px solid {_C['amber']};
            border-radius: 22px;
            padding: 1.25rem 1.4rem;
            box-shadow: 0 8px 0 rgba(245,158,11,0.15), 0 24px 55px rgba(0, 0, 0, 0.25);
            margin-bottom: 1rem;
        }}

        .small-card {{
            padding: 1rem 1.2rem;
            border-width: 1.5px;
            box-shadow: 0 4px 0 rgba(245,158,11,0.1), 0 16px 36px rgba(0, 0, 0, 0.18);
        }}

        .section-label {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.75rem;
            font-weight: 900;
            letter-spacing: 0.18em;
            text-transform: uppercase;
            color: {_C['muted']};
            margin-bottom: 0.75rem;
        }}
        .section-label.salmon {{ color: {_C['salmon']}; }}
        .section-label.teal   {{ color: {_C['teal']}; }}
        .section-label.amber  {{ color: {_C['amber']}; }}

        /* ── Neo-brutalist buttons ── */
        .stButton>button {{
            font-family: 'Century Gothic', CenturyGothic, AppleGothic, sans-serif !important;
            font-weight: 700 !important;
            letter-spacing: 0.04em !important;
            text-transform: uppercase;
            font-size: 0.85rem;
            line-height: 1.1;
            border-radius: 14px;
            color: #ffffff;
            background: {_C['amber']};
            border: 2px solid {_C['amber']} !important;
            min-height: 48px;
            box-shadow: none;
            transition: opacity 0.12s ease;
        }}
        .stButton>button:hover {{ opacity: 0.88; }}
        .stButton>button:active {{ opacity: 0.75; }}

        /* ── Inputs ── */
        .stTextInput>div>div>input,
        .stTextArea>div>div>textarea {{
            background: {_C['input_bg']} !important;
            color: {_C['text']} !important;
            border: 2px solid {_C['border']} !important;
            border-radius: 14px !important;
            padding: 0.9rem !important;
            font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace !important;
        }}
        .stTextInput>div>div>input:focus,
        .stTextArea>div>div>textarea:focus {{
            border-color: {_C['amber']} !important;
            box-shadow: 0 0 0 3px rgba(245,158,11,0.25), 0 4px 0 rgba(245,158,11,0.15) !important;
        }}

        /* Selectbox — lighter touch, no padding that breaks text */
        [data-baseweb="select"] {{
            background: {_C['input_bg']} !important;
            color: {_C['text']} !important;
            border: 2px solid {_C['border']} !important;
            border-radius: 14px !important;
            font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace !important;
        }}

        .stFileUploader>div>label {{
            border-radius: 18px;
            border: 2px dashed {_C['amber']};
            background: rgba(245,158,11,0.05);
        }}

        /* ── Sidebar — glassmorphism ── */
        [data-testid="stSidebar"] {{
            background: rgba(10, 17, 40, 0.95) !important;
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border-right: 2px solid {_C['amber']} !important;
        }}
        [data-testid="stSidebar"] * {{ color: {_C['text']} !important; }}

        /* ── Expanders ── */
        .streamlit-expanderHeader {{
            background: rgba(17, 29, 59, 0.8) !important;
            backdrop-filter: blur(8px);
            border: 2px solid {_C['amber']} !important;
            border-radius: 14px !important;
            font-weight: 700 !important;
        }}

        /* ── Mobile ── */
        @media (max-width: 768px) {{
            .main-title {{ font-size: 1.6rem !important; }}
            .login-wordmark {{ font-size: 1.5rem !important; }}
            .section-card, .small-card {{ padding: 0.9rem 1rem !important; }}
            .stButton>button {{ min-height: 44px !important; font-size: 0.8rem !important; }}
            .stTextInput>div>div>input,
            .stTextArea>div>div>textarea {{ padding: 0.7rem !important; font-size: 16px !important; }}
        }}

        /* ── Auth ── */
        .auth-stripe {{
            height: 5px;
            background: linear-gradient(90deg, {_C['teal']} 0%, {_C['salmon']} 50%, {_C['amber']} 100%);
            border-radius: 99px;
            margin-bottom: 1.5rem;
        }}

        .login-wordmark {{
            font-size: 2.5rem;
            font-weight: 900;
            letter-spacing: 0.06em;
            color: {_C['text']};
            line-height: 1.05;
            text-transform: uppercase;
        }}

        .login-sub {{
            font-size: 0.7rem;
            font-weight: 700;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            color: {_C['amber']};
            margin-top: 0.75rem;
            margin-bottom: 1.5rem;
            line-height: 1.6;
        }}

        .auth-divider {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin: 1rem 0;
            color: {_C['muted']};
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.12em;
        }}
        .auth-divider::before, .auth-divider::after {{
            content: '';
            flex: 1;
            height: 2px;
            background: {_C['amber']};
            opacity: 0.3;
        }}

        .status-ok {{ color: {_C['success']}; font-size: 0.85rem; font-weight: 700; }}
        .status-err {{ color: {_C['salmon']}; font-size: 0.85rem; font-weight: 700; }}

        .avatar-row {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 1rem; }}
        .avatar-chip {{
            width: 44px; height: 44px;
            background: {_C['input_bg']};
            border: 2px solid {_C['border']};
            border-radius: 14px;
            display: flex; align-items: center; justify-content: center;
            font-size: 1.4rem;
            cursor: pointer;
            transition: transform 0.12s ease, border-color 0.12s ease;
        }}
        .avatar-chip.selected {{
            border-color: {_C['salmon']};
            transform: translateY(-2px);
            background: rgba(255,127,80,0.18);
            box-shadow: 0 4px 0 rgba(255,127,80,0.25);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    inject_pwa_meta()

@st.cache_resource
def get_database() -> Database:
    return Database(
        url=os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", ""),
        key=os.environ.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY", ""),
    )

@st.cache_resource
def pdflatex_available() -> bool:
    """Check if pdflatex is installed on the system."""
    import shutil
    return shutil.which("pdflatex") is not None

@st.cache_resource
def get_gemini_client() -> GeminiClient:
    return GeminiClient(
        api_key=os.environ.get("GOOGLE_API_KEY") or st.secrets.get("google_api_key"),
    )


def _persist_login(teacher_code: str):
    """Store teacher code in URL params so login survives refresh."""
    try:
        st.query_params["tk"] = teacher_code
    except Exception:
        pass  # older Streamlit; login won't persist

def _clear_persisted_login():
    """Remove the persisted token from URL."""
    try:
        st.query_params.clear()
    except Exception:
        pass


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
          themeMeta.content = '#0a1128';
          document.head.appendChild(themeMeta);

          // iOS full-screen / standalone mode
          const appleMeta = document.createElement('meta');
          appleMeta.name = 'apple-mobile-web-app-capable';
          appleMeta.content = 'yes';
          document.head.appendChild(appleMeta);

          const appleStatus = document.createElement('meta');
          appleStatus.name = 'apple-mobile-web-app-status-bar-style';
          appleStatus.content = 'black-translucent';
          document.head.appendChild(appleStatus);

          const appleTitle = document.createElement('meta');
          appleTitle.name = 'apple-mobile-web-app-title';
          appleTitle.content = 'MY-Mark';
          document.head.appendChild(appleTitle);

          const viewportMeta = document.createElement('meta');
          viewportMeta.name = 'viewport';
          viewportMeta.content = 'width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover';
          document.head.appendChild(viewportMeta);

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
            "<div class='login-wordmark'>MY-Mark</div>"
            "<div class='login-sub'>"
            "Make Your Mark with MY-Mark &nbsp;—&nbsp; AI-Supported, Semi-Automated Marking"
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
                    _persist_login(teacher["teacher_code"])
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
                        if teacher.get("teacher_code"):
                            _persist_login(teacher["teacher_code"])
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
            reg_pw = st.text_input("Password", key="reg_pw", placeholder="Min. 8 characters", type="password")
            reg_pw2 = st.text_input("Confirm Password", key="reg_pw2", placeholder="Repeat password", type="password")

            if st.button("Create Account →", key="reg_submit", use_container_width=True):
                import re
                err = None
                if not all([reg_name.strip(), reg_email.strip(), reg_pw, reg_pw2]):
                    err = "Please fill in all fields."
                elif not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", reg_email.strip()):
                    err = "Please enter a valid email address (e.g. teacher@school.edu)."
                elif len(reg_pw) < 8:
                    err = "Password must be at least 8 characters."
                elif reg_pw != reg_pw2:
                    err = "Passwords do not match."
                elif db.get_teacher_by_email(reg_email):
                    err = "An account with that email already exists. Sign in instead."

                if err:
                    st.markdown(f"<p class='status-err'>{err}</p>", unsafe_allow_html=True)
                else:
                    db.create_teacher(email=reg_email, display_name=reg_name, password=reg_pw)
                    teacher = db.get_teacher_by_email(reg_email)
                    st.session_state.authenticated = True
                    st.session_state.teacher = teacher
                    st.session_state.needs_setup = True
                    st.session_state.new_teacher_code = teacher["teacher_code"]
                    _persist_login(teacher["teacher_code"])
                    st.rerun()


# ── Account Setup page ────────────────────────────────────────────────────────
def render_account_setup(db: Database) -> None:
    inject_css()
    teacher = st.session_state.get("teacher", {})

    # Show new teacher code prominently (from registration)
    new_code = st.session_state.pop("new_teacher_code", None)
    if new_code:
        st.info(
            f"✅ Account created! Your teacher code is: **{new_code}**  \n"
            f"Save this — use it to log in from any device."
        )

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

        # Responsive 4-column grid that wraps cleanly on mobile
        cols_per_row = 4
        for row_start in range(0, len(avatars), cols_per_row):
            row_avatars = avatars[row_start:row_start + cols_per_row]
            avatar_cols = st.columns(len(row_avatars))
            for i, (av, acol) in enumerate(zip(row_avatars, avatar_cols)):
                with acol:
                    if av == selected_avatar:
                        st.markdown(
                            f"<div style='width:48px;height:48px;display:flex;align-items:center;justify-content:center;"
                            f"font-size:1.5rem;border:2px solid {_C['amber']};border-radius:14px;"
                            f"background:{_C['amber']}22;cursor:default'>✓</div>",
                            unsafe_allow_html=True
                        )
                    else:
                        if st.button(av, key=f"av_{row_start + i}"):
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


def _compile_with_fallback(tex_path: Path, output_dir: Path) -> Path | None:
    """Try pdflatex first, fall back to online API. Returns PDF path or None."""
    # Try local pdflatex
    try:
        return compile_latex(tex_path, output_dir)
    except (RuntimeError, FileNotFoundError) as exc:
        msg = str(exc)
        is_missing = "not found" in msg.lower() or "pdflatex" in msg.lower()
        if not is_missing:
            st.warning(f"Local LaTeX failed: {exc}. Trying online compiler...")
        else:
            st.info("pdflatex not installed — using online LaTeX compiler...")

    # Fallback: online API
    try:
        return compile_latex_online(tex_path, output_dir)
    except Exception as exc:
        st.error(
            f"LaTeX compilation failed both locally and online.\n\n"
            f"**Online error:** {exc}\n\n"
            f"You can copy the LaTeX source below and compile it at "
            f"[Overleaf](https://overleaf.com) or with a local TeX install."
        )
        return None


def extract_submission_text(uploaded_file) -> str:
    if uploaded_file.type.startswith("image/"):
        return _ocr_image(uploaded_file)

    if uploaded_file.type == "text/plain":
        return uploaded_file.read().decode("utf-8")

    if uploaded_file.type == "application/pdf":
        # Try text extraction first
        reader = PdfReader(uploaded_file)
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)
        text = "\n".join(text_parts).strip()
        if text:
            return text
        # Image-only PDF → Gemini Vision
        mime = "application/pdf"
        # Rely on Gemini's native PDF ingestion
        uploaded_file.seek(0)
        pdf_bytes = uploaded_file.read()
        try:
            gemini = get_gemini_client()
            with st.spinner("PDF is image-only — using Gemini Vision..."):
                text = gemini.extract_text_from_image(pdf_bytes, mime)
            if text.strip():
                st.caption("📷 Text extracted from PDF via Gemini Vision")
                return text.strip()
        except Exception:
            pass
        st.error("Could not extract text from PDF. Try uploading individual page images instead.")
        return ""

    return ""


def _ocr_image(uploaded_file) -> str:
    """Extract text from an image using Tesseract → Gemini Vision fallback."""
    try:
        image = Image.open(uploaded_file)
        text = image_to_string(image, lang="eng")
        if text.strip():
            return text.strip()
    except Exception:
        pass

    uploaded_file.seek(0)
    image_bytes = uploaded_file.read()
    mime = uploaded_file.type or "image/png"
    try:
        gemini = get_gemini_client()
        with st.spinner("Tesseract unavailable — using Gemini Vision..."):
            text = gemini.extract_text_from_image(image_bytes, mime)
        if text.strip():
            st.caption("📷 Text extracted via Gemini Vision")
            return text.strip()
    except Exception:
        pass

    st.error("OCR failed — please paste text directly.")
    return ""


def student_upload_area(db: Database, class_id: int, assignment_id: int, student_id: int):
    st.header("Upload Student Work")

    # Mode toggle
    mode = st.radio("Grading mode:", ["Grade now", "Upload for batch grading later"],
                    horizontal=True, key=f"mode_{student_id}")

    with st.form(key=f"submission_form_{student_id}"):
        # Multi-file upload
        uploaded_files = st.file_uploader(
            "Upload student work (supports multi-page — order by filename)",
            type=["png", "jpg", "jpeg", "pdf", "txt"],
            accept_multiple_files=True,
            key=f"files_{student_id}"
        )
        raw_text = st.text_area("OR paste student text here", height=220, key=f"text_{student_id}")
        submit = st.form_submit_button("Submit")

    if not submit:
        return

    # Extract text from all uploaded files in order
    submission_text = raw_text.strip()
    file_paths = []

    if uploaded_files and not submission_text:
        parts = []
        with st.spinner(f"Extracting text from {len(uploaded_files)} file(s)..."):
            for i, f in enumerate(uploaded_files):
                txt = extract_submission_text(f)
                if txt:
                    parts.append(f"[Page {i+1}]\n{txt}")
        submission_text = "\n\n--- Page Break ---\n\n".join(parts)

    if not submission_text:
        st.error("No extractable text found. Please paste text or upload clearer images.")
        return

    if mode == "Upload for batch grading later":
        try:
            db.add_submission(student_id, assignment_id, submission_text, file_paths)
        except RuntimeError as exc:
            st.error(str(exc))
            return
        st.success(f"✓ Submission queued for batch grading. {db.get_pending_count(assignment_id)} pending total.")
        return

    # Grade now mode
    _grade_submission(db, class_id, assignment_id, student_id, submission_text)


def _grade_submission(db: Database, class_id: int, assignment_id: int, student_id: int, submission_text: str):
    """Grade a single submission and produce feedback PDF."""
    assignment = db.get_assignment(assignment_id)
    student = db.get_student(student_id)
    history = db.get_feedback_history(student_id, assignment_id)
    previous_feedback = "\n\n".join([f"Draft {item.draft_number}: {item.feedback_json}" for item in history]) or "None"

    gemini = get_gemini_client()
    with st.spinner(f"Grading {student.name}..."):
        try:
            latex_result = gemini.generate_student_feedback(
                student_name=student.name,
                class_name=db.get_class(class_id).name,
                assignment=assignment,
                submission_text=submission_text,
                history=previous_feedback,
                subject=getattr(assignment, 'subject', 'english'),
            )
        except Exception as exc:
            st.error(f"Gemini API error: {exc}")
            return

    st.subheader(f"Feedback — {student.name}")
    st.code(latex_result, language="latex")

    tex_file = OUTPUT_DIR / f"feedback_{student_id}_{assignment_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.tex"
    try:
        write_tex_file(tex_file, latex_result)
    except Exception as exc:
        st.error(f"Failed to write LaTeX file: {exc}")
        return

    pdf_file = _compile_with_fallback(tex_file, OUTPUT_DIR)
    pdf_path = None
    if pdf_file:
        st.success("PDF generated successfully.")
        with open(pdf_file, "rb") as f:
            st.download_button("⬇ Download Feedback PDF", f, file_name=f"{student.name}_{assignment.title}.pdf",
                               key=f"dl_{student_id}_{assignment_id}", mime="application/pdf")
        try:
            pdf_path = db.upload_pdf(pdf_file)
            st.caption(f"☁️ Saved to cloud: [Open]({pdf_path})")
        except Exception as exc:
            pdf_path = str(pdf_file)
            st.caption(f"⚠️ Cloud upload failed: {exc}")
    else:
        st.warning("PDF could not be generated, but LaTeX code is shown above — copy to Overleaf.")

    # Persist result in session state
    st.session_state.setdefault("graded", {})
    st.session_state.graded[f"{student_id}_{assignment_id}"] = {
        "student_name": student.name,
        "latex": latex_result,
        "pdf_path": pdf_path,
        "assignment_title": assignment.title,
    }

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
        feedback_pdf_path=pdf_path,
    )


def render_batch_grading(db: Database, class_id: int, assignment_id: int):
    """Show pending submissions and allow batch grading."""
    pending = db.list_pending_submissions(assignment_id)
    if not pending:
        return

    st.header(f"📋 Batch Grading — {len(pending)} pending")

    # Show pending list
    pending_df = pd.DataFrame([{
        "Student": getattr(s, 'student_name', f"ID {s.student_id}"),
        "Submitted": s.created_at[:16],
        "Text length": len(s.submission_text),
    } for s in pending])
    st.dataframe(pending_df, hide_index=True)

    if st.button(f"Grade All {len(pending)} Pending Submissions", type="primary"):
        progress = st.progress(0)
        for i, sub in enumerate(pending):
            student_name = getattr(sub, 'student_name', f"Student {sub.student_id}")
            st.write(f"**Grading {i+1}/{len(pending)}: {student_name}**")
            _grade_submission(db, class_id, assignment_id, sub.student_id, sub.submission_text)
            db.mark_submission_graded(sub.id)
            progress.progress((i + 1) / len(pending))
            st.divider()

        st.success(f"✅ All {len(pending)} submissions graded!")
        st.rerun()


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
        pdf_file = _compile_with_fallback(report_file, OUTPUT_DIR)
        if pdf_file is None:
            return

        st.success("Class report PDF generated successfully.")
        with open(pdf_file, "rb") as f:
            st.download_button("⬇ Download Class Report PDF", f, file_name=f"{selected_class.name}_{assignment.title}_report.pdf",
                               key="dl_class_report", mime="application/pdf")

        # Persist in session
        st.session_state.setdefault("graded", {})
        st.session_state.graded["class_report"] = {
            "student_name": f"Class Report — {selected_class.name}",
            "latex": report_tex,
            "pdf_path": str(pdf_file),
            "assignment_title": f"{assignment.title} Report",
        }

        # Upload to cloud for cross-device access
        try:
            report_url = db.upload_pdf(pdf_file)
            st.caption(f"☁️ Report saved to cloud: [Open]({report_url})")
        except Exception:
            st.caption("⚠️ Could not upload report to cloud storage.")

        # Merge all PDFs — download cloud ones first
        student_pdf_paths = []
        for row in feedback_rows:
            path = row.feedback_pdf_path
            if not path:
                continue
            if str(path).startswith("http"):
                # Download from Supabase to a temp file
                try:
                    import tempfile
                    file_name = str(path).split("/")[-1].split("?")[0] or "feedback.pdf"
                    tmp = Path(tempfile.gettempdir()) / f"mymark_{file_name}"
                    resp = __import__("requests").get(str(path), timeout=30)
                    if resp.status_code == 200:
                        tmp.write_bytes(resp.content)
                        student_pdf_paths.append(str(tmp))
                except Exception:
                    pass
            elif Path(path).exists():
                student_pdf_paths.append(path)
        if student_pdf_paths:
            merged_path = OUTPUT_DIR / f"merged_{class_id}_{assignment_id}.pdf"
            merge_pdfs(student_pdf_paths, merged_path)
            with open(merged_path, "rb") as f:
                st.download_button("Download merged class PDFs", f, file_name=merged_path.name, mime="application/pdf")
        else:
            st.info("No existing student PDF files were found to merge.")


def render_mobile(db: Database, teacher: dict, teacher_id: int):
    """Mobile-first layout: submit-first, then map to class/student/assignment."""
    st.markdown("<div class='main-title' style='font-size:1.4rem;'>MY-Mark</div>", unsafe_allow_html=True)

    if st.button("🏠 Home", key="mob_back_home"):
        st.session_state.app_mode = None
        st.session_state.is_mobile = False
        st.rerun()

    teacher_code = teacher.get("teacher_code", "")
    if teacher_code:
        st.caption(f"Code: **{teacher_code}** | 🧠 `{get_gemini_client().last_model_used or 'ready'}`")

    # ── Quick submit: class picker ──
    classes = db.list_classes(teacher_id=teacher_id)
    if not classes:
        with st.expander("📚 Create First Class", expanded=True):
            new_class = st.text_input("Class name", key="mob_new_class", placeholder="e.g. P6 English SA2")
            if st.button("Create Class", key="mob_add_class") and new_class:
                try:
                    db.add_class(new_class, teacher_id=teacher_id)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        return

    class_sel = st.selectbox("Class", [c.name for c in classes], key="mob_class_sel")
    class_id = next(c.id for c in classes if c.name == class_sel)

    # ── Assignment: new or existing? ──
    assignments = db.list_assignments(class_id)
    assignment_id = None
    students = db.list_students(class_id)

    if assignments:
        asm_mode = st.radio("Assignment", ["📋 Use existing", "➕ Create new"], horizontal=True, key="mob_asm_mode")
    else:
        asm_mode = "➕ Create new"
        st.info("No assignments yet — create one below.")

    if asm_mode == "📋 Use existing":
        asm_sel = st.selectbox("Select assignment", [a.title for a in assignments], key="mob_asm_sel")
        assignment_id = next(a.id for a in assignments if a.title == asm_sel)
    else:
        with st.form(f"mob_new_assignment_{class_id}"):
            new_title = st.text_input("Assignment title", key="mob_new_asm_title", placeholder="e.g. SA2 Paper 1")
            new_subject = st.selectbox("Subject", ["english", "mathematics", "science"], key="mob_new_subject")
            new_context = st.text_area("Question / prompt (optional)", key="mob_new_ctx", height=80)
            if st.form_submit_button("Create & Continue", type="primary"):
                if new_title:
                    db.add_assignment(class_id, new_title, new_context or "[No prompt]", "Auto-generate on desktop", subject=new_subject)
                    st.rerun()
                else:
                    st.error("Please enter a title.")
            return  # wait for form submit

    if not assignment_id:
        return

    assignment = db.get_assignment(assignment_id)

    # ── Upload ──
    st.markdown("---")
    st.caption(f"📝 {assignment.title} · Subject: {getattr(assignment, 'subject', 'english').title()}")

    camera_photo = st.camera_input("Take photo", key=f"mob_cam_{assignment_id}")
    uploaded_files = st.file_uploader("Upload files", type=["png","jpg","jpeg","pdf","txt"],
                                       accept_multiple_files=True, key=f"mob_files_{assignment_id}")
    raw_text = st.text_area("OR paste text", key=f"mob_text_{assignment_id}", height=80)

    if st.button("📤 Extract & Tag Student", key=f"mob_upload_{assignment_id}", type="primary", use_container_width=True):
        submission_text = raw_text.strip()
        extracted = False

        if camera_photo and not submission_text:
            try:
                camera_photo.seek(0)
                submission_text = get_gemini_client().extract_text_from_image(camera_photo.read(), "image/jpeg")
                if submission_text and submission_text.strip():
                    extracted = True
                    st.session_state.mob_submission_text = submission_text
                else:
                    st.error("Photo was blank or unreadable. Please try again or paste text.")
            except Exception as exc:
                st.error(f"Could not read photo: {exc}")

        if uploaded_files and not submission_text:
            parts = []
            for i, f in enumerate(uploaded_files):
                txt = extract_submission_text(f)
                if txt:
                    parts.append(f"[Page {i+1}]\n{txt}")
            submission_text = "\n\n---\n\n".join(parts)
            if submission_text.strip():
                st.session_state.mob_submission_text = submission_text

        if not submission_text or not submission_text.strip():
            st.error("No text found. Take a clearer photo, upload a file, or paste text below.")
        elif not extracted and uploaded_files:
            st.session_state.mob_submission_text = submission_text

        if st.session_state.get("mob_submission_text"):
            st.rerun()

    # ── Tag to student ──
    if st.session_state.get("mob_submission_text"):
        st.success("✅ Text extracted!")
        if not students:
            # Quick add student inline
            new_stu = st.text_input("Add student", key="mob_add_stu_quick", placeholder="Student name")
            if st.button("Add & Select", key="mob_add_stu_btn") and new_stu:
                db.add_student(class_id, new_stu)
                st.rerun()
            st.info("Add a student above, then submit.")
        else:
            student_sel = st.selectbox("Which student?", [s.name for s in students], key="mob_stu_tag")
            student_id = next((s.id for s in students if s.name == student_sel), None)
            if st.button("✅ Submit", key="mob_confirm", type="primary", use_container_width=True):
                try:
                    db.add_submission(student_id, assignment_id, st.session_state.mob_submission_text)
                except RuntimeError as exc:
                    st.error(str(exc))
                    st.stop()
                st.session_state.pop("mob_submission_text", None)
                st.success(f"✓ {student_sel}'s work submitted!")
                st.rerun()

    # ── Quick actions ──
    pending = db.get_pending_count(assignment_id)
    if pending:
        st.info(f"📋 {pending} pending grading.")
    st.caption(f"To grade: open MY-Mark on your laptop.")

    st.markdown("---")
    if st.button("Sign Out", key="mob_signout"):
        for k in ["authenticated", "teacher", "needs_setup", "setup_avatar", "new_teacher_code"]:
            st.session_state.pop(k, None)
        _clear_persisted_login()
        st.rerun()


def _render_assignment_form(db: Database, class_id: int):
    """Render the assignment creation form (used in both desktop and mobile)."""
    st.caption("Create a new assignment")
    new_assignment_title = st.text_input("Title", key="new_assignment_title", placeholder="e.g. SA2 Continuous Writing")
    new_subject = st.selectbox("Subject", ["english", "mathematics", "science"], key="new_subject")

    qp_file = st.file_uploader("Upload question paper (PDF/image)", type=["png","jpg","jpeg","pdf"],
                               key="qp_upload", accept_multiple_files=True)
    new_context = st.text_area("OR paste question paper / prompt", key="new_assignment_context",
                               placeholder="Write a composition of at least 150 words...")

    st.markdown("**Answer Key / Rubric**")
    ak_file = st.file_uploader("Upload answer key (PDF/image)", type=["png","jpg","jpeg","pdf"],
                               key="ak_upload", accept_multiple_files=True)
    new_answer_key = st.text_area("OR paste answer key", key="new_assignment_answer_key",
                                  placeholder="AO1 Content (20m): ...")
    auto_generate = st.checkbox("Auto-generate answer key from question paper", key="auto_ak")

    if st.button("Add Assignment", key="add_assignment") and new_assignment_title:
        context_text = new_context.strip()
        if qp_file and not context_text:
            with st.spinner("Extracting question paper..."):
                context_parts = []
                for f in qp_file:
                    txt = extract_submission_text(f)
                    if txt:
                        context_parts.append(txt)
                context_text = "\n\n--- Page Break ---\n\n".join(context_parts)

        if context_text:
            answer_key_text = new_answer_key.strip()
            answer_key_source = "manual"
            if ak_file and not answer_key_text:
                with st.spinner("Extracting answer key..."):
                    ak_parts = []
                    for f in ak_file:
                        txt = extract_submission_text(f)
                        if txt:
                            ak_parts.append(txt)
                    answer_key_text = "\n\n".join(ak_parts)
            if auto_generate and not answer_key_text:
                with st.spinner("Gemini is generating an answer key..."):
                    gemini = get_gemini_client()
                    try:
                        answer_key_text = gemini.generate_answer_key(context_text)
                        answer_key_source = "generated"
                        st.success("Answer key auto-generated by Gemini.")
                    except Exception as exc:
                        st.error(f"Failed to generate answer key: {exc}")
            if answer_key_text:
                db.add_assignment(class_id, new_assignment_title, context_text,
                                answer_key_text, answer_key_source=answer_key_source,
                                subject=new_subject)
                st.rerun()
            else:
                st.error("Please provide an answer key or enable auto-generate.")
        else:
            st.error("Please provide a question paper (text or file).")

    assignments = db.list_assignments(class_id)
    if assignments:
        st.caption(f"{len(assignments)} assignment(s) — showing 3 most recent")
        st.write(pd.DataFrame([{"ID": a.id, "Title": a.title, "Subject": getattr(a,'subject','')} for a in assignments]))


def _render_home(db: Database, teacher: dict, teacher_id: int, is_mobile: bool):
    """Home screen: 'How can I make MY MARK today?' with 3 action cards."""
    inject_css()
    avatar = teacher.get("avatar", "🧑‍🏫") if isinstance(teacher, dict) else "🧑‍🏫"
    name = teacher.get("display_name", "Teacher") if isinstance(teacher, dict) else "Teacher"

    # Minimal sidebar
    with st.sidebar:
        st.markdown(f"### {avatar} {name}")
        teacher_code = teacher.get("teacher_code", "")
        if teacher_code:
            st.caption(f"Code: **{teacher_code}**")
        if st.button("Sign Out", key="home_signout"):
            for k in ["authenticated", "teacher", "needs_setup", "setup_avatar", "new_teacher_code", "app_mode"]:
                st.session_state.pop(k, None)
            _clear_persisted_login()
            st.rerun()

    # Centre column
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("<div class='auth-stripe'></div>", unsafe_allow_html=True)
        st.markdown("<div class='login-wordmark' style='font-size:2rem;'>MY-Mark</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='login-sub' style='font-size:0.9rem;'>How can I make MY MARK today?</div>",
            unsafe_allow_html=True,
        )

        pending_all = db.list_all_pending(teacher_id)
        total_pending = sum(len(v["submissions"]) for v in pending_all.values()) if pending_all else 0
        st.markdown("<br>", unsafe_allow_html=True)

        # Card 1: Submit
        st.markdown("#### 📤 Submit Assignments")
        st.caption("Take photos of student work. Map to class & student after upload.")
        if st.button("Start Submitting →", key="mode_submit", type="primary", use_container_width=True):
            st.session_state.app_mode = "submit"
            st.session_state.is_mobile = True
            st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        # Card 2: Grade
        badge = f" — {total_pending} pending" if total_pending else ""
        st.markdown(f"#### 📋 Grade Assignments{badge}")
        st.caption("Review and grade uploaded submissions. Generate feedback PDFs.")
        if st.button("Start Grading →", key="mode_grade", type="primary", use_container_width=True):
            st.session_state.app_mode = "grade"
            st.session_state.is_mobile = False
            st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        # Card 3: Configure
        st.markdown("#### ⚙️ Configure Dashboards")
        st.caption("Manage classes, students, assignments. Rename, archive, delete.")
        if st.button("Start Configuring →", key="mode_config", type="primary", use_container_width=True):
            st.session_state.app_mode = "configure"
            st.session_state.is_mobile = False
            st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        # Card 4: Past Reports
        st.markdown("#### 📄 View Past Reports")
        st.caption("Browse and download graded assignments, feedback PDFs, and class reports.")
        if st.button("View Reports →", key="mode_reports", type="primary", use_container_width=True):
            st.session_state.app_mode = "reports"
            st.session_state.is_mobile = False
            st.rerun()


def render_reports(db: Database, teacher_id: int):
    """Browse and download all past graded assignments."""
    inject_css()
    st.markdown("<div class='main-title'>📄 Past Reports</div>", unsafe_allow_html=True)
    if st.button("🏠 Home", key="reports_home"):
        st.session_state.app_mode = None
        st.rerun()

    classes = db.list_classes(teacher_id=teacher_id)
    if not classes:
        st.info("No classes yet.")
        return

    for cls in classes:
        st.subheader(f"📚 {cls.name}")
        assignments = db.list_assignments(cls.id, include_archived=True)
        if not assignments:
            st.caption("No assignments.")
            continue
        for asm in assignments:
            feedback_rows = db.get_feedback_for_class_assignment(cls.id, asm.id)
            if not feedback_rows:
                continue
            seen = {}
            for f in feedback_rows:
                sid = f.student_id
                if sid not in seen or f.draft_number > seen[sid].draft_number:
                    seen[sid] = f
            if seen:
                with st.expander(f"{asm.title} — {len(seen)} student(s) · {getattr(asm,'subject','english').title()}"):
                    for sid, fb in seen.items():
                        sname = fb.student_name or f"Student {sid}"
                        c1, c2 = st.columns([3, 1])
                        with c1:
                            st.caption(f"📎 {sname} — Draft {fb.draft_number}")
                        with c2:
                            path = fb.feedback_pdf_path
                            if path:
                                if str(path).startswith("http"):
                                    st.markdown(f"[Open PDF]({path})", unsafe_allow_html=True)
                                elif Path(path).exists():
                                    with open(path, "rb") as pf:
                                        st.download_button("⬇ Download", pf, file_name=f"{sname}_{asm.title}.pdf", key=f"rpt_{fb.id}", mime="application/pdf")
                                else:
                                    st.caption("No file available")
                            else:
                                st.caption("Not yet generated")


def main():
    db = get_database()

    # ── Auto-login from persisted token ──
    if not st.session_state.get("authenticated"):
        try:
            token = st.query_params.get("tk")
        except Exception:
            token = None
        if token and isinstance(token, str) and len(token) >= 4:
            try:
                teacher = db.get_teacher_by_code(token)
                if teacher:
                    st.session_state.authenticated = True
                    st.session_state.teacher = teacher
                    st.session_state.needs_setup = not bool(teacher.get("setup_complete"))
                    st.toast(f"👋 Welcome back, {teacher.get('display_name', 'Teacher')}!", icon="🔐")
                    st.rerun()
            except Exception:
                pass

    # ── Auth gate ──
    if not st.session_state.get("authenticated"):
        render_login(db)
        return

    # ── Account setup gate ──
    if st.session_state.get("needs_setup"):
        render_account_setup(db)
        return

    inject_css()

    # ── Teacher info ──
    teacher = st.session_state.get("teacher", {})
    teacher_id = teacher.get("id") if isinstance(teacher, dict) else None

    # ── Mobile toggle ──
    is_mobile = st.session_state.get("is_mobile", False)

    # ── Home screen: 3-action launcher ──
    if not st.session_state.get("app_mode"):
        _render_home(db, teacher, teacher_id, is_mobile)
        return

    if is_mobile or st.session_state.get("app_mode") == "submit":
        st.session_state.is_mobile = True
        render_mobile(db, teacher, teacher_id)
        return

    # ── Grade mode or Configure mode: desktop dashboard ──
    if st.session_state.get("app_mode") == "reports":
        render_reports(db, teacher_id)
        return

    # ── Sidebar + main area sidebar-toggle ──
    avatar = teacher.get("avatar", "🧑‍🏫") if isinstance(teacher, dict) else "🧑‍🏫"
    name = teacher.get("display_name", "Teacher") if isinstance(teacher, dict) else "Teacher"

    # Sidebar identity
    with st.sidebar:
        st.markdown(f"### {avatar} {name}")
        if st.button("Sign Out", key="signout"):
            for k in ["authenticated", "teacher", "needs_setup", "setup_avatar", "new_teacher_code"]:
                st.session_state.pop(k, None)
            _clear_persisted_login()
            st.rerun()
        teacher_code = teacher.get("teacher_code", "")
        if teacher_code:
            st.caption(f"Code: **{teacher_code}**")
        gemini = get_gemini_client()
        if gemini.last_model_used:
            st.caption(f"🧠 `{gemini.last_model_used}`")
        if pdflatex_available():
            st.caption("📄 pdflatex ready")
        else:
            st.caption("⚠️ pdflatex missing")
        if st.button("📱 Mobile View", key="layout_toggle"):
            st.session_state.is_mobile = True
            st.rerun()

        st.divider()
        st.caption("⚙️ CLASS ADMIN")
        new_class_name = st.text_input("New class", key="new_class_name", placeholder="Class name")
        if st.button("Add Class", key="add_class") and new_class_name:
            try:
                db.add_class(new_class_name, teacher_id=teacher_id)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    # ── Landing page ──
    col_title, col_back = st.columns([4, 1])
    with col_title:
        st.markdown("<div class='main-title'>MY-Mark Dashboard</div>", unsafe_allow_html=True)
    with col_back:
        if st.button("🏠 Home", key="back_home_desk"):
            st.session_state.app_mode = None
            st.rerun()

    # ── Persistent grading results ──
    graded = st.session_state.get("graded", {})
    if graded:
        with st.expander(f"📄 Latest Graded Results — {len(graded)} result(s)", expanded=True):
            for key, gr in graded.items():
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    st.caption(f"📎 {gr['student_name']} — {gr.get('assignment_title','')}")
                with c2:
                    st.code(gr.get("latex","")[:200] + "..." if len(gr.get("latex","")) > 200 else gr.get("latex",""), language="latex")
                with c3:
                    pdf = gr.get("pdf_path")
                    if pdf and str(pdf).startswith("http"):
                        st.markdown(f"[Open PDF]({pdf})", unsafe_allow_html=True)
                    elif pdf and Path(pdf).exists():
                        with open(pdf, "rb") as pf:
                            st.download_button("⬇ Download", pf, file_name=f"{gr['student_name']}.pdf", key=f"persist_{key}", mime="application/pdf")
            if st.button("Clear Results", key="clear_graded"):
                st.session_state.pop("graded", None)
                st.rerun()
        st.divider()

    # ── PENDING GRADING — always first, before anything else ──
    pending_all = db.list_all_pending(teacher_id)
    total_pending = sum(len(v["submissions"]) for v in pending_all.values()) if pending_all else 0

    # If cross-class query failed, try per-class
    if not pending_all:
        classes_temp = db.list_classes(teacher_id=teacher_id)
        for cls in classes_temp:
            asms = db.list_assignments(cls.id, include_archived=False)
            for a in asms:
                subs = db.list_pending_submissions(a.id)
                if subs:
                    key = f"{cls.id}:{a.id}:{a.title}"
                    pending_all[key] = {
                        "class_id": cls.id, "assignment_id": a.id,
                        "title": a.title,
                        "submissions": [{
                            "id": s.id, "student_id": s.student_id,
                            "student_name": getattr(s, 'student_name', f"Student {s.student_id}"),
                            "submission_text": s.submission_text,
                        } for s in subs]
                    }
        total_pending = sum(len(v["submissions"]) for v in pending_all.values()) if pending_all else 0

    if total_pending:
        st.warning(f"📋 **{total_pending} submission(s) pending grading** — uploaded from mobile, ready for review.")
    else:
        st.caption("✅ No pending submissions — all graded.")

    # Show per-student submissions immediately
    if pending_all:
        st.subheader(f"📋 Pending Submissions")
        if st.button("⚡ Grade ALL", key="grade_all_top", type="primary"):
            for key, data in pending_all.items():
                for sub in data['submissions']:
                    _grade_submission(db, data['class_id'], data['assignment_id'], sub['student_id'], sub['submission_text'])
                    db.mark_submission_graded(sub['id'])
            st.rerun()

        for key, data in pending_all.items():
            st.markdown(f"**{data['title']}** — {len(data['submissions'])} pending")
            for sub in data['submissions']:
                sname = sub.get("student_name", f"Student {sub['student_id']}")
                text_len = len(sub.get('submission_text', ''))
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.caption(f"👤 {sname} — {text_len} chars")
                with c2:
                    if st.button("Grade", key=f"gsub_{sub['id']}"):
                        _grade_submission(db, data['class_id'], data['assignment_id'], sub['student_id'], sub['submission_text'])
                        db.mark_submission_graded(sub['id'])
                        st.rerun()
            st.markdown("---")
        st.divider()

    classes = db.list_classes(teacher_id=teacher_id)
    if not classes:
        st.info("👋 Welcome! Create your first class in the sidebar to begin.")
        return

    class_options = {c.name: c.id for c in classes}
    selected_class_name = st.selectbox("Active Class", list(class_options.keys()), key="selected_class")
    class_id = class_options.get(selected_class_name)
    if not class_id:
        return
    selected_class = db.get_class(class_id)
    students = db.list_students(class_id)
    assignments = db.list_assignments(class_id)

    dash_left, dash_right = st.columns([3, 2])

    with dash_left:
        with st.container(border=True):
            st.subheader(f"📚 {selected_class.name}")
            st.caption(f"**{len(students)} student(s)** · **{len(assignments)} assignment(s)**")
            if students:
                student_names = [s.name for s in students]
                st.caption("Students: " + ", ".join(student_names[:8]) + ("..." if len(student_names) > 8 else ""))
            else:
                st.caption("No students yet — add below")
            col_add_stu, _ = st.columns([2, 1])
            with col_add_stu:
                new_student_name = st.text_input("Add student", key="ds_new_student", placeholder="Student name", label_visibility="collapsed")
                if st.button("+ Add", key="ds_add_student") and new_student_name:
                    db.add_student(class_id, new_student_name)
                    st.rerun()
            if students:
                student_options = {s.name: s.id for s in students}
                selected_student_name = st.selectbox("Selected Student", list(student_options.keys()), key="selected_student")
                student_id = student_options.get(selected_student_name)
            else:
                student_id = None
            with st.popover("⚙️ Manage Class"):
                new_name = st.text_input("Rename", value=selected_class_name, key="ds_rename")
                if st.button("Rename Class", key="ds_do_rename") and new_name != selected_class_name:
                    try:
                        db.rename_class(class_id, new_name)
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
                if st.button("🗑 Delete Class", key="ds_delete", type="secondary"):
                    db.delete_class(class_id)
                    st.session_state.selected_class = "Choose a class"
                    st.rerun()

    with dash_right:
        with st.container(border=True):
            st.subheader("📝 Assignments")
            if assignments:
                assignment_options = {a.title: a.id for a in assignments}
                selected_assignment_title = st.selectbox("Active", list(assignment_options.keys()), key="selected_assignment", label_visibility="collapsed")
                assignment_id = assignment_options.get(selected_assignment_title)
                if assignment_id:
                    asm = db.get_assignment(assignment_id)
                    st.caption(f"Subject: **{getattr(asm, 'subject', 'english').title()}**")
                    drafts = db.get_feedback_history(student_id, assignment_id) if student_id else []
                    if drafts:
                        st.caption(f"📄 {len(drafts)} draft(s)")
                    col_archive, _ = st.columns([1, 1])
                    with col_archive:
                        if st.button("📦 Archive", key="ds_archive"):
                            db.archive_assignment(assignment_id)
                            st.rerun()
            else:
                assignment_id = None
                st.caption("No assignments yet")
            with st.popover("➕ New Assignment"):
                _render_assignment_form(db, class_id)
                st.rerun()

    if not assignment_id:
        st.info("Select or create an assignment to begin grading.")
        return

    # ── Graded student downloads ──
    if assignment_id and students:
        # Get graded feedback for this assignment
        graded = db.get_feedback_for_class_assignment(class_id, assignment_id)
        # Deduplicate by student — show latest draft
        seen = {}
        for f in graded:
            sid = f.student_id
            if sid not in seen or f.draft_number > seen[sid].draft_number:
                seen[sid] = f
        if seen:
            with st.expander(f"📄 Graded Feedback — {len(seen)} student(s)", expanded=False):
                for sid, fb in seen.items():
                    sname = fb.student_name or f"Student {sid}"
                    col_name, col_btn = st.columns([3, 1])
                    with col_name:
                        st.caption(f"📎 {sname} — Draft {fb.draft_number}")
                    with col_btn:
                        if fb.feedback_pdf_path:
                            # If it's a cloud URL, link to it; if local, create download
                            path = fb.feedback_pdf_path
                            if str(path).startswith("http"):
                                st.markdown(f"[Open PDF]({path})", unsafe_allow_html=True)
                            elif Path(path).exists():
                                with open(path, "rb") as pf:
                                    st.download_button("Download", pf, file_name=f"{sname}_{selected_assignment_title}.pdf",
                                                       key=f"dl_{fb.id}", mime="application/pdf")

    if not student_id:
        st.info("Select a student above to upload and grade their work.")
        return

    st.divider()
    st.subheader(f"📤 Grading: {selected_class.name} — {selected_assignment_title} — {selected_student_name}")
    render_feedback_history(db, student_id, assignment_id)
    student_upload_area(db, class_id, assignment_id, student_id)
    render_class_report(db, class_id, assignment_id)


if __name__ == "__main__":
    main()
