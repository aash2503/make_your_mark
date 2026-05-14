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
    """Fallback: compile LaTeX via free online APIs when pdflatex is unavailable."""
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / tex_path.with_suffix(".pdf").name

    with open(tex_path, "rb") as f:
        tex_data = f.read()

    # Try multiple endpoints
    endpoints = [
        ("https://latexonline.cc/data", {"file": (tex_path.name, tex_data, "application/x-tex")}),
        ("https://texlive.net/compile", {"file": (tex_path.name, tex_data, "application/x-tex")}),
    ]

    last_error = None
    for url, files in endpoints:
        try:
            response = requests.post(url, files=files, timeout=90)
            if response.status_code == 200 and len(response.content) > 100:
                pdf_path.write_bytes(response.content)
                return pdf_path
            last_error = f"HTTP {response.status_code}: {response.text[:200]}"
        except Exception as exc:
            last_error = str(exc)

    raise RuntimeError(
        f"All online LaTeX compilers failed. Last error: {last_error}. "
        f"Copy the LaTeX source to Overleaf (https://overleaf.com) or install texlive."
    )


def merge_pdfs(paths: List[str], output_path: Path) -> None:
    writer = PdfWriter()
    for pdf_path in paths:
        reader = PdfReader(str(pdf_path))
        for page in reader.pages:
            writer.add_page(page)
    with output_path.open("wb") as output_file:
        writer.write(output_file)
