import subprocess
from pathlib import Path
from typing import List

import requests
from pypdf import PdfReader, PdfWriter

BASE_LATEX_HEADER = r"""
\documentclass[11pt]{article}
\usepackage[svgnames]{xcolor}
\usepackage{tcolorbox}
\usepackage{geometry}
\usepackage{amssymb}
\usepackage{hyperref}
\geometry{margin=1in}
\tcbset{enhanced,boxrule=0.5pt,sharp corners,arc=2mm}
\begin{document}
"""

BASE_LATEX_FOOTER = r"""
\end{document}
"""


def write_tex_file(path: Path, latex_text: str) -> None:
    content = latex_text.strip()
    if not content.startswith("\\documentclass"):
        content = f"{BASE_LATEX_HEADER}\n{content}\n{BASE_LATEX_FOOTER}"
    path.write_text(content, encoding="utf-8")


def compile_latex(tex_path: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    compile_args = [
        "pdflatex",
        "-interaction=nonstopmode",
        "-halt-on-error",
        f"-output-directory={output_dir}",
        str(tex_path),
    ]
    try:
        process = subprocess.run(compile_args, capture_output=True, text=True)
    except FileNotFoundError:
        raise RuntimeError(
            "pdflatex was not found. Install a TeX distribution such as texlive or MacTeX before running the app."
        )
    if process.returncode != 0:
        raise RuntimeError(
            f"LaTeX compilation failed with return code {process.returncode}.\n"
            f"Stdout:\n{process.stdout}\n\nStderr:\n{process.stderr}"
        )
    pdf_path = output_dir / tex_path.with_suffix(".pdf").name
    if not pdf_path.exists():
        raise RuntimeError("LaTeX compilation completed but the PDF file was not generated.")
    return pdf_path


def compile_latex_online(tex_path: Path, output_dir: Path) -> Path:
    """Fallback: compile LaTeX via a free online API when pdflatex is unavailable."""
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / tex_path.with_suffix(".pdf").name

    with open(tex_path, "rb") as f:
        response = requests.post(
            "https://latexonline.cc/compile",
            files={"file": (tex_path.name, f, "application/x-tex")},
            timeout=60,
        )

    if response.status_code != 200:
        raise RuntimeError(
            f"Online LaTeX compilation failed (HTTP {response.status_code}). "
            f"Response: {response.text[:500]}"
        )

    pdf_path.write_bytes(response.content)
    if not pdf_path.exists() or pdf_path.stat().st_size < 100:
        raise RuntimeError("Online LaTeX compilation returned an empty or invalid PDF.")

    return pdf_path


def merge_pdfs(paths: List[str], output_path: Path) -> None:
    writer = PdfWriter()
    for pdf_path in paths:
        reader = PdfReader(str(pdf_path))
        for page in reader.pages:
            writer.add_page(page)
    with output_path.open("wb") as output_file:
        writer.write(output_file)
