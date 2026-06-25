"""Stage 4 — assemble a :class:`Document` into an HWPX file.

HWPX is Hancom Office's open document format: a ZIP container holding OWPML XML
(``http://www.hancom.co.kr/hwpml/2011/*`` namespaces), structured like ODF/OOXML.

This writer emits the documented HWPX container layout::

    mimetype                 (stored uncompressed, first entry)
    version.xml
    settings.xml
    Contents/content.hpf     (package manifest / spine)
    Contents/header.xml      (fonts, borders, char/para properties, bin-data list)
    Contents/section0.xml    (the body paragraphs)
    BinData/imageN.<ext>     (embedded figures, if any)
    Preview/PrvText.txt
    META-INF/container.xml
    META-INF/manifest.xml

It targets the published OWPML structure and is best-effort with respect to a
specific Hancom build; an always-correct ``preview.html`` (with figures rendered
inline) is written alongside the ``.hwpx`` so results are verifiable without
Hancom installed.

Detected figures are embedded as registered ``BinData`` items and marked in the
body with a placeholder line; inline picture *placement* is intentionally left
out of the section XML so the document stays in the known-openable family.
"""

from __future__ import annotations

import base64
import html
import mimetypes
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
from xml.sax.saxutils import escape as xml_escape

from .models import Document, Figure

# Equations the AI marks like [[eq]]{1} over {2}[[/eq]] become real 한글 수식 objects.
_EQ_RE = re.compile(r"\[\[eq\]\](.*?)\[\[/eq\]\]", re.DOTALL)


def _strip_markers(s: str) -> str:
    return (s or "").replace("[[eq]]", "").replace("[[/eq]]", "")


def _split_eq(line: str) -> List[Tuple[str, str]]:
    """Split a line into ('text', s) / ('eq', script) segments."""
    out: List[Tuple[str, str]] = []
    pos = 0
    for m in _EQ_RE.finditer(line):
        if line[pos:m.start()]:
            out.append(("text", line[pos:m.start()]))
        out.append(("eq", m.group(1)))
        pos = m.end()
    if line[pos:]:
        out.append(("text", line[pos:]))
    return out


def _add_rich_line(builder, line: str) -> None:
    """Add a line, rendering [[eq]] segments as 한글 수식 objects (block-level)."""
    if "[[eq]]" not in line:
        if line.strip() or line == "":
            builder.add_paragraph(line)
        return
    for kind, seg in _split_eq(line):
        seg = seg.strip()
        if not seg:
            continue
        if kind == "eq":
            try:
                builder.add_equation(seg)
            except Exception:
                builder.add_paragraph(seg)  # bad script must not break the doc
        else:
            builder.add_paragraph(seg)

MIMETYPE = "application/hwp+zip"

NS = {
    "head": "http://www.hancom.co.kr/hwpml/2011/head",
    "para": "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "section": "http://www.hancom.co.kr/hwpml/2011/section",
    "core": "http://www.hancom.co.kr/hwpml/2011/core",
}

_LANGS = ["HANGUL", "LATIN", "HANJA", "JAPANESE", "OTHER", "SYMBOL", "USER"]


@dataclass
class _BinItem:
    """An embedded binary (figure) ready to be written into the ZIP."""

    bin_id: int          # 1-based id used across header / manifests
    figure_id: str
    arc_name: str        # e.g. "BinData/image1.png"
    fmt: str             # e.g. "png"
    media_type: str      # e.g. "image/png"
    data: bytes


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def build(document: Document, out_path: Path, assets_dir: Optional[Path] = None,
          columns: int = 1, header: bool = True) -> Path:
    """Write ``document`` to ``out_path`` (an ``.hwpx`` file).

    Prefers the validated ``pyhwpxlib`` backend (produces Hancom-openable files);
    falls back to the built-in writer if the library is unavailable. ``assets_dir``
    is the work directory holding figure files referenced by ``Problem.figures``.
    ``columns`` (1 or 2) lays the body out in newspaper columns like a real exam;
    ``header`` adds a centered title + 이름/학년/날짜 fill-in table. An
    always-correct ``preview.html`` is written alongside either way.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        _build_with_pyhwpxlib(document, out_path, assets_dir, header=header)
        if columns and columns > 1:
            _apply_columns(out_path, columns)
    except Exception:
        # Library missing or failed -> fall back to the built-in writer so a
        # file is always produced (and the HTML preview always renders).
        _build_legacy(document, out_path, assets_dir)

    write_preview_html(document, out_path.with_suffix(".html"), assets_dir, columns, header)
    return out_path


def _apply_columns(out_path: Path, col_count: int, gap: int = 2268) -> None:
    """Set newspaper columns by bumping the section's existing ``hp:colPr``.

    pyhwpxlib already emits a single-column ``<hp:colPr colCount="1" .../>``; we
    rewrite its ``colCount`` (and gap). Best-effort: a no-op if the element isn't
    found, so it can never corrupt an otherwise-valid file. (``gap`` in HWPUNIT.)
    """
    import re

    with zipfile.ZipFile(out_path) as zin:
        infos = zin.infolist()
        contents = {i.filename: zin.read(i.filename) for i in infos}

    sec = contents.get("Contents/section0.xml")
    if not sec:
        return
    text = sec.decode("utf-8")

    def _bump(match: "re.Match[str]") -> str:
        tag = match.group(0)
        tag = re.sub(r'colCount="\d+"', f'colCount="{int(col_count)}"', tag)
        if "sameGap=" in tag:
            tag = re.sub(r'sameGap="\d+"', f'sameGap="{int(gap)}"', tag)
        return tag

    new_text = re.sub(r"<hp:colPr\b[^>]*/>", _bump, text, count=1)
    if new_text == text:
        return
    contents["Contents/section0.xml"] = new_text.encode("utf-8")

    with zipfile.ZipFile(out_path, "w") as zout:
        for info in infos:  # preserve order + per-entry compression (mimetype stays STORED)
            zi = zipfile.ZipInfo(info.filename)
            zi.compress_type = info.compress_type
            zout.writestr(zi, contents[info.filename])


def _build_with_pyhwpxlib(document: Document, out_path: Path, assets_dir: Optional[Path],
                          header: bool = True) -> Path:
    """Build the HWPX with pyhwpxlib (raises ImportError if not installed)."""
    from pyhwpxlib import HwpxBuilder

    builder = HwpxBuilder()

    # --- exam-style header: centered title + a 이름/학년반/날짜 fill-in table ---
    if header:
        try:
            builder.add_heading(document.title or "시험지", level=1, alignment="CENTER")
            builder.add_table(
                [["이름", "", "학년 / 반", "", "날짜", ""]],
                cell_colors={(0, 0): "#EEEEEE", (0, 2): "#EEEEEE", (0, 4): "#EEEEEE"},
                col_widths=[5200, 9000, 6500, 8000, 5200, 8620],
                use_preset=False,
            )
            builder.add_draw_line()  # divider under the header
            builder.add_paragraph("")
        except Exception:
            builder.add_heading(document.title or "시험지", level=1, alignment="CENTER")
    else:
        builder.add_heading(document.title or "Exam", level=1)

    for problem in document.problems:
        _add_rich_line(builder, f"{problem.number}. {problem.text}".strip())
        for i, choice in enumerate(problem.choices):
            mark = "①②③④⑤⑥⑦⑧⑨⑩"[i] if i < 10 else f"({i + 1})"
            _add_rich_line(builder, f"   {mark} {choice}")
        if assets_dir is not None:
            for fig in problem.figures:
                src = Path(assets_dir) / fig.path
                if src.exists():
                    try:
                        builder.add_image(str(src))
                    except Exception:
                        pass  # a bad image must not abort the whole document
        if problem.solution:
            builder.add_paragraph("[풀이]", bold=True)
            for line in problem.solution.splitlines() or [""]:
                if line.strip():
                    _add_rich_line(builder, line)
        builder.add_paragraph("")  # spacer between problems

    builder.save(str(out_path))
    return out_path


def _build_legacy(document: Document, out_path: Path, assets_dir: Optional[Path] = None) -> Path:
    """Built-in fallback HWPX writer (used when pyhwpxlib is unavailable)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    bins = _collect_bins(document, assets_dir)
    paragraphs = _document_paragraphs(document)

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # mimetype MUST be the first entry and stored (uncompressed).
        zf.writestr(_stored("mimetype"), MIMETYPE)
        zf.writestr("version.xml", _version_xml())
        zf.writestr("settings.xml", _settings_xml())
        zf.writestr("Contents/content.hpf", _content_hpf(document, bins))
        zf.writestr("Contents/header.xml", _header_xml(bins))
        zf.writestr("Contents/section0.xml", _section_xml(paragraphs))
        for item in bins:
            zf.writestr(item.arc_name, item.data)
        zf.writestr("Preview/PrvText.txt", _preview_text(document))
        zf.writestr("META-INF/container.xml", _container_xml())
        zf.writestr("META-INF/manifest.xml", _manifest_xml(bins))

    return out_path


def write_preview_html(document: Document, out_path: Path, assets_dir: Optional[Path] = None,
                       columns: int = 1, header: bool = True) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_preview_html(document, assets_dir, columns, header), encoding="utf-8")
    return out_path


# --------------------------------------------------------------------------- #
# Figures / binary data
# --------------------------------------------------------------------------- #
def _collect_bins(document: Document, assets_dir: Optional[Path]) -> List[_BinItem]:
    if assets_dir is None:
        return []
    assets_dir = Path(assets_dir)
    bins: List[_BinItem] = []
    next_id = 1
    for problem in document.problems:
        for figure in problem.figures:
            src = assets_dir / figure.path
            if not src.exists():
                continue
            fmt = (src.suffix.lstrip(".") or "png").lower()
            media = mimetypes.guess_type(src.name)[0] or f"image/{fmt}"
            bins.append(
                _BinItem(
                    bin_id=next_id,
                    figure_id=figure.id,
                    arc_name=f"BinData/image{next_id}.{fmt}",
                    fmt=fmt,
                    media_type=media,
                    data=src.read_bytes(),
                )
            )
            next_id += 1
    return bins


# --------------------------------------------------------------------------- #
# Paragraph model -> OWPML
# --------------------------------------------------------------------------- #
def _document_paragraphs(document: Document) -> List[str]:
    """Flatten a document into a list of plain-text paragraph strings."""
    paras: List[str] = [document.title, ""]
    for p in document.problems:
        paras.append(f"{p.number}. {p.text}".strip())
        for i, choice in enumerate(p.choices):
            mark = "①②③④⑤⑥⑦⑧⑨⑩"[i] if i < 10 else f"({i + 1})"
            paras.append(f"   {mark} {choice}")
        for fig in p.figures:
            paras.append(f"〔그림 {fig.id} ({fig.width}×{fig.height})〕")
        if p.solution:
            paras.append("[풀이]")
            paras.extend(p.solution.splitlines() or [""])
        paras.append("")
    return paras


def _section_xml(paragraphs: List[str]) -> str:
    body = []
    for idx, text in enumerate(paragraphs):
        # The first paragraph of a section carries the page setup (secPr).
        secpr = _sec_pr() if idx == 0 else ""
        run_inner = secpr + (f"<hp:t>{xml_escape(_strip_markers(text))}</hp:t>" if text else "<hp:t></hp:t>")
        body.append(
            f'<hp:p paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="0">{run_inner}</hp:run></hp:p>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<hs:sec xmlns:hs="{NS["section"]}" xmlns:hp="{NS["para"]}" '
        f'xmlns:hc="{NS["core"]}">'
        + "".join(body)
        + "</hs:sec>"
    )


def _sec_pr() -> str:
    # A4 portrait, 1-inch-ish margins, expressed in HWPUNIT (1/7200 inch).
    return (
        '<hp:secPr id="0" textDirection="HORIZONTAL" spaceColumns="1134" '
        'tabStop="8000" outlineShapeIDRef="1" memoShapeIDRef="0" '
        'textVerticalWidthHead="0">'
        '<hp:pagePr landscape="WIDELY" width="59528" height="84188" gutterType="LEFT_ONLY">'
        '<hp:margin header="4252" footer="4252" gutter="0" '
        'left="8504" right="8504" top="5668" bottom="4252"/>'
        '</hp:pagePr>'
        '</hp:secPr>'
    )


# --------------------------------------------------------------------------- #
# header.xml — reference lists (fonts, borders, char/para props, bin data)
# --------------------------------------------------------------------------- #
def _header_xml(bins: List[_BinItem]) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<hh:head xmlns:hh="{NS["head"]}" xmlns:hc="{NS["core"]}" '
        'version="1.31" secCnt="1">'
        '<hh:beginNum page="1" footnote="1" endnote="1" pic="1" tbl="1" equation="1"/>'
        + _bin_data_list(bins)
        + '<hh:refList>'
        + _fontfaces()
        + _border_fills()
        + _char_properties()
        + _tab_properties()
        + '<hh:numberings itemCnt="0"/>'
        + '<hh:bullets itemCnt="0"/>'
        + _para_properties()
        + _styles()
        + '</hh:refList>'
        '</hh:head>'
    )


def _bin_data_list(bins: List[_BinItem]) -> str:
    if not bins:
        return ""
    items = "".join(
        f'<hh:binData id="{b.bin_id}" type="EMBEDDING" format="{b.fmt}" compress="0"/>'
        for b in bins
    )
    return f'<hh:binDataList itemCnt="{len(bins)}">{items}</hh:binDataList>'


def _fontfaces() -> str:
    # Declare the same font for every language slot so charPr fontRefs resolve.
    one = (
        '<hh:font id="0" face="함초롬바탕" type="TTF" isEmbedded="0">'
        '<hh:typeInfo familyType="FCAT_MYUNGJO" weight="50" proportion="0" '
        'contrast="0" strokeVariation="0" armStyle="0" letterform="0" '
        'midline="0" xHeight="0"/>'
        '</hh:font>'
    )
    faces = "".join(
        f'<hh:fontface lang="{lang}" fontCnt="1">{one}</hh:fontface>' for lang in _LANGS
    )
    return f'<hh:fontfaces itemCnt="{len(_LANGS)}">{faces}</hh:fontfaces>'


def _border_fills() -> str:
    def border(direction: str, type_: str = "NONE") -> str:
        return f'<hh:{direction} type="{type_}" width="0.1mm" color="#000000"/>'

    def fill(bid: int) -> str:
        return (
            f'<hh:borderFill id="{bid}" threeD="0" shadow="0" centerLine="NONE" '
            'breakCellSeparateLine="0">'
            '<hh:slash type="NONE" Crooked="0" isCounter="0"/>'
            '<hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
            + border("leftBorder") + border("rightBorder")
            + border("topBorder") + border("bottomBorder")
            + '<hh:diagonal type="SOLID" width="0.1mm" color="#000000"/>'
            '</hh:borderFill>'
        )

    return f'<hh:borderFills itemCnt="2">{fill(1)}{fill(2)}</hh:borderFills>'


def _char_properties() -> str:
    return (
        '<hh:charProperties itemCnt="1">'
        '<hh:charPr id="0" height="1000" textColor="#000000" shadeColor="none" '
        'useFontSpace="0" useKerning="0" symMark="NONE" borderFillIDRef="1">'
        + _per_lang("fontRef", "0") + _per_lang("ratio", "100")
        + _per_lang("spacing", "0") + _per_lang("relSz", "100")
        + _per_lang("offset", "0")
        + '</hh:charPr>'
        '</hh:charProperties>'
    )


def _per_lang(tag: str, value: str) -> str:
    attrs = " ".join(
        f'{name}="{value}"'
        for name in ["hangul", "latin", "hanja", "japanese", "other", "symbol", "user"]
    )
    return f'<hh:{tag} {attrs}/>'


def _tab_properties() -> str:
    return (
        '<hh:tabProperties itemCnt="1">'
        '<hh:tabPr id="0" autoTabLeft="0" autoTabRight="0"/>'
        '</hh:tabProperties>'
    )


def _para_properties() -> str:
    return (
        '<hh:paraProperties itemCnt="1">'
        '<hh:paraPr id="0" tabPrIDRef="0" condense="0" fontLineHeight="0" '
        'snapToGrid="1" suppressLineNumbers="0" checked="0">'
        '<hh:align horizontal="LEFT" vertical="BASELINE"/>'
        '<hh:heading type="NONE" idRef="0" level="0"/>'
        '<hh:breakSetting breakLatinWord="KEEP_WORD" breakNonLatinWord="KEEP_WORD" '
        'widowOrphan="0" keepWithNext="0" keepLines="0" pageBreakBefore="0" lineWrap="BREAK"/>'
        '<hh:margin><hc:intent value="0" unit="HWPUNIT"/>'
        '<hc:left value="0" unit="HWPUNIT"/><hc:right value="0" unit="HWPUNIT"/>'
        '<hc:prev value="0" unit="HWPUNIT"/><hc:next value="0" unit="HWPUNIT"/></hh:margin>'
        '<hh:lineSpacing type="PERCENT" value="160" unit="HWPUNIT"/>'
        '</hh:paraPr>'
        '</hh:paraProperties>'
    )


def _styles() -> str:
    return (
        '<hh:styles itemCnt="1">'
        '<hh:style id="0" type="PARA" name="바탕글" engName="Normal" '
        'paraPrIDRef="0" charPrIDRef="0" nextStyleIDRef="0" langID="1042" lockForm="0"/>'
        '</hh:styles>'
    )


# --------------------------------------------------------------------------- #
# Package descriptor & container parts
# --------------------------------------------------------------------------- #
def _content_hpf(document: Document, bins: List[_BinItem]) -> str:
    title = xml_escape(document.title)
    bin_items = "".join(
        f'<opf:item id="{b.figure_id}" href="{b.arc_name}" '
        f'media-type="{b.media_type}" isEmbeded="1"/>'
        for b in bins
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<hpf:package xmlns:hpf="http://www.hancom.co.kr/schema/2011/hpf" '
        'xmlns:opf="http://www.idpf.org/2007/opf/" version="1.31" unique-identifier="hwpUID">'
        '<hpf:head>'
        '<hpf:version targetApplication="WORDPROCESSOR" major="5" minor="1" '
        'micro="1" buildNumber="0" os="1" application="Exam Studio"/>'
        '</hpf:head>'
        '<opf:metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f'<dc:title>{title}</dc:title>'
        '<dc:creator>Exam Studio</dc:creator>'
        '<dc:language>ko</dc:language>'
        '</opf:metadata>'
        '<opf:manifest>'
        '<opf:item id="header" href="Contents/header.xml" media-type="application/xml"/>'
        '<opf:item id="section0" href="Contents/section0.xml" media-type="application/xml"/>'
        '<opf:item id="settings" href="settings.xml" media-type="application/xml"/>'
        + bin_items
        + '</opf:manifest>'
        '<opf:spine>'
        '<opf:itemref idref="header" linear="yes"/>'
        '<opf:itemref idref="section0" linear="yes"/>'
        '</opf:spine>'
        '</hpf:package>'
    )


def _version_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<hv:HCFVersion xmlns:hv="http://www.hancom.co.kr/hwpml/2011/version" '
        'tagetApplication="WORDPROCESSOR" major="5" minor="1" micro="1" '
        'buildNumber="0" os="1" xmlVersion="1.4" application="Exam Studio" '
        'appVersion="0.1.0"/>'
    )


def _settings_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<ha:HWPApplicationSetting xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app">'
        '<ha:CaretPosition listIDRef="0" paraIDRef="0" pos="0"/>'
        '</ha:HWPApplicationSetting>'
    )


def _container_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<ocf:container xmlns:ocf="urn:oasis:names:tc:opendocument:xmlns:container" '
        'xmlns:hpf="http://www.hancom.co.kr/schema/2011/hpf">'
        '<ocf:rootfiles>'
        '<ocf:rootfile full-path="Contents/content.hpf" '
        'media-type="application/hwpml-package+xml"/>'
        '</ocf:rootfiles>'
        '</ocf:container>'
    )


def _manifest_xml(bins: List[_BinItem]) -> str:
    entries = [
        ("Contents/content.hpf", "application/hwpml-package+xml"),
        ("Contents/header.xml", "application/xml"),
        ("Contents/section0.xml", "application/xml"),
        ("settings.xml", "application/xml"),
        ("version.xml", "application/xml"),
        ("Preview/PrvText.txt", "text/plain"),
    ] + [(b.arc_name, b.media_type) for b in bins]
    items = "".join(
        f'<odf:file-entry odf:full-path="{path}" odf:media-type="{mt}"/>'
        for path, mt in entries
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<odf:manifest xmlns:odf="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" '
        'odf:version="1.2">'
        '<odf:file-entry odf:full-path="/" odf:media-type="application/hwp+zip"/>'
        + items
        + '</odf:manifest>'
    )


def _preview_text(document: Document) -> str:
    lines = [document.title, ""]
    for p in document.problems:
        lines.append(f"{p.number}. {p.text}")
        for i, choice in enumerate(p.choices):
            lines.append(f"  ({i + 1}) {choice}")
        for fig in p.figures:
            lines.append(f"  [그림 {fig.id}]")
        if p.solution:
            lines.append("[풀이]")
            lines.append(p.solution)
        lines.append("")
    return _strip_markers("\n".join(lines))


def _preview_html(document: Document, assets_dir: Optional[Path], columns: int = 1,
                  header: bool = True) -> str:
    def esc(s: str) -> str:
        s = (s or "").replace("[[eq]]", "").replace("[[/eq]]", "")
        return html.escape(s).replace("\n", "<br/>")

    def img_tag(figure: Figure) -> str:
        if assets_dir is None:
            return ""
        src = Path(assets_dir) / figure.path
        if not src.exists():
            return ""
        media = mimetypes.guess_type(src.name)[0] or "image/png"
        b64 = base64.b64encode(src.read_bytes()).decode("ascii")
        return f"<img class='figure' alt='{html.escape(figure.id)}' src='data:{media};base64,{b64}'/>"

    rows = []
    for p in document.problems:
        choices = "".join(f"<li>{esc(c)}</li>" for c in p.choices)
        choices_html = f"<ol class='choices'>{choices}</ol>" if choices else ""
        figures_html = "".join(img_tag(f) for f in p.figures)
        solution = (
            f"<div class='solution'><b>풀이</b><p>{esc(p.solution)}</p></div>"
            if p.solution
            else ""
        )
        rows.append(
            f"<section class='problem'><h3>{p.number}.</h3>"
            f"<p class='stem'>{esc(p.text)}</p>{choices_html}{figures_html}{solution}</section>"
        )
    col_css = (
        f"column-count:{int(columns)};column-gap:2rem;" if columns and columns > 1 else ""
    )
    title = html.escape(document.title)
    if header:
        head_html = (
            f"<h1 class='examtitle'>{title}</h1>"
            "<table class='infohdr'><tr>"
            "<td class='lbl'>이름</td><td></td>"
            "<td class='lbl'>학년 / 반</td><td></td>"
            "<td class='lbl'>날짜</td><td></td>"
            "</tr></table>"
        )
    else:
        head_html = f"<h1>{title}</h1>"
    return (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        f"<title>{title}</title>"
        "<style>body{font-family:'Malgun Gothic',sans-serif;max-width:820px;margin:2rem auto;"
        "padding:0 1rem;line-height:1.6;color:#1a1a1a}"
        ".examtitle{text-align:center;font-size:1.8rem;border:none;margin:.2rem 0 1rem}"
        "h1{border-bottom:2px solid #333;padding-bottom:.4rem}"
        ".infohdr{width:100%;border-collapse:collapse;margin-bottom:1.2rem}"
        ".infohdr td{border:1px solid #888;padding:.5rem;height:1.4rem}"
        ".infohdr .lbl{background:#eee;text-align:center;font-weight:600;width:9%}"
        f".body{{{col_css}}}"
        ".problem{margin:0 0 1.4rem;padding:1rem;border:1px solid #e2e2e2;border-radius:8px;"
        "break-inside:avoid}"
        ".problem h3{margin:.2rem 0;color:#0b5}.choices{margin:.4rem 0}"
        ".figure{max-width:100%;margin:.6rem 0;border:1px solid #ddd;border-radius:6px}"
        ".solution{margin-top:.8rem;padding:.6rem .8rem;background:#f6f8fa;border-radius:6px}"
        ".solution p{margin:.3rem 0;white-space:pre-wrap}</style></head>"
        f"<body>{head_html}<div class='body'>"
        + "".join(rows)
        + "</div></body></html>"
    )


def _stored(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name)
    info.compress_type = zipfile.ZIP_STORED
    return info


__all__ = ["build", "write_preview_html", "MIMETYPE", "_build_legacy"]
