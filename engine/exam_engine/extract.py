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
from typing import Dict, List, Optional, Tuple

from .models import Document, Figure, Problem

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


def problem_positions(pdf_path: Path) -> Dict[int, List[Tuple[int, float]]]:
    """Map each page to ``(problem_number, y_top)`` for every problem header.

    Used to decide which problem a detected figure belongs to.
    """
    fitz = _require_fitz()
    positions: Dict[int, List[Tuple[int, float]]] = {}
    with fitz.open(pdf_path) as doc:
        for page_no, page in enumerate(doc, start=1):
            data = page.get_text("dict")
            for block in data.get("blocks", []):
                for line in block.get("lines", []):
                    text = "".join(span.get("text", "") for span in line.get("spans", []))
                    match = _PROBLEM_RE.match(text)
                    if match:
                        y_top = float(line.get("bbox", [0, 0, 0, 0])[1])
                        positions.setdefault(page_no, []).append((int(match.group(1)), y_top))
    return positions


def detect_figures(pdf_path: Path, work_dir: Path) -> Dict[int, List[Tuple[float, Figure]]]:
    """Extract embedded raster images per page as ``(y_top, Figure)`` pairs."""
    fitz = _require_fitz()
    fig_dir = Path(work_dir) / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    by_page: Dict[int, List[Tuple[float, Figure]]] = {}

    with fitz.open(pdf_path) as doc:
        for page_no, page in enumerate(doc, start=1):
            pw = float(page.rect.width) or 1.0
            ph = float(page.rect.height) or 1.0
            for idx, info in enumerate(page.get_images(full=True)):
                xref = info[0]
                try:
                    rects = page.get_image_rects(xref)
                    rect = rects[0] if rects else None
                except Exception:
                    rect = None

                # Skip header banners, full-page scans, thin rules, and tiny icons,
                # which are not real problem figures.
                if rect is not None and not _is_real_figure(rect, pw, ph):
                    continue

                try:
                    base = doc.extract_image(xref)
                except Exception:
                    continue
                ext = base.get("ext", "png")
                fid = f"p{page_no}_img{idx}"
                fname = f"{fid}.{ext}"
                (fig_dir / fname).write_bytes(base["image"])

                figure = Figure(
                    id=fid,
                    path=f"figures/{fname}",
                    page=page_no,
                    width=int(base.get("width", 0)),
                    height=int(base.get("height", 0)),
                )
                by_page.setdefault(page_no, []).append((float(rect.y0) if rect else 0.0, figure))
    return by_page


def _is_real_figure(rect, page_w: float, page_h: float) -> bool:
    """Heuristic: keep diagram-sized images, drop headers/banners/full-page scans."""
    w, h = float(rect.width), float(rect.height)
    if w < 28 or h < 28:
        return False  # icon / bullet
    rel_w = w / page_w
    rel_h = h / page_h
    top_frac = float(rect.y0) / page_h
    aspect = w / max(h, 1.0)
    if rel_w >= 0.92 and rel_h >= 0.85:
        return False  # whole-page scan
    if rel_w >= 0.85 and top_frac < 0.18:
        return False  # full-width header banner near the top
    if aspect >= 4.0 or aspect <= 0.18:
        return False  # thin rule / sidebar
    return True


def _cluster_rects(rects, gap: float = 16.0):
    """Merge rects whose padded bounding boxes touch, into figure-region clusters."""
    boxes = [[float(r.x0), float(r.y0), float(r.x1), float(r.y1)] for r in rects]

    def touch(a, b) -> bool:
        return not (a[2] + gap < b[0] or b[2] + gap < a[0] or
                    a[3] + gap < b[1] or b[3] + gap < a[1])

    merged = True
    while merged:
        merged = False
        out: List[list] = []
        used = [False] * len(boxes)
        for i in range(len(boxes)):
            if used[i]:
                continue
            a = boxes[i][:]
            for j in range(i + 1, len(boxes)):
                if used[j]:
                    continue
                if touch(a, boxes[j]):
                    b = boxes[j]
                    a = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]
                    used[j] = True
                    merged = True
            used[i] = True
            out.append(a)
        boxes = out
    return boxes


def _is_vector_figure(box, page_w: float, page_h: float, member_count: int) -> bool:
    """Decide if a cluster of vector strokes is a real figure (not a box/table/rule)."""
    w, h = box[2] - box[0], box[3] - box[1]
    if w < 35 or h < 35:
        return False  # too small (answer box, single mark)
    rel_w, rel_h = w / page_w, h / page_h
    top_frac = box[1] / page_h
    aspect = w / max(h, 1.0)
    if rel_w >= 0.85 and top_frac < 0.18:
        return False  # header table band
    if rel_w >= 0.9 and rel_h >= 0.8:
        return False  # full-page frame
    if aspect >= 5.0 or aspect <= 0.2:
        return False  # rule / thin strip
    if member_count < 3:
        return False  # a lone rectangle (choice box) — not a diagram
    return True


def detect_vector_figures(pdf_path: Path, work_dir: Path, dpi: int = 200, max_per_page: int = 8):
    """Find vector-drawn diagrams/graphs and crop them from the rendered page.

    Exam figures are usually vector strokes (not embedded images), so
    ``get_images`` misses them. We cluster the page's drawing paths into regions,
    keep diagram-shaped clusters, and render each region to a PNG crop.
    """
    fitz = _require_fitz()
    fig_dir = Path(work_dir) / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    by_page: Dict[int, List[Tuple[float, Figure]]] = {}
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    with fitz.open(pdf_path) as doc:
        for page_no, page in enumerate(doc, start=1):
            pw = float(page.rect.width) or 1.0
            ph = float(page.rect.height) or 1.0
            try:
                rects = [d["rect"] for d in page.get_drawings() if d.get("rect")]
            except Exception:
                continue
            # Keep thin line strokes (a line has ~0 width or height) — we filter
            # by the *cluster* size later, not the individual stroke.
            rects = [r for r in rects if float(r.width) > 1 or float(r.height) > 1]
            if not rects:
                continue
            clusters = _cluster_rects(rects)
            kept = 0
            for idx, box in enumerate(clusters):
                members = sum(
                    1 for r in rects
                    if r.x0 >= box[0] - 1 and r.y0 >= box[1] - 1
                    and r.x1 <= box[2] + 1 and r.y1 <= box[3] + 1
                )
                if not _is_vector_figure(box, pw, ph, members):
                    continue
                if kept >= max_per_page:
                    break
                clip = fitz.Rect(box[0], box[1], box[2], box[3])
                try:
                    cpix = page.get_pixmap(matrix=matrix, clip=clip)
                except Exception:
                    continue
                fid = f"p{page_no}_vec{idx}"
                fname = f"{fid}.png"
                cpix.save(str(fig_dir / fname))
                figure = Figure(id=fid, path=f"figures/{fname}", page=page_no,
                                width=cpix.width, height=cpix.height)
                by_page.setdefault(page_no, []).append((float(box[1]), figure))
                kept += 1
    return by_page


def _merge_page_figs(*sources):
    out: Dict[int, List[Tuple[float, Figure]]] = {}
    for src in sources:
        for page_no, figs in src.items():
            out.setdefault(page_no, []).extend(figs)
    return out


def assign_figures(problems: List[Problem], pdf_path: Path, work_dir: Path) -> int:
    """Attach detected figures (raster + vector) to the problem they appear under."""
    positions = problem_positions(pdf_path)
    raster = detect_figures(pdf_path, work_dir)
    try:
        vector = detect_vector_figures(pdf_path, work_dir)
    except Exception:
        vector = {}
    figures_by_page = _merge_page_figs(raster, vector)
    by_number = {p.number: p for p in problems}
    assigned = 0

    for page_no, figures in figures_by_page.items():
        headers = sorted(positions.get(page_no, []), key=lambda h: h[1])
        for y_top, figure in figures:
            # The owning problem is the last header whose top is above the figure.
            owner_number: Optional[int] = None
            for number, header_y in headers:
                if header_y <= y_top:
                    owner_number = number
                else:
                    break
            if owner_number is None and headers:
                owner_number = headers[0][0]
            target = by_number.get(owner_number) if owner_number is not None else None
            if target is None and problems:
                target = problems[-1]  # fall back to the last problem on the page
            if target is not None:
                target.figures.append(figure)
                assigned += 1
    return assigned


def extract(
    pdf_path: Path,
    work_dir: Path,
    dpi: int = 200,
    render: bool = True,
    detect: bool = True,
) -> Document:
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
    if detect:
        try:
            assign_figures(problems, pdf_path, work_dir)
        except Exception:
            pass  # figure detection is best-effort
    title = pdf_path.stem or "Exam"
    return Document(title=title, source=str(pdf_path), problems=problems)


def extract_with_vision(
    pdf_path: Path,
    work_dir: Path,
    ai_client,
    dpi: int = 200,
    log=lambda _m: None,
) -> Document:
    """Extract problems by sending each rendered page image to Claude vision.

    Math and figure-laden problems that plain text extraction garbles are read
    accurately here. Figures are still detected/attached via PyMuPDF.
    """
    pdf_path = Path(pdf_path)
    work_dir = Path(work_dir)
    images = render_pages(pdf_path, work_dir / "pages", dpi=dpi)

    problems: List[Problem] = []
    for page_no, img_path in enumerate(images, start=1):
        log(f"  비전 분석 {page_no}/{len(images)} 페이지...")
        try:
            page_problems = ai_client.extract_problems_from_image(img_path.read_bytes(), "image/png")
        except Exception as exc:
            log(f"  (페이지 {page_no} 비전 실패: {exc} — 건너뜀)")
            page_problems = []
        for p in page_problems:
            p.page = page_no
            problems.append(p)

    # If the model didn't number problems, assign sequential numbers.
    if problems and all(p.number == 0 for p in problems):
        for i, p in enumerate(problems, start=1):
            p.number = i

    document = Document(title=pdf_path.stem or "Exam", source=str(pdf_path), problems=problems)
    try:
        assign_figures(problems, pdf_path, work_dir)
    except Exception:
        pass
    return document


__all__ = [
    "extract",
    "extract_with_vision",
    "extract_text_pages",
    "render_pages",
    "split_problems",
    "detect_figures",
    "detect_vector_figures",
    "problem_positions",
    "assign_figures",
]
