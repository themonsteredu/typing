"""Tests for crop mode — per-problem bounding boxes cropped into the document."""

from pathlib import Path

import pytest

from exam_engine import settings as settings_mod
from exam_engine.settings import Settings
from exam_engine.extract import _clamp_bbox, extract_with_crop
from exam_engine.hwpx import build
from exam_engine.models import Document, Figure, Problem


# --- settings round-trip ---
def test_settings_crop_roundtrip(tmp_path, monkeypatch):
    target = tmp_path / "settings.json"
    monkeypatch.setenv("EXAM_STUDIO_SETTINGS", str(target))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    assert Settings.from_dict({}).crop_mode is False  # default off

    cfg = Settings.from_dict({})
    cfg.crop_mode = True
    settings_mod.save(cfg)

    assert settings_mod.load().crop_mode is True
    assert cfg.to_dict()["cropMode"] is True


# --- bbox clamping ---
def test_clamp_bbox_clamps_and_drops():
    # normal box gets padded then clamped to bounds
    assert _clamp_bbox([10, 20, 100, 200], 300, 400) == (4, 14, 106, 206)
    # inverted coords are normalized
    assert _clamp_bbox([100, 200, 10, 20], 300, 400) == (4, 14, 106, 206)
    # out-of-bounds is clamped to the image
    assert _clamp_bbox([-50, -50, 999, 999], 300, 400) == (0, 0, 300, 400)
    # degenerate (zero-area) box is dropped
    assert _clamp_bbox([50, 50, 50, 50], 300, 400) is None
    # malformed input is dropped
    assert _clamp_bbox([1, 2, 3], 300, 400) is None


# --- extraction produces crop figures ---
class _StubClient:
    """Stands in for AIClient — returns one box per page, no network."""

    def locate_problems_in_image(self, image_bytes, media_type="image/png"):
        return [{"number": 1, "bbox": [10, 10, 120, 160]}]


def test_extract_with_crop_makes_figures(tmp_path):
    fitz = pytest.importorskip("fitz")

    pdf = tmp_path / "c.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "1. 다음을 계산하시오.")
    doc.save(str(pdf))
    doc.close()

    work = tmp_path / "work"
    document = extract_with_crop(pdf, work, _StubClient(), dpi=150)

    assert len(document.problems) == 1
    problem = document.problems[0]
    assert len(problem.figures) == 1
    assert problem.text == ""
    crop_file = work / problem.figures[0].path
    assert crop_file.exists()
    assert problem.figures[0].path.startswith("crops/")


# --- a crop-only problem (empty text + one figure) builds cleanly ---
def test_build_crop_problem_renders(tmp_path):
    pytest.importorskip("pyhwpxlib")
    from PIL import Image

    assets = tmp_path / "assets"
    (assets / "crops").mkdir(parents=True)
    img = assets / "crops" / "p1_q1.png"
    Image.new("RGB", (120, 90), "white").save(img)

    doc = Document(title="수학", source="x.pdf", problems=[
        Problem(number=1, page=1, text="", choices=[],
                figures=[Figure(id="p1_q1", path="crops/p1_q1.png", page=1,
                                width=120, height=90)]),
    ])
    out = tmp_path / "e.hwpx"
    build(doc, out, assets_dir=assets)

    assert out.exists()
    html = out.with_suffix(".html").read_text(encoding="utf-8")
    assert "<img" in html
