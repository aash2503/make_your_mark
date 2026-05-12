# AI Marking Assistant

A Streamlit-based AI grading assistant for Singapore MOE PSLE English.  
Uses **Google Gemini 1.5** to analyse student submissions and generate strict, rubric-based feedback as LaTeX → PDF reports.

---

## Features

- 🔐 **Teacher accounts** — email/password registration, Google Sign-In (prototype), legacy PIN fallback
- 🧑‍🏫 **Account setup** — display name, school, subject, avatar
- 📚 **Class & student management** — create classes, add students, manage assignments
- 📝 **AI grading** — upload handwritten images, PDFs, or paste text; Gemini grades against PSLE rubrics
- 📄 **PDF feedback** — LaTeX compiled to PDF per student, downloadable
- 📊 **Class competency report** — aggregated analysis across all students
- 💾 **Feedback history** — tracks draft-by-draft progression per student

---

## Quick Start (Local)

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/ai_marking_assistant.git
cd ai_marking_assistant

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Install system packages (macOS)
brew install tesseract
brew install --cask mactex   # or: brew install basictex

# 4. Configure secrets
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit .streamlit/secrets.toml and add your Gemini API key

# 5. Run
streamlit run app.py
```

---

## Deploy to Streamlit Cloud

1. **Push this repo to GitHub** (public or private)
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Select your repo, branch `main`, file `app.py`
4. Click **Advanced settings → Secrets** and paste:

```toml
google_api_key = "YOUR_GEMINI_API_KEY"
gemini_model   = "gemini-1.5-flash"
pin_code       = ""
```

5. Click **Deploy** — Streamlit Cloud will install `requirements.txt` and `packages.txt` automatically.

> **Get a Gemini API key:** [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) — free tier available.

---

## System Packages (packages.txt)

Streamlit Cloud uses `packages.txt` to install apt packages:

```
tesseract-ocr
texlive-latex-base
texlive-latex-extra
texlive-fonts-recommended
```

These are already configured in `packages.txt`.

---

## Project Structure

```
ai_marking_assistant/
├── app.py                  # Main Streamlit app (login, dashboard, grading)
├── database.py             # SQLite persistence (teachers, classes, students, feedback)
├── gemini_client.py        # Google Gemini 1.5 API integration
├── latex_utils.py          # LaTeX → PDF compilation helpers
├── requirements.txt        # Python dependencies
├── packages.txt            # Streamlit Cloud system packages
├── Procfile                # Deployment entrypoint
├── .streamlit/
│   ├── config.toml         # Theme (dark blue, salmon/teal/amber)
│   └── secrets.toml.example  # Secrets template (copy → secrets.toml)
└── .gitignore
```

---

## Secrets Reference

| Key | Description |
|-----|-------------|
| `google_api_key` | Gemini API key from Google AI Studio |
| `gemini_model` | Model name (default: `gemini-1.5-flash`) |
| `pin_code` | Optional legacy PIN for quick access |

---

## Notes

- The SQLite database (`marking_assistant.db`) is excluded from git — it is created fresh on each deployment. Use the export/import features for persistence across deployments.
- For production Google OAuth, replace `_mock_google_login()` in `app.py` with a real `google-auth-oauthlib` flow.
- LaTeX compilation requires `pdflatex` — available on Streamlit Cloud via `packages.txt`.
