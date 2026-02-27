from __future__ import annotations

import sys
from typing import Any, TextIO


class Console:
    def __init__(
        self,
        *,
        file: TextIO | None = None,
        highlight: bool = True,  # kept for compatibility
        markup: bool = True,  # kept for compatibility
        width: int | None = None,
        **_: Any,
    ) -> None:
        self.file = file or sys.stdout
        self.highlight = highlight
        self.markup = markup
        self.width = width

    def print(self, *objects: Any, sep: str = " ", end: str = "\n", **_: Any) -> None:
        text = sep.join(str(o) for o in objects)
        self.file.write(text + end)
        try:
            self.file.flush()
        except Exception:
            pass

