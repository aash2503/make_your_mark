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
        .stTextArea>div>div>textarea,
        .stSelectbox>div>div>div {{
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

@st.cache_resource
def get_database() -> Database:
    return Database(
        url=os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", ""),
        key=os.environ.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY", ""),
    )

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
        # Try tesseract first
        try:
            image = Image.open(uploaded_file)
            text = image_to_string(image, lang="eng")
            if text.strip():
                return text.strip()
        except Exception:
            pass

        # Fallback: Gemini Vision OCR
        try:
            uploaded_file.seek(0)
            image_bytes = uploaded_file.read()
            mime = uploaded_file.type or "image/png"
            gemini = get_gemini_client()
            with st.spinner("Tesseract unavailable — using Gemini Vision for OCR..."):
                text = gemini.extract_text_from_image(image_bytes, mime)
            if text.strip():
                st.caption("📷 Text extracted via Gemini Vision")
                return text.strip()
        except Exception:
            st.error("OCR failed — both Tesseract and Gemini Vision are unavailable. Please paste text directly.")
            return ""

        st.error("No text could be extracted from the image. Please paste text directly.")
        return ""

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
            st.error(f"Grading failed for {student.name}: {exc}")
            return

    st.subheader(f"Feedback — {student.name}")
    st.code(latex_result, language="latex")

    tex_file = OUTPUT_DIR / f"feedback_{student_id}_{assignment_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.tex"
    write_tex_file(tex_file, latex_result)

    pdf_file = _compile_with_fallback(tex_file, OUTPUT_DIR)
    pdf_path = None
    if pdf_file:
        st.success("PDF generated successfully.")
        with open(pdf_file, "rb") as f:
            st.download_button("Download feedback PDF", f, file_name=pdf_file.name, mime="application/pdf")
        # Upload to cloud
        try:
            pdf_path = db.upload_pdf(pdf_file)
            st.caption(f"☁️ Saved to cloud: [Open]({pdf_path})")
        except Exception:
            pdf_path = str(pdf_file)
            st.caption("⚠️ Could not upload PDF to cloud.")

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
            st.download_button("Download class report PDF", f, file_name=pdf_file.name, mime="application/pdf")

        # Upload to cloud for cross-device access
        try:
            report_url = db.upload_pdf(pdf_file)
            st.caption(f"☁️ Report saved to cloud: [Open]({report_url})")
        except Exception:
            st.caption("⚠️ Could not upload report to cloud storage.")

        # Merge local PDFs (skips cloud URLs — download individual PDFs instead)
        student_pdf_paths = [
            row.feedback_pdf_path for row in feedback_rows
            if row.feedback_pdf_path
            and not str(row.feedback_pdf_path).startswith("http")
            and Path(row.feedback_pdf_path).exists()
        ]
        if student_pdf_paths:
            merged_path = OUTPUT_DIR / f"merged_{class_id}_{assignment_id}.pdf"
            merge_pdfs(student_pdf_paths, merged_path)
            with open(merged_path, "rb") as f:
                st.download_button("Download merged class PDFs", f, file_name=merged_path.name, mime="application/pdf")
        else:
            st.info("No existing student PDF files were found to merge.")


def render_mobile(db: Database, teacher: dict, teacher_id: int):
    """Mobile-first layout: camera input, linear flow, no sidebar."""
    st.markdown("<div class='main-title' style='font-size:1.4rem;'>MY-Mark</div>", unsafe_allow_html=True)

    teacher_code = teacher.get("teacher_code", "")
    if teacher_code:
        st.caption(f"Your code: **{teacher_code}** | 🧠 `{get_gemini_client().last_model_used or 'ready'}`")

    # ── Section 1: Class ──
    with st.expander("📚 Class", expanded=True):
        classes = db.list_classes(teacher_id=teacher_id)
        new_class = st.text_input("New class name", key="mob_new_class", placeholder="e.g. P6 English SA2")
        if st.button("Add Class", key="mob_add_class") and new_class:
            try:
                db.add_class(new_class, teacher_id=teacher_id)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

        if classes:
            class_sel = st.selectbox("Active class", [c.name for c in classes], key="mob_class_sel")
            class_id = next(c.id for c in classes if c.name == class_sel)
            st.caption(f"{len(classes)} class(es)")
        else:
            class_id = None

    if not class_id:
        st.info("Create a class above to get started.")
        return

    selected_class = db.get_class(class_id)

    # ── Section 2: Students ──
    with st.expander("👥 Students", expanded=False):
        new_student = st.text_input("Student name", key="mob_new_student", placeholder="e.g. Alice Tan")
        if st.button("Add Student", key="mob_add_student") and new_student:
            db.add_student(class_id, new_student)
            st.rerun()
        students = db.list_students(class_id)
        if students:
            st.write(pd.DataFrame([{"Name": s.name} for s in students], index=range(1, len(students)+1)))

    # ── Section 3: Assignments (create on desktop, mobile just selects) ──
    with st.expander("📝 Assignment", expanded=False):
        assignments = db.list_assignments(class_id)
        if not assignments:
            st.info("Create an assignment on desktop first, then upload here.")
            return
        assignment_sel = st.selectbox("Active assignment", [a.title for a in assignments], key="mob_asm_sel")
        assignment_id = next(a.id for a in assignments if a.title == assignment_sel)
        assignment = db.get_assignment(assignment_id)
        st.caption(f"Subject: {getattr(assignment, 'subject', 'english').title()}")

    # ── Section 4: Upload ──
    student_sel = st.selectbox("Student", [s.name for s in students], key="mob_stu_sel") if students else None
    student_id = next(s.id for s in students if s.name == student_sel) if student_sel else None

    if not student_id:
        st.info("Select a student.")
        return

    st.markdown("---")
    st.caption(f"📝 {assignment.title}  |  👤 {student_sel}")

    camera_photo = st.camera_input("Take photo", key=f"cam_{student_id}")
    uploaded_files = st.file_uploader("Upload file(s)", type=["png","jpg","jpeg","pdf","txt"],
                                       accept_multiple_files=True, key=f"mob_files_{student_id}")
    raw_text = st.text_area("OR paste text", key=f"mob_text_{student_id}", height=100)

    if st.button("Submit for Grading", key=f"mob_submit_{student_id}", type="primary", use_container_width=True):
        submission_text = raw_text.strip()
        if camera_photo and not submission_text:
            camera_photo.seek(0)
            try:
                submission_text = get_gemini_client().extract_text_from_image(camera_photo.read(), "image/jpeg")
            except Exception:
                st.error("Could not read photo.")
                return
        if uploaded_files and not submission_text:
            parts = []
            for i, f in enumerate(uploaded_files):
                txt = extract_submission_text(f)
                if txt:
                    parts.append(f"[Page {i+1}]\n{txt}")
            submission_text = "\n\n---\n\n".join(parts)
        if not submission_text:
            st.error("No text found.")
            return
        try:
            db.add_submission(student_id, assignment_id, submission_text)
        except RuntimeError as exc:
            st.error(str(exc))
            return
        st.success(f"✓ Uploaded! Grade on desktop. {db.get_pending_count(assignment_id)} pending.")
        st.rerun()

    # ── Section 5: Pending status ──
    pending = db.get_pending_count(assignment_id)
    if pending:
        st.info(f"📋 {pending} submission(s) pending grading on desktop.")

    # ── Footer ──
    st.markdown("---")
    if st.button("Sign Out", key="mob_signout"):
        for k in ["authenticated", "teacher", "needs_setup", "setup_avatar", "new_teacher_code"]:
            st.session_state.pop(k, None)
        st.rerun()


def _detect_mobile() -> bool:
    """Detect mobile via query param + JS redirect for narrow screens."""
    if st.session_state.get("is_mobile") is not None:
        return st.session_state.is_mobile

    # Check URL param (handle both old list-style and new string-style)
    try:
        raw = st.query_params.get("mobile")
    except Exception:
        raw = None
    if raw in ("1", ["1"]):
        st.session_state.is_mobile = True
        return True

    # Inject JS to auto-detect and redirect
    components.html(
        """<script>
        if (window.innerWidth < 768 && !window.location.search.includes('mobile=1')) {
            var sep = window.location.search ? '&' : '?';
            window.location.search += sep + 'mobile=1';
        }
        </script>""",
        height=0, width=0,
    )
    st.session_state.is_mobile = False
    return False


def main():
    db = get_database()

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

    # ── Mobile detection ──
    is_mobile = _detect_mobile()

    if is_mobile:
        render_mobile(db, teacher, teacher_id)
        return

    # ── Desktop layout below ──
    avatar = teacher.get("avatar", "🧑‍🏫") if isinstance(teacher, dict) else "🧑‍🏫"
    name = teacher.get("display_name", "Teacher") if isinstance(teacher, dict) else "Teacher"

    st.sidebar.markdown(
        f"<div style='padding:0.6rem 0; border-bottom:1px solid #1e3a5f; margin-bottom:0.8rem;'>"
        f"<span style='font-size:1.4rem;'>{avatar}</span>&nbsp;"
        f"<span style='font-weight:900; font-size:0.8rem; color:#e8edf5;'>{name}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )
    if st.sidebar.button("Sign Out", key="signout"):
        for k in ["authenticated", "teacher", "needs_setup", "setup_avatar", "new_teacher_code"]:
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

    st.sidebar.title("MY-Mark")
    st.sidebar.markdown("## Classes & Assignments")

    classes = db.list_classes(teacher_id=teacher_id)

    with st.sidebar.expander("Create New Class", expanded=not bool(classes)):
        new_class_name = st.text_input("Class Name", key="new_class_name")
        if st.button("Add Class", key="add_class") and new_class_name:
            try:
                db.add_class(new_class_name, teacher_id=teacher_id)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    if classes:
        # Show class list with manage options
        st.sidebar.caption(f"Your classes ({len(classes)})")
        class_options = {c.name: c.id for c in classes}
        selected_class_name = st.sidebar.selectbox(
            "Select Class", ["Choose a class"] + list(class_options.keys()),
            key="selected_class"
        )
        class_id = class_options.get(selected_class_name)

        # Class management: rename / delete
        if class_id and "class_mgmt_open" not in st.session_state:
            st.session_state.class_mgmt_open = False
        if class_id:
            with st.sidebar.expander(f"Manage: {selected_class_name}"):
                new_name = st.text_input("Rename class", key="rename_class", value=selected_class_name)
                if st.button("Rename", key="do_rename") and new_name != selected_class_name:
                    try:
                        db.rename_class(class_id, new_name)
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))

                if st.button("🗑 Delete this class", key="delete_class", type="secondary"):
                    db.delete_class(class_id)
                    st.session_state.selected_class = "Choose a class"
                    st.rerun()
    else:
        class_id = None

    if not class_id:
        st.markdown("<div class='main-title'>MY-Mark Dashboard</div>", unsafe_allow_html=True)
        st.markdown("<p class='subheader-text'>Create or select a class from the sidebar to begin marking.</p>", unsafe_allow_html=True)
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
        st.caption("Create a new assignment")
        new_assignment_title = st.text_input("Title", key="new_assignment_title", placeholder="e.g. SA2 Continuous Writing")
        new_subject = st.selectbox("Subject", ["english", "mathematics", "science"], key="new_subject")

        # Question paper: text + optional file
        qp_file = st.file_uploader("Upload question paper (PDF/image)", type=["png","jpg","jpeg","pdf"],
                                   key="qp_upload", accept_multiple_files=True)
        new_context = st.text_area("OR paste question paper / prompt", key="new_assignment_context",
                                   placeholder="Write a composition of at least 150 words...")

        # Answer key: text + optional file + auto-generate
        st.markdown("**Answer Key / Rubric**")
        ak_file = st.file_uploader("Upload answer key (PDF/image)", type=["png","jpg","jpeg","pdf"],
                                   key="ak_upload", accept_multiple_files=True)
        new_answer_key = st.text_area("OR paste answer key", key="new_assignment_answer_key",
                                      placeholder="AO1 Content (20m): ...")

        auto_generate = st.checkbox("Auto-generate answer key from question paper", key="auto_ak")

        if st.button("Add Assignment", key="add_assignment") and new_assignment_title:
            context_text = new_context.strip()

            # Extract text from uploaded question paper files
            if qp_file and not context_text:
                with st.spinner("Extracting question paper..."):
                    context_parts = []
                    for f in qp_file:
                        txt = extract_submission_text(f)
                        if txt:
                            context_parts.append(txt)
                    context_text = "\n\n--- Page Break ---\n\n".join(context_parts)

            if context_text:
                # Determine answer key
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

    assignment_options = {a.title: a.id for a in assignments}
    selected_assignment_title = st.sidebar.selectbox("Select Assignment", ["Choose an assignment"] + list(assignment_options.keys()), key="selected_assignment")
    assignment_id = assignment_options.get(selected_assignment_title)

    # Archive button for selected assignment
    if assignment_id:
        if st.sidebar.button("📦 Archive this assignment", key="archive_asm"):
            db.archive_assignment(assignment_id)
            st.rerun()

    student_options = {s.name: s.id for s in students}
    selected_student_name = st.sidebar.selectbox("Select Student", ["Choose a student"] + list(student_options.keys()), key="selected_student")
    student_id = student_options.get(selected_student_name)

    st.markdown("<div class='main-title'>MY-Mark Dashboard</div>", unsafe_allow_html=True)
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
        st.markdown("- Upload & grade now\n- Upload for batch grading\n- Create class competency report")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='small-card'>", unsafe_allow_html=True)
        st.subheader("Status")
        st.markdown(f"**Students:** {len(students)}")
        st.markdown(f"**Assignments:** {len(assignments)}")
        if assignment_id:
            pending_count = db.get_pending_count(assignment_id)
            if pending_count:
                st.markdown(f"**📋 Pending grading:** {pending_count}")
        if student_id and assignment_id:
            history = db.get_feedback_history(student_id, assignment_id)
            st.markdown(f"**Drafts saved:** {len(history)}")
        st.markdown("</div>", unsafe_allow_html=True)

    if not assignment_id:
        st.warning("Select an assignment before grading.")
        return

    # Show batch grading section for this assignment
    render_batch_grading(db, class_id, assignment_id)

    if not student_id:
        st.info("Select a student above to upload and grade individual work.")
        return

    render_feedback_history(db, student_id, assignment_id)
    student_upload_area(db, class_id, assignment_id, student_id)
    render_class_report(db, class_id, assignment_id)


if __name__ == "__main__":
    main()
