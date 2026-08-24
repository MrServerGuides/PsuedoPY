
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class SourceMap:

    python_to_ppy: Dict[int, int]
    ppy_lines: List[str]

    def original_line_no(self, python_lineno: int) -> int:
        return self.python_to_ppy.get(python_lineno, python_lineno)

    def original_source_line(self, python_lineno: int) -> Optional[str]:
        original_lineno = self.original_line_no(python_lineno)
        if 1 <= original_lineno <= len(self.ppy_lines):
            return self.ppy_lines[original_lineno - 1].rstrip("\n")
        return None

    @classmethod
    def identity(cls, ppy_lines: List[str]) -> "SourceMap":
        mapping = {i: i for i in range(1, len(ppy_lines) + 1)}
        return cls(python_to_ppy=mapping, ppy_lines=ppy_lines)