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

        headers = []
        helper_imports = []
        if "inclusive_range" in parsed.required_helpers:
            helper_imports.append("inclusive_range as __ppy_inclusive_range")
        if "repeat_times" in parsed.required_helpers:
            helper_imports.append("repeat_times as __ppy_repeat_times")
        if helper_imports:
            headers.append("from psuedopy.runtime import " + ", ".join(helper_imports))
            headers.append("")

        generated_lines = headers + [line.python for line in parsed.lines]
        mapping = {}
        if headers:
            mapping[1] = 1
            mapping[2] = 1
        offset = len(headers)
        for index, generated in enumerate(parsed.lines, start=1):
            mapping[index + offset] = generated.source_line

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
