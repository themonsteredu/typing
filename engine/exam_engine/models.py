"""Data models passed between pipeline stages (serialized as JSON on disk)."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class Figure:
    """An image cropped from the source PDF and referenced by a problem."""

    id: str
    path: str            # relative path inside the work dir
    page: int
    width: int = 0
    height: int = 0
    caption: str = ""

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Figure":
        return cls(
            id=d["id"],
            path=d["path"],
            page=int(d.get("page", 0)),
            width=int(d.get("width", 0)),
            height=int(d.get("height", 0)),
            caption=d.get("caption", ""),
        )


@dataclass
class Problem:
    """A single exam problem and its (optional) generated solution."""

    number: int
    page: int
    text: str
    choices: List[str] = field(default_factory=list)
    answer: str = ""
    solution: str = ""
    figures: List[Figure] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Problem":
        return cls(
            number=int(d.get("number", 0)),
            page=int(d.get("page", 0)),
            text=d.get("text", ""),
            choices=list(d.get("choices", [])),
            answer=d.get("answer", ""),
            solution=d.get("solution", ""),
            figures=[Figure.from_dict(f) for f in d.get("figures", [])],
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Document:
    """The full extracted exam: a title plus an ordered list of problems."""

    title: str
    source: str
    problems: List[Problem] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Document":
        return cls(
            title=d.get("title", "Exam"),
            source=d.get("source", ""),
            problems=[Problem.from_dict(p) for p in d.get("problems", [])],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "source": self.source,
            "problems": [p.to_dict() for p in self.problems],
        }


__all__ = ["Figure", "Problem", "Document"]
