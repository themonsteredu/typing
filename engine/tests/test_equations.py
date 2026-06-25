import zipfile
from pathlib import Path

import pytest

from exam_engine.hwpx import build, _split_eq, _strip_markers
from exam_engine.extract import _is_real_figure
from exam_engine.models import Document, Problem


class _Rect:
    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1
        self.width, self.height = x1 - x0, y1 - y0


# --- equations ---
def test_split_eq_mixed():
    segs = _split_eq("값은 [[eq]]{1} over {2}[[/eq]] 입니다")
    kinds = [k for k, _ in segs]
    assert kinds == ["text", "eq", "text"]
    assert segs[1][1] == "{1} over {2}"


def test_strip_markers():
    assert _strip_markers("a [[eq]]x^2[[/eq]] b") == "a x^2 b"


def test_build_emits_equation_objects(tmp_path: Path):
    pytest.importorskip("pyhwpxlib")
    doc = Document(title="수학", source="x.pdf", problems=[
        Problem(number=1, page=1, text="간단히 [[eq]]{x^2-1} over {x-1}[[/eq]]",
                choices=[], solution="정답: [[eq]]x+1[[/eq]]"),
    ])
    out = tmp_path / "e.hwpx"
    build(doc, out)
    sec = zipfile.ZipFile(out).read("Contents/section0.xml").decode()
    assert sec.count("<hp:equation") == 2
    # markers never leak into the body or preview
    assert "[[eq]]" not in sec
    assert "[[eq]]" not in out.with_suffix(".html").read_text(encoding="utf-8")


# --- figure filtering ---
def test_figure_filter_drops_header_banner():
    assert _is_real_figure(_Rect(30, 20, 560, 70), 595, 842) is False


def test_figure_filter_drops_full_page():
    assert _is_real_figure(_Rect(10, 10, 585, 835), 595, 842) is False


def test_figure_filter_keeps_diagram():
    assert _is_real_figure(_Rect(80, 300, 260, 460), 595, 842) is True


def test_figure_filter_drops_tiny_and_thin():
    assert _is_real_figure(_Rect(80, 300, 95, 315), 595, 842) is False  # tiny
    assert _is_real_figure(_Rect(40, 400, 560, 430), 595, 842) is False  # thin rule
