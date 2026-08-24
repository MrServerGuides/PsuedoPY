from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from psuedopy.errors import IncompleteInputError, TranspilerError
from psuedopy.grammar import Grammar
from psuedopy.parser import SyntaxParser
from psuedopy.source_map import SourceMap


class TranslatedSource(NamedTuple):
    python_code: str
    source_map: SourceMap
    original_source: str


class Transpiler:
    """Parse PsuedoPY source and generate executable, line-mapped Python."""

    def __init__(self, grammar_file: str | Path | None = None) -> None:
        self.grammar = Grammar.load(grammar_file)
        self.grammar_map: dict[str, str] = self.grammar.simple_map
        self.keyword_categories = {
            spec.spelling: spec.category for _, spec in self.grammar.items()
        }
        self.parser = SyntaxParser(self.grammar)

    def translate(
        self, source: str, *, allow_incomplete: bool = False
    ) -> TranslatedSource:
        parsed = self.parser.parse(source, allow_incomplete=allow_incomplete)
        original_lines = source.splitlines() or [""]

        headers = [
            "from __future__ import annotations",
            "from typing import NoReturn as __PpyNever",
            "",
        ]
        helper_imports = []
        if "inclusive_range" in parsed.required_helpers:
            helper_imports.append("inclusive_range as __ppy_inclusive_range")
        if "repeat_times" in parsed.required_helpers:
            helper_imports.append("repeat_times as __ppy_repeat_times")
        if helper_imports:
            headers.append("from psuedopy.runtime import " + ", ".join(helper_imports))
            headers.append("")
        if "protocol" in parsed.required_helpers:
            headers.append("from typing import Protocol as __PpyProtocol")
            headers.append("")
        if "enum" in parsed.required_helpers:
            headers.append("from enum import Enum as __PpyEnum")
            headers.append("")

        generated_lines = list(headers)
        mapping = {index: 0 for index in range(1, len(headers) + 1)}
        for generated in parsed.lines:
            physical = generated.python.split("\n")
            source_end = generated.source_end or generated.source_line
            for offset, line in enumerate(physical):
                generated_lines.append(line)
                mapping[len(generated_lines)] = min(
                    generated.source_line + offset, source_end
                )

        python_code = "\n".join(generated_lines)
        source_map = SourceMap(
            python_to_ppy=mapping,
            ppy_lines=original_lines,
            python_lines=generated_lines,
        )
        return TranslatedSource(
            python_code=python_code,
            source_map=source_map,
            original_source=source,
        )


__all__ = [
    "IncompleteInputError",
    "TranslatedSource",
    "Transpiler",
    "TranspilerError",
]
