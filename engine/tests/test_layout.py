import zipfile
from pathlib import Path

import pytest

from exam_engine.hwpx import build
from exam_engine.models import Document, Problem


def _doc() -> Document:
    return Document(
        title="시험",
        source="x.pdf",
        problems=[Problem(number=1, page=1, text="문제", solution="풀이\n정답: 1")],
    )


def test_single_column_default(tmp_path: Path):
    pytest.importorskip("pyhwpxlib")
    out = tmp_path / "a.hwpx"
    build(_doc(), out)  # columns defaults to 1
    sec = zipfile.ZipFile(out).read("Contents/section0.xml").decode()
    assert 'colCount="1"' in sec


def test_two_column_sets_colcount(tmp_path: Path):
    pytest.importorskip("pyhwpxlib")
    out = tmp_path / "b.hwpx"
    build(_doc(), out, columns=2)
    with zipfile.ZipFile(out) as zf:
        assert zf.infolist()[0].filename == "mimetype"  # still valid container
        sec = zf.read("Contents/section0.xml").decode()
    assert 'colCount="2"' in sec
    # HTML preview reflects columns too
    assert "column-count:2" in out.with_suffix(".html").read_text(encoding="utf-8")


def test_solutions_included_vs_skipped(tmp_path):
    # build always includes whatever solution the problem carries; the *skip*
    # happens in the pipeline (run_generate is not called). Simulate both.
    from exam_engine.hwpx import _build_legacy

    with_sol = tmp_path / "w.hwpx"
    _build_legacy(_doc(), with_sol)
    assert "정답: 1" in zipfile.ZipFile(with_sol).read("Contents/section0.xml").decode()

    no_sol_doc = Document(title="시험", source="x.pdf",
                          problems=[Problem(number=1, page=1, text="문제", solution="")])
    without = tmp_path / "n.hwpx"
    _build_legacy(no_sol_doc, without)
    assert "[풀이]" not in zipfile.ZipFile(without).read("Contents/section0.xml").decode()
