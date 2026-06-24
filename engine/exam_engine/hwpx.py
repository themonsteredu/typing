"""Stage 4 — assemble a :class:`Document` into an HWPX file.

HWPX is Hancom Office's open document format: a ZIP container holding OWPML XML
(``http://www.hancom.co.kr/hwpml/2011/*`` namespaces), structured like ODF/OOXML.

This writer emits the documented HWPX container layout::

    mimetype                 (stored uncompressed, first entry)
    version.xml
    settings.xml
    Contents/content.hpf     (package manifest / spine)
    Contents/header.xml      (fonts, char/para properties)
    Contents/section0.xml    (the body paragraphs)
    Preview/PrvText.txt
    META-INF/container.xml
    META-INF/manifest.xml

It targets the published OWPML structure and is best-effort with respect to a
specific Hancom build; an always-correct ``preview.html`` is written alongside
the ``.hwpx`` so results are verifiable without Hancom installed.
"""

from __future__ import annotations

import html
import zipfile
from pathlib import Path
from typing import List
from xml.sax.saxutils import escape as xml_escape

from .models import Document, Problem

MIMETYPE = "application/hwp+zip"

NS = {
    "head": "http://www.hancom.co.kr/hwpml/2011/head",
    "para": "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "section": "http://www.hancom.co.kr/hwpml/2011/section",
    "core": "http://www.hancom.co.kr/hwpml/2011/core",
}


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def build(document: Document, out_path: Path) -> Path:
    """Write ``document`` to ``out_path`` (an ``.hwpx`` file)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    paragraphs = _document_paragraphs(document)

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # mimetype MUST be the first entry and stored (uncompressed).
        zf.writestr(_stored("mimetype"), MIMETYPE)
        zf.writestr("version.xml", _version_xml())
        zf.writestr("settings.xml", _settings_xml())
        zf.writestr("Contents/content.hpf", _content_hpf(document))
        zf.writestr("Contents/header.xml", _header_xml())
        zf.writestr("Contents/section0.xml", _section_xml(paragraphs))
        zf.writestr("Preview/PrvText.txt", _preview_text(document))
        zf.writestr("META-INF/container.xml", _container_xml())
        zf.writestr("META-INF/manifest.xml", _manifest_xml())

    # Always-correct, verifiable rendering next to the HWPX.
    write_preview_html(document, out_path.with_suffix(".html"))
    return out_path


def write_preview_html(document: Document, out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_preview_html(document), encoding="utf-8")
    return out_path


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
        run_inner = secpr + (f"<hp:t>{xml_escape(text)}</hp:t>" if text else "<hp:t></hp:t>")
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
# Static-ish container parts
# --------------------------------------------------------------------------- #
def _header_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<hh:head xmlns:hh="{NS["head"]}" xmlns:hc="{NS["core"]}" '
        'version="1.31" secCnt="1">'
        '<hh:beginNum page="1" footnote="1" endnote="1" pic="1" tbl="1" equation="1"/>'
        '<hh:refList>'
        '<hh:fontfaces itemCnt="1">'
        '<hh:fontface lang="HANGUL" fontCnt="1">'
        '<hh:font id="0" face="함초롬바탕" type="TTF" isEmbedded="0">'
        '<hh:typeInfo familyType="FCAT_MYUNGJO" weight="50" proportion="0" '
        'contrast="0" strokeVariation="0" armStyle="0" letterform="0" '
        'midline="0" xHeight="0"/>'
        '</hh:font>'
        '</hh:fontface>'
        '</hh:fontfaces>'
        '<hh:charProperties itemCnt="1">'
        '<hh:charPr id="0" height="1000" textColor="#000000" shadeColor="none" '
        'useFontSpace="0" useKerning="0" symMark="NONE" borderFillIDRef="2">'
        '<hh:fontRef hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
        '<hh:ratio hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>'
        '<hh:spacing hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
        '<hh:relSz hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>'
        '<hh:offset hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
        '</hh:charPr>'
        '</hh:charProperties>'
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
        '<hh:styles itemCnt="1">'
        '<hh:style id="0" type="PARA" name="바탕글" engName="Normal" '
        'paraPrIDRef="0" charPrIDRef="0" nextStyleIDRef="0" langID="1042" lockForm="0"/>'
        '</hh:styles>'
        '</hh:refList>'
        '</hh:head>'
    )


def _content_hpf(document: Document) -> str:
    title = xml_escape(document.title)
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
        '</opf:manifest>'
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


def _manifest_xml() -> str:
    entries = [
        ("Contents/content.hpf", "application/hwpml-package+xml"),
        ("Contents/header.xml", "application/xml"),
        ("Contents/section0.xml", "application/xml"),
        ("settings.xml", "application/xml"),
        ("version.xml", "application/xml"),
        ("Preview/PrvText.txt", "text/plain"),
    ]
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
        if p.solution:
            lines.append("[풀이]")
            lines.append(p.solution)
        lines.append("")
    return "\n".join(lines)


def _preview_html(document: Document) -> str:
    def esc(s: str) -> str:
        return html.escape(s).replace("\n", "<br/>")

    rows = []
    for p in document.problems:
        choices = "".join(
            f'<li>{esc(c)}</li>' for c in p.choices
        )
        choices_html = f"<ol class='choices'>{choices}</ol>" if choices else ""
        solution = f"<div class='solution'><b>풀이</b><p>{esc(p.solution)}</p></div>" if p.solution else ""
        rows.append(
            f"<section class='problem'><h3>{p.number}.</h3>"
            f"<p class='stem'>{esc(p.text)}</p>{choices_html}{solution}</section>"
        )
    return (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        f"<title>{html.escape(document.title)}</title>"
        "<style>body{font-family:'Malgun Gothic',sans-serif;max-width:820px;margin:2rem auto;"
        "padding:0 1rem;line-height:1.6;color:#1a1a1a}h1{border-bottom:2px solid #333;padding-bottom:.4rem}"
        ".problem{margin:1.4rem 0;padding:1rem;border:1px solid #e2e2e2;border-radius:8px}"
        ".problem h3{margin:.2rem 0;color:#0b5}.choices{margin:.4rem 0}"
        ".solution{margin-top:.8rem;padding:.6rem .8rem;background:#f6f8fa;border-radius:6px}"
        ".solution p{margin:.3rem 0;white-space:pre-wrap}</style></head>"
        f"<body><h1>{html.escape(document.title)}</h1>"
        + "".join(rows)
        + "</body></html>"
    )


def _stored(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name)
    info.compress_type = zipfile.ZIP_STORED
    return info


__all__ = ["build", "write_preview_html", "MIMETYPE"]
