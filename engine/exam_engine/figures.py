"""Stage 3 — figure processing.

Optimizes rendered page images (downscale + recompress) so the assembled
document stays small. Figure *detection* (cropping diagrams out of pages) is a
deeper task; this MVP normalizes the rendered previews and is the seam where a
detector/AI figure engine would plug in.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from .models import Document


def process(document: Document, work_dir: Path, max_width: int = 1600) -> Document:
    work_dir = Path(work_dir)
    pages_dir = work_dir / "pages"
    if not pages_dir.exists():
        return document

    try:
        from PIL import Image
    except ImportError:
        return document  # Pillow optional; skip optimization gracefully

    for img_path in sorted(pages_dir.glob("*.png")):
        try:
            with Image.open(img_path) as im:
                if im.width > max_width:
                    ratio = max_width / im.width
                    im = im.resize((max_width, int(im.height * ratio)))
                im.save(img_path, optimize=True)
        except Exception:
            continue
    return document


__all__ = ["process"]
