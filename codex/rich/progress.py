from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .console import Console


@dataclass(slots=True)
class SpinnerColumn:
    pass


@dataclass(slots=True)
class BarColumn:
    pass


@dataclass(slots=True)
class TextColumn:
    template: str


class Progress:
    def __init__(self, *columns: Any, console: Console | None = None, **_: Any) -> None:
        self.columns = columns
        self.console = console or Console()

    def __enter__(self) -> "Progress":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    def add_task(self, description: str, total: int | None = None) -> int:
        return 0

    def update(self, task_id: int, advance: int = 1, **_: Any) -> None:
        return None
