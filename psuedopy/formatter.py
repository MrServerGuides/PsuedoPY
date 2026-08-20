
from __future__ import annotations

import io
import json
import tokenize
from pathlib import Path
from typing import Dict, List, NamedTuple

_CANONICAL_FORMS: Dict[str, str] = {
    "text": "Text",
    "print": "Text",
    "echo": "Text",
    "write": "Text",
    "display": "Text",
    "output": "Text",
    "ask": "Ask",
    "input": "Ask",
    "read": "Ask",
    "prompt": "Ask",
    "function": "Function",
    "def": "Function",
    "func": "Function",
    "procedure": "Function",
    "method": "Function",
    "when": "When",
    "if": "When",
    "otherwise": "Otherwise",
    "else": "Otherwise",
    "elseif": "ElseIf",
    "elif": "ElseIf",
    "repeat": "Repeat",
    "for": "Repeat",
    "while": "While",
    "loop": "While",
    "let": "Let",
    "set": "Set",
    "var": "Var",
    "declare": "Declare",
    "const": "Const",
    "end": "End",
    "return": "Return",
    "class": "Class",
    "try": "Try",
    "except": "Except",
    "catch": "Catch",
    "finally": "Finally",
    "with": "With",
    "using": "Using",
    "match": "Match",
    "case": "Case",
    "import": "Import",
    "include": "Include",
    "from": "From",
    "use": "Use",
    "true": "True",
    "false": "False",
    "yes": "True",
    "no": "False",
    "on": "True",
    "off": "False",
    "none": "None",
    "null": "None",
    "nil": "None",
    "nothing": "None",
    "and": "And",
    "or": "Or",
    "not": "Not",
}

_BLOCK_OPENERS = {
    "Function",
    "When",
    "While",
    "Repeat",
    "Class",
    "Try",
    "With",
    "Match",
}

_MIDDLE_BLOCK_KEYWORDS = {
    "Otherwise",
    "ElseIf",
    "Except",
    "Catch",
    "Finally",
    "Case",
}


class _Replacement(NamedTuple):

    start: int
    end: int
    text: str


class FormatterError(Exception):
    pass


class PsuedoPYFormatter:

    def __init__(self) -> None:
        self._case_lookup = _CANONICAL_FORMS

    def format(self, source: str) -> str:
        ppy_lines = source.splitlines()
        if not ppy_lines:
            return ""

        replacements_by_line: Dict[int, List[_Replacement]] = {}

        try:
            tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        except tokenize.TokenError as exc:
            raise FormatterError(f"Tokenization error: {exc}") from exc

        for token in tokens:
            if token.type != tokenize.NAME:
                continue

            original = token.string
            canonical = self._case_lookup.get(original.lower())
            if canonical and canonical != original:
                replacements_by_line.setdefault(token.start[0], []).append(
                    _Replacement(token.start[1], token.end[1], canonical)
                )

        output_lines: List[str] = []
        indent_level = 0
        indent_unit = "    "

        for idx, original_line in enumerate(ppy_lines, start=1):
            raw = original_line.rstrip()
            stripped = raw.strip()

            if not stripped:
                output_lines.append("")
                continue

            line = self._apply_replacements(raw, replacements_by_line.get(idx, []))
            stripped = line.strip()

            if not stripped:
                output_lines.append("")
                continue

            first_word = stripped.split()[0] if stripped else ""
            canonical_word = self._case_lookup.get(first_word.lower(), first_word)

            if canonical_word == "End":
                indent_level = max(indent_level - 1, 0)
                output_lines.append(f"{indent_unit * indent_level}{stripped}")
                continue

            if canonical_word in _MIDDLE_BLOCK_KEYWORDS:
                align = max(indent_level - 1, 0)
                output_lines.append(f"{indent_unit * align}{stripped}")
                continue

            output_lines.append(f"{indent_unit * indent_level}{stripped}")

            if canonical_word in _BLOCK_OPENERS:
                indent_level += 1

        return "\n".join(output_lines).rstrip() + "\n"

    @staticmethod
    def _apply_replacements(
        line: str,
        replacements: List[_Replacement] | None,
    ) -> str:
        if not replacements:
            return line

        replacements = sorted(replacements, key=lambda r: r.start)
        parts: List[str] = []
        last = 0
        for repl in replacements:
            parts.append(line[last : repl.start])
            parts.append(repl.text)
            last = repl.end
        parts.append(line[last:])
        return "".join(parts)

    def format_file(self, path: str | Path) -> None:
        target = Path(path)
        source = target.read_text(encoding="utf-8")
        formatted = self.format(source)
        target.write_text(formatted, encoding="utf-8")
