"""AI client wrapper.

Wraps the Anthropic Claude SDK with a deterministic fallback so the whole
pipeline runs (and tests pass) without a key. When a key is present in the
shared settings (entered via the web Settings panel) the real model is used.
"""

from __future__ import annotations

import base64
import json
import re
from typing import List, Optional, Tuple

from . import usage as usage_mod
from .models import Problem
from .settings import Settings, load as load_settings


_EQ_INSTRUCTION = (
    " 수식(분수·지수·루트·적분 등 모양이 중요한 식)은 한글 수식 스크립트로 "
    "[[eq]]와 [[/eq]] 사이에 작성하세요. 표기 규칙: 분수는 {분자} over {분모}, "
    "지수는 x^2, 아래첨자는 x_1, 루트는 sqrt{x}, 곱은 times, 부등호는 <= >=, "
    "적분은 int, 시그마는 sum 입니다. 예: [[eq]]{1} over {2} x^2 - sqrt{3} <= 0[[/eq]]. "
    "간단한 정수 계산이나 한 줄 답은 평문으로 두어도 됩니다."
)


def sanitize_text(text: str) -> str:
    """Strip markdown/LaTeX so it reads as plain text in HWPX/한글.

    The model sometimes returns `## 풀이`, `**bold**`, `$$...$$`, `\\frac{a}{b}`.
    None of that renders in 한글, so flatten it to readable plain-text math.
    """
    if not text:
        return text
    # \frac{a}{b} -> (a)/(b)
    text = re.sub(r"\\d?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"(\1)/(\2)", text)
    # common LaTeX commands -> unicode/plain
    for pat, rep in {
        r"\\times": "×", r"\\div": "÷", r"\\cdot": "·", r"\\pm": "±",
        r"\\leq": "≤", r"\\geq": "≥", r"\\le\b": "≤", r"\\ge\b": "≥",
        r"\\neq": "≠", r"\\sqrt": "√", r"\\pi": "π", r"\\infty": "∞",
        r"\\left": "", r"\\right": "", r"\\,": " ", r"\\\\": "\n",
    }.items():
        text = re.sub(pat, rep, text)
    # drop $$ / $ math delimiters (keep the inner content)
    text = text.replace("$$", "").replace("$", "")
    # markdown headers, bold/italic, inline code
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = text.replace("**", "").replace("__", "").replace("`", "")
    # collapse excess blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

# JSON schema for vision extraction (structured output).
_EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "problems": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "number": {"type": "integer"},
                    "text": {"type": "string"},
                    "choices": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["number", "text", "choices"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["problems"],
    "additionalProperties": False,
}


class AIClient:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or load_settings()
        self._client = None  # lazily constructed anthropic.Anthropic

    @property
    def enabled(self) -> bool:
        return bool(self.settings.api_key())

    def _anthropic(self):
        if self._client is not None:
            return self._client
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "The `anthropic` package is required for AI features. "
                "Install it with `pip install -r requirements.txt`."
            ) from exc
        self._client = anthropic.Anthropic(api_key=self.settings.api_key())
        return self._client

    def _complete(self, stage: str, system: str, prompt: str, max_tokens: int = 1024) -> str:
        client = self._anthropic()
        message = client.messages.create(
            model=self.settings.model_for(stage),
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        self._record_usage(message, stage)
        parts = [block.text for block in message.content if getattr(block, "type", "") == "text"]
        return "\n".join(parts).strip()

    def _record_usage(self, message, stage: str) -> None:
        u = getattr(message, "usage", None)
        if u is None:
            return
        try:
            usage_mod.record(
                self.settings.model_for(stage),
                int(getattr(u, "input_tokens", 0) or 0),
                int(getattr(u, "output_tokens", 0) or 0),
                cache_read=int(getattr(u, "cache_read_input_tokens", 0) or 0),
                cache_creation=int(getattr(u, "cache_creation_input_tokens", 0) or 0),
                stage=stage,
            )
        except Exception:
            pass  # usage tracking must never break the pipeline

    # ----- stage 1 (vision): read problems from a rendered page image -----
    def extract_problems_from_image(
        self, image_bytes: bytes, media_type: str = "image/png"
    ) -> List[Problem]:
        """Use Claude vision to transcribe problems (math included) from a page."""
        if not self.enabled:
            return []
        client = self._anthropic()
        b64 = base64.standard_b64encode(image_bytes).decode("ascii")
        system = (
            "당신은 한국 수학 시험지를 정확히 디지털화하는 OCR 전문가입니다. "
            "이미지의 모든 문제를 읽어 번호, 문제 본문, 보기(객관식)로 구조화하세요. "
            "보기가 없으면 빈 배열로 두세요."
        )
        system += _EQ_INSTRUCTION if self.settings.use_equations else (
            " 수식은 사람이 읽을 수 있는 평문(x^2, √, 분수는 a/b)으로 옮기되 의미를 보존하세요."
        )
        message = client.messages.create(
            model=self.settings.model_for("extract"),
            max_tokens=4096,
            system=system,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                    {"type": "text", "text": "이 페이지의 문제들을 추출하세요."},
                ],
            }],
            output_config={"format": {"type": "json_schema", "schema": _EXTRACT_SCHEMA}},
        )
        self._record_usage(message, "extract")
        text = "".join(b.text for b in message.content if getattr(b, "type", "") == "text").strip()
        try:
            data = json.loads(text)
        except Exception:
            return []
        problems: List[Problem] = []
        for p in data.get("problems", []):
            problems.append(Problem(
                number=int(p.get("number", 0) or 0),
                page=0,
                text=sanitize_text(p.get("text", "")),
                choices=[sanitize_text(c) for c in p.get("choices", [])],
            ))
        return problems

    # ----- stage 2: generate a worked solution for one problem -----
    def solve(self, problem: Problem) -> str:
        if not self.enabled:
            return _fallback_solution(problem)
        system = (
            "당신은 한국 고등학교 수학 시험 문제의 풀이를 작성하는 전문가입니다. "
            "단계별로 명확하고 간결하게 풀이를 작성하고, 마지막 줄에 '정답: '으로 정답을 표시하세요. "
            "중요: 마크다운(#, **, 목록 기호)이나 LaTeX($, $$, \\frac 등)을 절대 쓰지 마세요."
        )
        system += _EQ_INSTRUCTION if self.settings.use_equations else (
            " 수식은 x^2, a/b, √, ≤, × 같은 평문 기호로 표기하세요."
        )
        prompt = _problem_prompt(problem)
        try:
            return sanitize_text(self._complete("generate", system, prompt, max_tokens=1500))
        except Exception as exc:  # network / auth errors -> graceful fallback
            return _fallback_solution(problem, error=str(exc))


def solve_all(problems: List[Problem], settings: Optional[Settings] = None) -> List[Problem]:
    client = AIClient(settings)
    for problem in problems:
        problem.solution = client.solve(problem)
    return problems


def _problem_prompt(problem: Problem) -> str:
    lines = [f"[{problem.number}번 문제]", problem.text]
    if problem.choices:
        for i, choice in enumerate(problem.choices, start=1):
            lines.append(f"{'①②③④⑤⑥⑦⑧⑨⑩'[i - 1]} {choice}")
    lines.append("\n위 문제의 풀이와 정답을 작성하세요.")
    return "\n".join(lines)


def _fallback_solution(problem: Problem, error: str = "") -> str:
    """Deterministic placeholder so the document still assembles without a key."""
    note = "(AI 키가 설정되지 않아 자동 풀이를 생성하지 못했습니다.)"
    if error:
        note = f"(AI 호출 실패로 자동 풀이를 생성하지 못했습니다: {error})"
    pieces = [note, "", "풀이를 입력하세요."]
    if problem.choices:
        pieces.append("정답: (보기 중 선택)")
    else:
        pieces.append("정답: ")
    return "\n".join(pieces)


__all__ = ["AIClient", "solve_all"]
