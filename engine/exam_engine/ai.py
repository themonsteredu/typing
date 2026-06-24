"""AI client wrapper.

Wraps the Anthropic Claude SDK with a deterministic fallback so the whole
pipeline runs (and tests pass) without a key. When a key is present in the
shared settings (entered via the web Settings panel) the real model is used.
"""

from __future__ import annotations

from typing import List, Optional

from .models import Problem
from .settings import Settings, load as load_settings


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
        parts = [block.text for block in message.content if getattr(block, "type", "") == "text"]
        return "\n".join(parts).strip()

    # ----- stage 2: generate a worked solution for one problem -----
    def solve(self, problem: Problem) -> str:
        if not self.enabled:
            return _fallback_solution(problem)
        system = (
            "당신은 한국 고등학교 수학 시험 문제의 풀이를 작성하는 전문가입니다. "
            "단계별로 명확하고 간결하게 풀이를 작성하고, 마지막 줄에 '정답: '으로 정답을 표시하세요."
        )
        prompt = _problem_prompt(problem)
        try:
            return self._complete("generate", system, prompt, max_tokens=1500)
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
