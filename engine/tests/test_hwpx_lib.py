"""Tests for the default (pyhwpxlib-backed) build() — produces Hancom-openable HWPX."""

import zipfile
from pathlib import Path

import pytest

from exam_engine.hwpx import build
from exam_engine.models import Document, Figure, Problem


def _doc() -> Document:
    return Document(
        title="2026 수학 모의고사",
        source="exam.pdf",
        problems=[
            Problem(
                number=1,
                page=1,
                text="2 + 3 × 4 의 값은?",
                choices=["12", "14", "20", "24", "26"],
                solution="3×4=12, 2+12=14\n정답: 14",
            ),
            Problem(number=2, page=1, text="함수 f(x)=x^2 의 도함수를 구하시오.", solution="f'(x)=2x"),
        ],
    )


def test_build_default_backend_is_valid_zip(tmp_path: Path):
    pytest.importorskip("pyhwpxlib")
    out = tmp_path / "exam.hwpx"
    build(_doc(), out)
    assert out.exists()
    assert zipfile.is_zipfile(out)
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
    # mimetype first + the OWPML core parts the library emits.
    assert names[0] == "mimetype"
    assert "Contents/section0.xml" in names
    assert "Contents/header.xml" in names
    assert "Contents/content.hpf" in names


def test_build_contains_text_and_writes_preview(tmp_path: Path):
    pytest.importorskip("pyhwpxlib")
    out = tmp_path / "exam.hwpx"
    build(_doc(), out)
    with zipfile.ZipFile(out) as zf:
        section = zf.read("Contents/section0.xml").decode("utf-8")
    assert "도함수" in section
    assert "정답: 14" in section
    # Always-correct HTML preview written alongside.
    assert out.with_suffix(".html").exists()


def test_build_embeds_figure_image(tmp_path: Path):
    pytest.importorskip("pyhwpxlib")
    Image = pytest.importorskip("PIL.Image")
    assets = tmp_path / "work"
    (assets / "figures").mkdir(parents=True)
    Image.new("RGB", (60, 40), (10, 100, 200)).save(assets / "figures" / "p1_img0.png")

    doc = Document(
        title="도형",
        source="x.pdf",
        problems=[
            Problem(
                number=1, page=1, text="그림을 보시오.",
                figures=[Figure(id="p1_img0", path="figures/p1_img0.png", page=1, width=60, height=40)],
            )
        ],
    )
    out = tmp_path / "fig.hwpx"
    build(doc, out, assets_dir=assets)
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
    # The library stores embedded images under BinData/.
    assert any(n.startswith("BinData/") for n in names), names
