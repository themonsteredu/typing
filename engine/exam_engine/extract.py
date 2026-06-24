"""Stage 1 — extract problems from a PDF.

Uses PyMuPDF (``fitz``) to pull text (and optionally render page images). The raw
text is split into individual problems with a heuristic tuned for Korean math
exams: a problem starts at a line beginning with ``<n>.`` / ``<n>)`` and choices
are marked with the circled digits ①②③④⑤.

An optional AI pass (see :mod:`exam_engine.ai`) can clean up / re-segment the
problems, but the heuristic alone produces a usable document offline.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

from .models import Document, Problem

# "1.", "12.", "3)", "10 )" at the start of a line.
_PROBLEM_RE = re.compile(r"^\s*(\d{1,3})\s*[.)]\s+(.*)$")
# Circled digits used for multiple-choice options in Korean exams.
_CHOICE_MARKS = "①②③④⑤⑥⑦⑧⑨⑩"
_CHOICE_RE = re.compile(rf"([{_CHOICE_MARKS}])\s*([^{_CHOICE_MARKS}]*)")


def _require_fitz():
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:  # pragma: no cover - exercised only without dep
        raise RuntimeError(
            "PyMuPDF is required for PDF extraction. Install it with "
            "`pip install -r requirements.txt`."
        ) from exc
    return fitz


def extract_text_pages(pdf_path: Path) -> List[str]:
    """Return the plain text of each page."""
    fitz = _require_fitz()
    pages: List[str] = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            pages.append(page.get_text("text"))
    return pages


def render_pages(pdf_path: Path, out_dir: Path, dpi: int = 200) -> List[Path]:
    """Render each page to a PNG (used for figure cropping / preview)."""
    fitz = _require_fitz()
    out_dir.mkdir(parents=True, exist_ok=True)
    images: List[Path] = []
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=matrix)
            target = out_dir / f"page-{i + 1:03d}.png"
            pix.save(target)
            images.append(target)
    return images


def split_problems(pages: List[str]) -> List[Problem]:
    """Segment the concatenated page text into individual problems."""
    problems: List[Problem] = []
    current: Optional[Problem] = None
    buffer: List[str] = []

    def flush():
        if current is not None:
            body = "\n".join(buffer).strip()
            text, choices = _split_choices(body)
            current.text = text
            current.choices = choices
            problems.append(current)

    for page_no, page_text in enumerate(pages, start=1):
        for raw_line in page_text.splitlines():
            line = raw_line.rstrip()
            match = _PROBLEM_RE.match(line)
            if match:
                flush()
                number = int(match.group(1))
                current = Problem(number=number, page=page_no, text="")
                buffer = [match.group(2)]
            elif current is not None:
                buffer.append(line)
    flush()
    return problems


def _split_choices(body: str) -> tuple[str, List[str]]:
    """Separate the stem from any circled-digit multiple-choice options."""
    idx = next((body.find(m) for m in _CHOICE_MARKS if m in body), -1)
    if idx == -1:
        return body.strip(), []
    stem = body[:idx].strip()
    choice_blob = body[idx:].replace("\n", " ")
    choices = [c.strip() for _, c in _CHOICE_RE.findall(choice_blob) if c.strip()]
    return stem, choices


def extract(pdf_path: Path, work_dir: Path, dpi: int = 200, render: bool = True) -> Document:
    """Run the full extraction stage and return a :class:`Document`."""
    pdf_path = Path(pdf_path)
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    pages = extract_text_pages(pdf_path)
    if render:
        try:
            render_pages(pdf_path, work_dir / "pages", dpi=dpi)
        except Exception:
            # Rendering is best-effort; text extraction is the source of truth.
            pass

    problems = split_problems(pages)
    title = pdf_path.stem or "Exam"
    return Document(title=title, source=str(pdf_path), problems=problems)


__all__ = ["extract", "extract_text_pages", "render_pages", "split_problems"]
