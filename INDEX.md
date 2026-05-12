# AI Marking Assistant Project Index

## Project Overview
A Streamlit-based AI grading assistant for Singapore MOE PSLE English. It uses the Google Gemini API to analyze student submissions and generate strict, rubric-based feedback as raw LaTeX, then compiles the results into PDF reports.

## Key Files
- `app.py` — main Streamlit application with login, class/student/assignment management, grading workflow, and report generation.
- `database.py` — SQLite persistence layer for classes, students, assignments, and feedback history.
- `gemini_client.py` — Google Gemini API integration with strict PSLE marking instructions and class report prompting.
- `latex_utils.py` — helpers for writing `.tex` files, compiling PDFs with `pdflatex`, and merging PDFs.
- `requirements.txt` — Python dependencies.
- `packages.txt` — Streamlit Cloud system packages for LaTeX and OCR.
- `.streamlit/secrets.toml` — example secret configuration.
- `Procfile` — Streamlit Cloud deployment entrypoint.
- `README.md` — installation and usage notes.
- `.gitignore` — ignores generated artifacts and database files.

## Usage Notes
1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Install required system packages:
   - `tesseract` for OCR
   - `pdflatex` via a TeX distribution
3. Run the app:
   ```bash
   python3 -m streamlit run app.py
   ```

## Status
- Project scaffold is complete
- Python files compile cleanly
- Streamlit is installed and the app was launched successfully via `python3 -m streamlit`
- External binaries are still required for full PDF and OCR support

## Notes
- Save teacher PIN and Gemini API key in `.streamlit/secrets.toml` or Streamlit secrets.
- The app stores feedback history in `marking_assistant.db`.
