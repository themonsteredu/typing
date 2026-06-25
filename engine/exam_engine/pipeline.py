"""End-to-end pipeline orchestration.

Wires the four stages together and reports progress through a callback so the
web UI can stream log lines over SSE.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Optional

from . import ai, extract as extract_stage, figures as figures_stage, hwpx
from .models import Document
from .settings import Settings, load as load_settings

Logger = Callable[[str], None]


def _noop(_msg: str) -> None:
    pass


def _doc_path(work_dir: Path) -> Path:
    return Path(work_dir) / "document.json"


def load_document(work_dir: Path) -> Document:
    return Document.from_dict(json.loads(_doc_path(work_dir).read_text(encoding="utf-8")))


def save_document(document: Document, work_dir: Path) -> Path:
    path = _doc_path(work_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return path


# --------------------------------------------------------------------------- #
# Individual stages (each persists document.json so they're independently runnable)
# --------------------------------------------------------------------------- #
def run_extract(pdf_path: Path, work_dir: Path, settings: Settings, log: Logger = _noop) -> Document:
    client = ai.AIClient(settings)
    if settings.use_vision and client.enabled:
        log(f"AI 비전으로 페이지를 읽는 중: {Path(pdf_path).name}")
        document = extract_stage.extract_with_vision(pdf_path, work_dir, client, dpi=settings.dpi, log=log)
    else:
        if settings.use_vision and not client.enabled:
            log("AI 키가 없어 일반 텍스트 추출로 진행합니다(수식이 깨질 수 있음).")
        else:
            log(f"PDF에서 텍스트를 추출하는 중: {Path(pdf_path).name}")
        document = extract_stage.extract(pdf_path, work_dir, dpi=settings.dpi)
    n_figs = sum(len(p.figures) for p in document.problems)
    log(f"문제 {len(document.problems)}개, 도형 {n_figs}개를 인식했습니다.")
    save_document(document, work_dir)
    return document


def run_generate(work_dir: Path, settings: Settings, log: Logger = _noop) -> Document:
    document = load_document(work_dir)
    client = ai.AIClient(settings)
    log("AI 풀이 생성을 시작합니다." if client.enabled else "AI 키가 없어 폴백 풀이를 채웁니다.")
    for i, problem in enumerate(document.problems, start=1):
        problem.solution = client.solve(problem)
        log(f"  풀이 생성 {i}/{len(document.problems)} (#{problem.number})")
    save_document(document, work_dir)
    return document


def run_figures(work_dir: Path, settings: Settings, log: Logger = _noop) -> Document:
    log("도형/이미지를 최적화하는 중...")
    document = load_document(work_dir)
    document = figures_stage.process(document, work_dir)
    save_document(document, work_dir)
    return document


def run_build(work_dir: Path, out_path: Path, settings: Settings, log: Logger = _noop) -> Path:
    log("HWPX 문서를 조립하는 중...")
    document = load_document(work_dir)
    n_figs = sum(len(p.figures) for p in document.problems)
    if n_figs:
        log(f"도형 {n_figs}개를 문서에 포함합니다.")
    result = hwpx.build(document, out_path, assets_dir=Path(work_dir))
    log(f"완료: {result}")
    return result


# --------------------------------------------------------------------------- #
# Full pipeline
# --------------------------------------------------------------------------- #
def run(
    pdf_path: Path,
    out_path: Path,
    work_dir: Optional[Path] = None,
    settings: Optional[Settings] = None,
    log: Logger = _noop,
) -> Path:
    settings = settings or load_settings()
    work_dir = Path(work_dir) if work_dir else Path(out_path).with_suffix("").parent / "work"
    work_dir.mkdir(parents=True, exist_ok=True)

    log("=== 1/4 추출 ===")
    run_extract(pdf_path, work_dir, settings, log)
    log("=== 2/4 풀이 생성 ===")
    run_generate(work_dir, settings, log)
    log("=== 3/4 도형 처리 ===")
    run_figures(work_dir, settings, log)
    log("=== 4/4 HWPX 조립 ===")
    result = run_build(work_dir, out_path, settings, log)
    log("파이프라인 완료 🎉")
    return result


__all__ = [
    "run",
    "run_extract",
    "run_generate",
    "run_figures",
    "run_build",
    "load_document",
    "save_document",
]
