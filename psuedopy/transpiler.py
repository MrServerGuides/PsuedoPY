
from __future__ import annotations

import io
import json
import tokenize
from pathlib import Path
from typing import Dict, List, NamedTuple

from psuedopy.source_map import SourceMap


class TranspilerError(Exception):
    pass


class _Replacement(NamedTuple):

    start: int
    end: int
    text: str


class TranslatedSource(NamedTuple):

    python_code: str
    source_map: SourceMap
    original_source: str


class Transpiler:

    _BLOCK_OPENERS = {
        "def", "if", "elif", "else", "for", "while", "class",
        "try", "except", "finally", "with", "match", "case",
    }

    _EMPTY = "__EMPTY__"
    _END = "__END__"

    def __init__(self, grammar_file: str | Path | None = None) -> None:
        if grammar_file is None:
            grammar_file = Path(__file__).parent / "data" / "grammar_map.json"
        self.grammar_map: Dict[str, str] = self._load_grammar(grammar_file)

    @staticmethod
    def _load_grammar(path: str | Path) -> Dict[str, str]:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise TranspilerError("grammar_map.json must contain a JSON object")
        return data

    def _apply_replacements(
        self,
        original_line: str,
        replacements: List[_Replacement],
    ) -> str:
        if not replacements:
            return original_line

        replacements = sorted(replacements, key=lambda r: r.start)

        parts: List[str] = []
        last = 0
        for repl in replacements:
            parts.append(original_line[last : repl.start])
            parts.append(repl.text)
            last = repl.end
        parts.append(original_line[last:])

        new_line = "".join(parts)

        if new_line.strip() == "":
            return ""

        original_indent = original_line[
            : len(original_line) - len(original_line.lstrip())
        ]
        stripped = new_line.lstrip()
        return original_indent + stripped

    def translate(self, source: str) -> TranslatedSource:
        ppy_lines = source.splitlines()
        if not ppy_lines:
            ppy_lines = [""]

        replacements_by_line: Dict[int, List[_Replacement]] = {}
        header_lines: set[int] = set()
        blank_lines: set[int] = set()

        try:
            tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        except tokenize.TokenError as exc:
            raise TranspilerError(f"Lexical error: {exc}") from exc

        for token in tokens:
            if token.type != tokenize.NAME:
                continue

            line_no = token.start[0]
            original = token.string
            mapped = self.grammar_map.get(original)

            if mapped is None:
                continue

            if mapped == self._END:
                blank_lines.add(line_no)
                continue

            if mapped == self._EMPTY:
                replacements_by_line.setdefault(line_no, []).append(
                    _Replacement(token.start[1], token.end[1], "")
                )
                continue

            replacements_by_line.setdefault(line_no, []).append(
                _Replacement(token.start[1], token.end[1], mapped)
            )

            if mapped in self._BLOCK_OPENERS:
                header_lines.add(line_no)

        output_lines: List[str] = []

        for idx, original_line in enumerate(ppy_lines, start=1):
            if idx in blank_lines:
                output_lines.append("")
                continue

            line = self._apply_replacements(
                original_line,
                replacements_by_line.get(idx, []),
            )

            if (
                idx in header_lines
                and line.strip()
                and not line.rstrip().endswith(":")
            ):
                line = line.rstrip() + ":"

            output_lines.append(line)

        python_code = "\n".join(output_lines)
        source_map = SourceMap.identity(ppy_lines)

        return TranslatedSource(
            python_code=python_code,
            source_map=source_map,
            original_source=source,
        )
