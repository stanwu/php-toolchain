from __future__ import annotations


class Text:
    def __init__(self, text: str, style: str = "") -> None:
        self.text = text
        self.style = style

    def __str__(self) -> str:
        return self.text

