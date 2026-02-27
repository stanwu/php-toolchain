from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class Panel:
    renderable: Any
    title: str = ""
    style: str = ""

    def __str__(self) -> str:
        body = str(self.renderable)
        if self.title:
            return f"{self.title}\n{body}"
        return body

    @classmethod
    def fit(cls, renderable: Any, *, title: str = "", style: str = "") -> "Panel":
        return cls(renderable=renderable, title=title, style=style)
