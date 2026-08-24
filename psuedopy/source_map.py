from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SourceMap:
    """Map generated Python locations back to original PsuedoPY source."""

    python_to_ppy: dict[int, int]
    ppy_lines: list[str]
    python_lines: list[str] = field(default_factory=list)

    def original_line_no(self, python_lineno: int) -> int:
        return self.python_to_ppy.get(python_lineno, python_lineno)

    def original_source_line(self, python_lineno: int) -> str | None:
        original_lineno = self.original_line_no(python_lineno)
        if 1 <= original_lineno <= len(self.ppy_lines):
            return self.ppy_lines[original_lineno - 1].rstrip("\n")
        return None

    def generated_source_line(self, python_lineno: int) -> str | None:
        if 1 <= python_lineno <= len(self.python_lines):
            return self.python_lines[python_lineno - 1].rstrip("\n")
        return None

    @classmethod
    def identity(cls, ppy_lines: list[str]) -> SourceMap:
        mapping = {i: i for i in range(1, len(ppy_lines) + 1)}
        return cls(
            python_to_ppy=mapping,
            ppy_lines=ppy_lines,
            python_lines=list(ppy_lines),
        )
