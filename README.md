# AI Marking Assistant

A Streamlit-based AI grading assistant for Singapore MOE PSLE English.  
Uses **Google Gemini 3.1 Flash Lite** to analyse student submissions and generate strict, rubric-based feedback as LaTeX → PDF reports.

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

1. **Push this repo to GitHub** (public or private).
2. Go to [share.streamlit.io](https://share.streamlit.io) and click **New app**.
3. Select your repository, branch `main`, and app file `app.py`.
4. In **Advanced settings → Secrets**, add the following keys:

```toml
google_api_key = "YOUR_GEMINI_API_KEY"
gemini_model   = "gemini-3.1-flash-lite"
google_oauth_client_id = "YOUR_GOOGLE_OAUTH_CLIENT_ID"
google_oauth_client_secret = "YOUR_GOOGLE_OAUTH_CLIENT_SECRET"
google_oauth_redirect_uri = "https://<your-app-name>.streamlit.app"
pin_code       = ""
```

5. Click **Deploy**. Streamlit Cloud will install `requirements.txt` and `packages.txt` automatically.

### What to configure in Google Cloud
- Create an OAuth consent screen and a Web application OAuth client.
- Set the redirect URI to your deployed app URL, e.g. `https://<your-app-name>.streamlit.app`.
- If you want local testing, also add `http://localhost:8501` as an authorized redirect URI.

### Notes
- PWA support is enabled through `static/manifest.json` and `static/sw.js`.
- Static assets are served from `/static/`.
- Google Drive upload requires OAuth with `drive.file` scope.

> **Get a Gemini API key:** [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)

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
## Deployment guide

See `DEPLOYMENT.md` for step-by-step Streamlit Cloud deployment and Google OAuth setup.

---
## Progressive Web App (PWA)

This project includes PWA support via `static/manifest.json` and `static/sw.js`.
The app injects the web app manifest and registers a service worker on page load.

The PWA asset files are served from `/app/static/`.

**Included files:**
- `static/manifest.json`
- `static/sw.js`
- `static/icon-192.svg`
- `static/icon-512.svg`

---

## Project Structure

```
ai_marking_assistant/
├── app.py                  # Main Streamlit app (login, dashboard, grading)
├── database.py             # SQLite persistence (teachers, classes, students, feedback)
├── gemini_client.py        # Google Gemini 3.1 Flash Lite API integration
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
| `gemini_model` | Model name (default: `gemini-3.1-flash-lite`) |
| `google_oauth_client_id` | Google OAuth client ID |
| `google_oauth_client_secret` | Google OAuth client secret |
| `google_oauth_redirect_uri` | Registered OAuth redirect URI |
| `pin_code` | Optional legacy PIN for quick access |

---

## Notes

- The SQLite database (`marking_assistant.db`) is excluded from git — it is created fresh on each deployment. Use the export/import features for persistence across deployments.
- For production Google OAuth, replace `_mock_google_login()` in `app.py` with a real `google-auth-oauthlib` flow.
- LaTeX compilation requires `pdflatex` — available on Streamlit Cloud via `packages.txt`.
