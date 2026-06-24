import zipfile
from pathlib import Path

from exam_engine.hwpx import build, MIMETYPE
from exam_engine.models import Document, Problem


def _sample_doc() -> Document:
    return Document(
        title="2026 모의고사 수학",
        source="exam.pdf",
        problems=[
            Problem(
                number=1,
                page=1,
                text="다음 식의 값을 구하시오. 2 + 3 × 4",
                choices=["12", "14", "20", "24", "26"],
                solution="3 × 4 = 12, 2 + 12 = 14\n정답: 14",
            ),
            Problem(number=2, page=1, text="함수 f(x)=x^2 의 도함수를 구하시오.", solution="f'(x)=2x"),
        ],
    )


def test_build_produces_valid_zip(tmp_path: Path):
    out = tmp_path / "exam.hwpx"
    result = build(_sample_doc(), out)
    assert result.exists()
    assert zipfile.is_zipfile(result)


def test_mimetype_is_first_and_stored(tmp_path: Path):
    out = tmp_path / "exam.hwpx"
    build(_sample_doc(), out)
    with zipfile.ZipFile(out) as zf:
        infos = zf.infolist()
        assert infos[0].filename == "mimetype"
        assert infos[0].compress_type == zipfile.ZIP_STORED
        assert zf.read("mimetype").decode() == MIMETYPE


def test_contains_required_entries(tmp_path: Path):
    out = tmp_path / "exam.hwpx"
    build(_sample_doc(), out)
    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
    for required in [
        "mimetype",
        "version.xml",
        "settings.xml",
        "Contents/content.hpf",
        "Contents/header.xml",
        "Contents/section0.xml",
        "Preview/PrvText.txt",
        "META-INF/container.xml",
        "META-INF/manifest.xml",
    ]:
        assert required in names, f"missing {required}"


def test_body_contains_problem_text(tmp_path: Path):
    out = tmp_path / "exam.hwpx"
    build(_sample_doc(), out)
    with zipfile.ZipFile(out) as zf:
        section = zf.read("Contents/section0.xml").decode("utf-8")
        preview = zf.read("Preview/PrvText.txt").decode("utf-8")
    assert "도함수" in section
    assert "정답: 14" in section
    assert "2026 모의고사 수학" in preview


def test_section_xml_is_well_formed(tmp_path: Path):
    import xml.dom.minidom as minidom

    out = tmp_path / "exam.hwpx"
    build(_sample_doc(), out)
    with zipfile.ZipFile(out) as zf:
        for entry in ["Contents/section0.xml", "Contents/header.xml", "Contents/content.hpf"]:
            minidom.parseString(zf.read(entry))  # raises if malformed


def test_preview_html_written(tmp_path: Path):
    out = tmp_path / "exam.hwpx"
    build(_sample_doc(), out)
    html = out.with_suffix(".html")
    assert html.exists()
    assert "2026 모의고사 수학" in html.read_text(encoding="utf-8")
