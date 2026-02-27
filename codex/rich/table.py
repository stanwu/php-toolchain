from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class _Column:
    header: str


class Table:
    def __init__(self, *, title: str = "", show_lines: bool = False, **_: Any) -> None:
        self.title = title
        self.columns: list[_Column] = []
        self.rows: list[list[Any]] = []

    def add_column(self, header: str, **_: Any) -> None:
        self.columns.append(_Column(header=header))

    def add_row(self, *values: Any, **_: Any) -> None:
        self.rows.append(list(values))

    def __str__(self) -> str:
        lines: list[str] = []
        if self.title:
            lines.append(self.title)
        headers = " | ".join(c.header for c in self.columns)
        lines.append(headers)
        for row in self.rows:
            lines.append(" | ".join(str(v) for v in row))
        return "\n".join(lines)
