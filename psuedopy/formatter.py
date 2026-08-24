from __future__ import annotations

import io
import re
import tokenize
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from psuedopy.errors import FormatterError, TranspilerError
from psuedopy.grammar import Grammar
from psuedopy.parser import (
    SyntaxParser,
    multiline_string_continuation_lines,
    normalize_surface_syntax,
)


@dataclass(frozen=True)
class _Replacement:
    start: int
    end: int
    text: str


@dataclass
class _FormatFrame:
    kind: str
    indent: int
    body_indent: int


class PsuedoPYFormatter:
    """Canonicalize keyword casing and explicit-End block indentation."""

    _OPENERS = {
        "function": "function",
        "func": "function",
        "define": "function",
        "def": "function",
        "procedure": "function",
        "method": "function",
        "constructor": "function",
        "class": "class",
        "interface": "interface",
        "enum": "enum",
        "when": "if",
        "if": "if",
        "while": "while",
        "loop": "while",
        "repeat": "for",
        "for": "for",
        "foreach": "for",
        "try": "try",
        "using": "with",
        "with": "with",
        "match": "match",
        "switch": "match",
    }
    _IF_BRANCHES = {"otherwise", "else", "elseif", "otherwiseif", "elif"}
    _TRY_BRANCHES = {"catch", "except", "finally"}
    _CASE_BRANCHES = {"case", "default"}

    def __init__(self, grammar_file: str | Path | None = None) -> None:
        self.grammar = Grammar.load(grammar_file)

    def format(self, source: str) -> str:
        if not source.splitlines():
            return ""
        canonical = normalize_surface_syntax(self._canonicalize(source))
        try:
            SyntaxParser(self.grammar).parse(canonical)
        except TranspilerError as exc:
            raise FormatterError(
                exc.message,
                line=exc.location.line if exc.location else None,
                column=exc.location.column if exc.location else 1,
                source_line=exc.location.source_line if exc.location else None,
            ) from exc

        output: list[str] = []
        stack: list[_FormatFrame] = []
        protected_lines = multiline_string_continuation_lines(canonical)
        bracket_depth = 0
        for line_number, original in enumerate(canonical.splitlines(), start=1):
            if line_number in protected_lines:
                output.append(original)
                continue
            stripped = original.strip()
            if not stripped:
                output.append("")
                continue
            if stripped.startswith("#"):
                output.append(self._indent(self._current_indent(stack), stripped))
                continue

            was_continuation = bracket_depth > 0
            bracket_depth = max(0, bracket_depth + self._bracket_delta(stripped))
            if was_continuation:
                extra = 0 if stripped.startswith((")", "]", "}")) else 1
                output.append(
                    self._indent(self._current_indent(stack) + extra, stripped)
                )
                continue

            first, second = self._first_two_words(stripped)
            lowered = first.casefold()
            if lowered in {"public", "private", "protected", "static"}:
                words = stripped.split()
                index = 0
                while index < len(words) and words[index].casefold() in {
                    "public",
                    "private",
                    "protected",
                    "static",
                }:
                    index += 1
                if index < len(words):
                    lowered = words[index].casefold()
                    second = words[index + 1] if index + 1 < len(words) else ""
            if lowered == "end":
                if stack:
                    frame = stack.pop()
                    output.append(self._indent(frame.indent, stripped))
                else:
                    output.append(stripped)
                continue

            if lowered in self._IF_BRANCHES or lowered in self._TRY_BRANCHES:
                if (
                    stack
                    and stack[-1].kind == "match"
                    and lowered in {"otherwise", "else"}
                ):
                    frame = stack[-1]
                    output.append(self._indent(frame.indent + 1, stripped))
                    frame.body_indent = frame.indent + 2
                elif stack:
                    frame = stack[-1]
                    output.append(self._indent(frame.indent, stripped))
                    frame.body_indent = frame.indent + 1
                else:
                    output.append(stripped)
                continue

            if lowered in self._CASE_BRANCHES:
                if stack:
                    frame = stack[-1]
                    output.append(self._indent(frame.indent + 1, stripped))
                    frame.body_indent = frame.indent + 2
                else:
                    output.append(stripped)
                continue

            indent = self._current_indent(stack)
            output.append(self._indent(indent, stripped))
            opener = self._OPENERS.get(lowered)
            if lowered == "async" and second.casefold() in {
                "function",
                "func",
                "define",
                "def",
                "procedure",
                "method",
            }:
                opener = "function"
            if opener:
                stack.append(_FormatFrame(opener, indent, indent + 1))

        return "\n".join(output).rstrip() + "\n"

    def _canonicalize(self, source: str) -> str:
        lines = source.splitlines()
        replacements: dict[int, list[_Replacement]] = {}
        shadowed = self._collect_shadowed_names(source)
        import_lines = {
            number
            for number, line in enumerate(lines, start=1)
            if re.match(r"^\s*(?:Import|Include|Use|From)\b", line, re.IGNORECASE)
        }
        try:
            tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
        except (tokenize.TokenError, IndentationError) as exc:
            raise FormatterError(f"Tokenization failed: {exc}") from exc

        previous_significant: tokenize.TokenInfo | None = None
        for token in tokens:
            if token.type == tokenize.NAME:
                after_dot = (
                    previous_significant is not None
                    and previous_significant.type == tokenize.OP
                    and previous_significant.string == "."
                )
                canonical = self.grammar.canonical(token.string)
                spec = self.grammar.resolve(token.string)
                protected_import_name = bool(
                    token.start[0] in import_lines
                    and spec
                    and spec.category not in {"import", "import_modifier"}
                )
                is_shadowed = bool(
                    spec
                    and token.string in shadowed
                    and (
                        spec.category in {"expression", "type"}
                        or spec.python_target in {"print", "input"}
                    )
                )
                if (
                    canonical
                    and not after_dot
                    and not is_shadowed
                    and not protected_import_name
                    and canonical != token.string
                ):
                    replacements.setdefault(token.start[0], []).append(
                        _Replacement(token.start[1], token.end[1], canonical)
                    )
            if token.type not in {
                tokenize.ENCODING,
                tokenize.ENDMARKER,
                tokenize.INDENT,
                tokenize.DEDENT,
                tokenize.NEWLINE,
                tokenize.NL,
                tokenize.COMMENT,
            }:
                previous_significant = token

        output = []
        for number, line in enumerate(lines, start=1):
            output.append(self._apply(line, replacements.get(number, [])))
        return "\n".join(output)

    @staticmethod
    def _collect_shadowed_names(source: str) -> set[str]:
        names: set[str] = set()
        for line in source.splitlines():
            stripped = line.strip()
            declaration = re.match(
                r"^(?:Let|Var|Declare|Const|Set|Field|Type)\s+([A-Za-z_]\w*)",
                stripped,
                re.IGNORECASE,
            )
            if declaration:
                names.add(declaration.group(1))
            callable_match = re.match(
                r"^(?:Async\s+)?(?:Function|Func|Define|Def|Procedure|Method)\s+"
                r"([A-Za-z_]\w*)\s*\((.*)\)",
                stripped,
                re.IGNORECASE,
            )
            if callable_match:
                names.add(callable_match.group(1))
                for parameter in callable_match.group(2).split(","):
                    match = re.match(r"\s*[*]{0,2}([A-Za-z_]\w*)", parameter)
                    if match:
                        names.add(match.group(1))
            named_type = re.match(
                r"^(?:Class|Interface|Enum)\s+([A-Za-z_]\w*)",
                stripped,
                re.IGNORECASE,
            )
            if named_type:
                names.add(named_type.group(1))
            loop_target = re.match(
                r"^(?:Repeat|ForEach)\s+([A-Za-z_]\w*)\s+(?:=|In\b)",
                stripped,
                re.IGNORECASE,
            )
            if not loop_target:
                loop_target = re.match(
                    r"^For\s*\(\s*(?:Let\s+|Var\s+)?([A-Za-z_]\w*)\s*=",
                    stripped,
                    re.IGNORECASE,
                )
            if loop_target:
                names.add(loop_target.group(1))
            if re.match(r"^(?:Import|Include|Use|From)\b", stripped, re.IGNORECASE):
                aliases = re.findall(
                    r"\bAs\s+([A-Za-z_]\w*)", stripped, flags=re.IGNORECASE
                )
                names.update(aliases)
                from_import = re.match(
                    r"^From\s+.+?\s+Import\s+(.+)$", stripped, re.IGNORECASE
                )
                if from_import:
                    for item in from_import.group(1).split(","):
                        imported = re.match(r"\s*([A-Za-z_]\w*)", item)
                        if imported and not re.search(r"\bAs\b", item, re.IGNORECASE):
                            names.add(imported.group(1))
        return names

    @staticmethod
    def _apply(line: str, replacements: Sequence[_Replacement]) -> str:
        if not replacements:
            return line
        parts: list[str] = []
        last = 0
        for replacement in sorted(replacements, key=lambda item: item.start):
            parts.append(line[last : replacement.start])
            parts.append(replacement.text)
            last = replacement.end
        parts.append(line[last:])
        return "".join(parts)

    @staticmethod
    def _first_two_words(line: str) -> tuple[str, str]:
        first = re.match(r"^([A-Za-z_]\w*)", line)
        if not first:
            return "", ""
        remainder = line[first.end() :].lstrip()
        second = re.match(r"^([A-Za-z_]\w*)", remainder)
        return first.group(1), second.group(1) if second else ""

    @staticmethod
    def _current_indent(stack: Sequence[_FormatFrame]) -> int:
        return stack[-1].body_indent if stack else 0

    @staticmethod
    def _indent(level: int, line: str) -> str:
        return f"{'    ' * level}{line}" if line else ""

    @staticmethod
    def _bracket_delta(line: str) -> int:
        quote: str | None = None
        escaped = False
        delta = 0
        for char in line:
            if quote is not None:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
                continue
            if char in {"'", '"'}:
                quote = char
            elif char == "#":
                break
            elif char in "([{":
                delta += 1
            elif char in ")]}":
                delta -= 1
        return delta

    def format_file(self, path: str | Path) -> bool:
        target = Path(path)
        source = target.read_text(encoding="utf-8")
        formatted = self.format(source)
        if formatted == source:
            return False
        target.write_text(formatted, encoding="utf-8", newline="\n")
        return True


__all__ = ["FormatterError", "PsuedoPYFormatter"]
