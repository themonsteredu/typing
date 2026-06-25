"""Command-line interface for the Exam Studio engine.

Examples::

    python -m exam_engine.cli run exam.pdf --out output/exam.hwpx
    python -m exam_engine.cli extract exam.pdf --out work/
    python -m exam_engine.cli settings get
    python -m exam_engine.cli settings set --anthropic-key sk-ant-...

Pass ``--json`` to emit newline-delimited JSON progress events on stdout
(consumed by the web studio to stream logs over SSE).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable

from . import license as license_mod, pipeline, settings as settings_mod
from .settings import Settings


def _make_logger(json_mode: bool) -> Callable[[str], None]:
    if json_mode:
        def log(msg: str) -> None:
            sys.stdout.write(json.dumps({"type": "log", "message": msg}, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    else:
        def log(msg: str) -> None:
            print(msg, flush=True)
    return log


def _emit_result(json_mode: bool, payload: dict) -> None:
    if json_mode:
        sys.stdout.write(json.dumps({"type": "result", **payload}, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def _require_license(log) -> bool:
    if license_mod.is_licensed():
        return True
    info = license_mod.load()
    log(f"라이선스가 필요합니다: {info.reason} (활성화: exam_engine.cli license activate <KEY>)")
    return False


def cmd_run(args: argparse.Namespace) -> int:
    log = _make_logger(args.json)
    if not _require_license(log):
        return 2
    cfg = settings_mod.load()
    out = Path(args.out)
    work = Path(args.work) if args.work else out.parent / "work"
    result = pipeline.run(Path(args.pdf), out, work_dir=work, settings=cfg, log=log)
    _emit_result(args.json, {"output": str(result), "preview": str(result.with_suffix(".html"))})
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    log = _make_logger(args.json)
    cfg = settings_mod.load()
    doc = pipeline.run_extract(Path(args.pdf), Path(args.out), cfg, log)
    _emit_result(args.json, {"problems": len(doc.problems), "work": str(args.out)})
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    log = _make_logger(args.json)
    cfg = settings_mod.load()
    doc = pipeline.run_generate(Path(args.work), cfg, log)
    _emit_result(args.json, {"problems": len(doc.problems), "work": str(args.work)})
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    log = _make_logger(args.json)
    cfg = settings_mod.load()
    result = pipeline.run_build(Path(args.work), Path(args.out), cfg, log)
    _emit_result(args.json, {"output": str(result), "preview": str(result.with_suffix(".html"))})
    return 0


def cmd_settings(args: argparse.Namespace) -> int:
    if args.action == "get":
        cfg = settings_mod.load()
        data = cfg.to_dict()
        # Mask the key when printing.
        if data.get("anthropicApiKey"):
            data["anthropicApiKey"] = data["anthropicApiKey"][:7] + "…"
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    # set
    cfg = settings_mod.load()
    if args.anthropic_key is not None:
        cfg.anthropic_api_key = args.anthropic_key
    if args.provider:
        cfg.provider = args.provider
    if args.dpi:
        cfg.dpi = args.dpi
    path = settings_mod.save(cfg)
    print(f"설정을 저장했습니다: {path}")
    return 0


def cmd_license(args: argparse.Namespace) -> int:
    if args.action == "status":
        info = license_mod.load()
        print(json.dumps(info.to_dict(), ensure_ascii=False, indent=2))
        return 0 if info.valid else 1
    # activate
    try:
        info = license_mod.activate(args.key)
    except ValueError as exc:
        print(f"활성화 실패: {exc}", file=sys.stderr)
        return 1
    exp = "무기한" if info.expires_at == 0 else str(info.expires_at)
    print(f"활성화 완료: {info.subject} (플랜 {info.plan}, 만료 {exp})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="exam_engine", description="Exam Studio document engine")
    parser.add_argument("--json", action="store_true", help="emit NDJSON progress events")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="full pipeline: PDF -> HWPX")
    p_run.add_argument("pdf")
    p_run.add_argument("--out", required=True)
    p_run.add_argument("--work")
    p_run.set_defaults(func=cmd_run)

    p_ext = sub.add_parser("extract", help="extract problems from a PDF")
    p_ext.add_argument("pdf")
    p_ext.add_argument("--out", required=True, help="work directory")
    p_ext.set_defaults(func=cmd_extract)

    p_gen = sub.add_parser("generate", help="generate AI solutions")
    p_gen.add_argument("work", help="work directory from extract")
    p_gen.add_argument("--out")
    p_gen.set_defaults(func=cmd_generate)

    p_bld = sub.add_parser("build", help="assemble HWPX from a work directory")
    p_bld.add_argument("work", help="work directory")
    p_bld.add_argument("--out", required=True)
    p_bld.set_defaults(func=cmd_build)

    p_set = sub.add_parser("settings", help="view or change stored settings")
    p_set.add_argument("action", choices=["get", "set"])
    p_set.add_argument("--anthropic-key", dest="anthropic_key")
    p_set.add_argument("--provider")
    p_set.add_argument("--dpi", type=int)
    p_set.set_defaults(func=cmd_settings)

    p_lic = sub.add_parser("license", help="view or activate a license key")
    p_lic.add_argument("action", choices=["status", "activate"])
    p_lic.add_argument("key", nargs="?", help="license token (for activate)")
    p_lic.set_defaults(func=cmd_license)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    # `--json` is global but argparse attaches it pre-subcommand; default if absent.
    if not hasattr(args, "json"):
        args.json = False
    try:
        return args.func(args)
    except Exception as exc:  # surface a clean error in both modes
        if getattr(args, "json", False):
            sys.stdout.write(json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        else:
            print(f"오류: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
