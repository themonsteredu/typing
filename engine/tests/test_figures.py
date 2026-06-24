import zipfile
from pathlib import Path

import pytest

from exam_engine.hwpx import build
from exam_engine.models import Document, Figure, Problem


def _doc_with_figure(fig_rel: str) -> Document:
    return Document(
        title="도형 시험",
        source="exam.pdf",
        problems=[
            Problem(
                number=1,
                page=1,
                text="아래 그림을 보고 넓이를 구하시오.",
                solution="넓이는 24",
                figures=[Figure(id="p1_img0", path=fig_rel, page=1, width=60, height=40)],
            )
        ],
    )


def _write_png(path: Path) -> None:
    # 1x1 red PNG (valid minimal image) so we don't depend on Pillow here.
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
        "53de0000000c4944415408d763f8cfc0f01f0005000196c9b1f80000000049"
        "454e44ae426082"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def test_figure_embedded_as_bindata(tmp_path: Path):
    assets = tmp_path / "work"
    _write_png(assets / "figures" / "p1_img0.png")
    out = tmp_path / "exam.hwpx"

    build(_doc_with_figure("figures/p1_img0.png"), out, assets_dir=assets)

    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        assert "BinData/image1.png" in names
        header = zf.read("Contents/header.xml").decode("utf-8")
        content = zf.read("Contents/content.hpf").decode("utf-8")
        manifest = zf.read("META-INF/manifest.xml").decode("utf-8")
    assert '<hh:binDataList itemCnt="1">' in header
    assert 'href="BinData/image1.png"' in content and 'isEmbeded="1"' in content
    assert 'odf:full-path="BinData/image1.png"' in manifest


def test_no_assets_dir_skips_figures(tmp_path: Path):
    out = tmp_path / "exam.hwpx"
    build(_doc_with_figure("figures/p1_img0.png"), out)  # no assets_dir
    with zipfile.ZipFile(out) as zf:
        assert not any(n.startswith("BinData/") for n in zf.namelist())
        assert '<hh:binDataList' not in zf.read("Contents/header.xml").decode("utf-8")


def test_preview_html_inlines_figure(tmp_path: Path):
    assets = tmp_path / "work"
    _write_png(assets / "figures" / "p1_img0.png")
    out = tmp_path / "exam.hwpx"
    build(_doc_with_figure("figures/p1_img0.png"), out, assets_dir=assets)
    html = out.with_suffix(".html").read_text(encoding="utf-8")
    assert "data:image/png;base64," in html


def test_header_has_richer_reflist(tmp_path: Path):
    out = tmp_path / "exam.hwpx"
    build(_doc_with_figure("missing.png"), out)
    with zipfile.ZipFile(out) as zf:
        header = zf.read("Contents/header.xml").decode("utf-8")
    for tag in ["borderFills", "tabProperties", "numberings", "bullets", "fontfaces"]:
        assert tag in header, f"header missing {tag}"
    assert header.count("<hh:fontface ") == 7  # one per language slot


# --- end-to-end detection from a real PDF (needs PyMuPDF) ---
def test_detect_and_assign_from_pdf(tmp_path: Path):
    fitz = pytest.importorskip("fitz")
    Image = pytest.importorskip("PIL.Image")
    from exam_engine import extract as extract_stage

    img = tmp_path / "fig.png"
    Image.new("RGB", (80, 50), (200, 40, 40)).save(img)
    pdf = tmp_path / "exam.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "1. first problem")
    page.insert_image(fitz.Rect(72, 100, 172, 180), filename=str(img))
    page.insert_text((72, 240), "2. second problem")
    doc.save(str(pdf))
    doc.close()

    work = tmp_path / "work"
    document = extract_stage.extract(pdf, work, render=False)
    figures = [f for p in document.problems for f in p.figures]
    assert len(figures) >= 1
    # The image sits under problem 1, so it should attach there.
    p1 = next(p for p in document.problems if p.number == 1)
    assert len(p1.figures) >= 1
