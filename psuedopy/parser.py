from __future__ import annotations

import ast
import io
import re
import tokenize
from collections.abc import Sequence, Set
from dataclasses import dataclass, field

from psuedopy.errors import IncompleteInputError, TranspilerError
from psuedopy.grammar import Grammar

_FIRST_WORD_RE = re.compile(r"^([A-Za-z_]\w*)\b(.*)$", re.UNICODE | re.DOTALL)
_ASSIGNMENT_RE = re.compile(r"^([A-Za-z_]\w*)\s*(?::[^=]+)?\s*(?:[+\-*/%]?=|:=)")


@dataclass(frozen=True)
class LogicalLine:
    """One PsuedoPY statement, possibly spanning several physical lines."""

    text: str
    start_line: int
    end_line: int


def normalize_surface_syntax(source: str) -> str:
    """Normalize C++-style comments/braces without touching quoted text."""

    normalized: list[str] = []
    block_words = {
        "async",
        "class",
        "case",
        "catch",
        "default",
        "enum",
        "else",
        "elseif",
        "finally",
        "for",
        "foreach",
        "function",
        "if",
        "interface",
        "loop",
        "match",
        "method",
        "otherwise",
        "otherwiseif",
        "procedure",
        "repeat",
        "switch",
        "try",
        "using",
        "when",
        "while",
    }
    protected = multiline_string_continuation_lines(source)
    for number, original in enumerate(source.splitlines(), start=1):
        if number in protected:
            normalized.append(original)
            continue
        line = _convert_cpp_comment(original)
        stripped = line.strip()
        joined_branch = re.match(
            r"^}\s*(Else|ElseIf|Otherwise|OtherwiseIf|Catch|Except|Finally)\b(.*)$",
            stripped,
            flags=re.IGNORECASE,
        )
        if joined_branch:
            indentation = line[: len(line) - len(line.lstrip())]
            line = f"{indentation}{joined_branch.group(1)}{joined_branch.group(2)}"
            stripped = line.strip()
        if stripped == "}":
            normalized.append(f"{line[: len(line) - len(line.lstrip())]}End")
            continue
        first = stripped.split(None, 1)[0].casefold() if stripped else ""
        brace_match = re.search(r"\{\s*(#.*)?$", line)
        if first in block_words and brace_match:
            comment = brace_match.group(1)
            line = line[: brace_match.start()].rstrip()
            if comment:
                line = f"{line}  {comment}"
        normalized.append(line)
    return "\n".join(normalized)


def logical_lines(source: str) -> tuple[list[LogicalLine], int | None]:
    """Group bracketed/backslash continuations into logical statements."""

    lines = source.splitlines() or [""]
    deltas = [0] * (len(lines) + 1)
    string_continuations: set[int] = set()
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for token in tokens:
            if token.type == tokenize.OP:
                if token.string in "([{":
                    deltas[token.start[0]] += 1
                elif token.string in ")]}":
                    deltas[token.start[0]] -= 1
            if token.type == tokenize.STRING and token.end[0] > token.start[0]:
                string_continuations.update(range(token.start[0], token.end[0]))
    except (tokenize.TokenError, IndentationError):
        # Tokens yielded before an incomplete final statement still give us its depth.
        pass

    result: list[LogicalLine] = []
    buffer: list[str] = []
    start = 1
    depth = 0
    unclosed_at: int | None = None
    for number, line in enumerate(lines, start=1):
        if not buffer:
            start = number
        buffer.append(line)
        depth += deltas[number]
        if depth > 0 and unclosed_at is None:
            unclosed_at = start
        continued = (
            depth > 0 or number in string_continuations or line.rstrip().endswith("\\")
        )
        if continued:
            continue
        result.append(LogicalLine("\n".join(buffer), start, number))
        buffer = []
        unclosed_at = None
    if buffer:
        result.append(LogicalLine("\n".join(buffer), start, len(lines)))
    return result, unclosed_at


def _convert_cpp_comment(line: str) -> str:
    quote: str | None = None
    triple = False
    escaped = False
    index = 0
    while index < len(line):
        if quote is not None:
            marker = quote * (3 if triple else 1)
            if escaped:
                escaped = False
            elif line[index] == "\\":
                escaped = True
            elif line.startswith(marker, index):
                index += len(marker)
                quote = None
                triple = False
                continue
            index += 1
            continue
        if line[index] in {"'", '"'}:
            quote = line[index]
            triple = line.startswith(quote * 3, index)
            index += 3 if triple else 1
            continue
        if line[index] == "#":
            return line
        if line.startswith("//", index):
            return f"{line[:index]}# {line[index + 2 :].lstrip()}"
        index += 1
    return line


def multiline_string_continuation_lines(source: str) -> set[int]:
    """Return physical lines after the first line of every multiline string."""

    protected: set[int] = set()
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for token in tokens:
            if token.type == tokenize.STRING and token.end[0] > token.start[0]:
                protected.update(range(token.start[0] + 1, token.end[0] + 1))
    except (tokenize.TokenError, IndentationError):
        return protected
    return protected


@dataclass(frozen=True)
class GeneratedLine:
    python: str
    source_line: int
    source_end: int | None = None


@dataclass(frozen=True)
class ParsedProgram:
    lines: Sequence[GeneratedLine]
    required_helpers: set[str] = field(default_factory=set)


@dataclass
class _BlockFrame:
    kind: str
    opener_line: int
    indent: int
    body_indent: int
    has_body: bool = False
    branch_started: bool = False
    else_seen: bool = False
    finally_seen: bool = False
    scope_opened: bool = False


class ExpressionTranslator:
    """Translate reserved words inside expressions without touching strings/comments."""

    _EXPRESSION_CATEGORIES = {
        "operator",
        "literal",
        "import_modifier",
        "expression",
    }
    _CALL_TARGETS = {"print", "input"}

    def __init__(self, grammar: Grammar) -> None:
        self.grammar = grammar

    def translate(
        self,
        text: str,
        *,
        condition: bool = False,
        bound_names: Set[str] = frozenset(),
    ) -> str:
        text = self._rewrite_cpp_operators(text)
        text = self._rewrite_advanced_expression(text, bound_names)
        replacements: list[tuple[int, int, str]] = []
        try:
            tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
        except (tokenize.TokenError, IndentationError):
            tokens = []

        previous_significant: tokenize.TokenInfo | None = None
        for token in tokens:
            if token.type == tokenize.NAME:
                spec = self.grammar.resolve(token.string)
                after_dot = (
                    previous_significant is not None
                    and previous_significant.type == tokenize.OP
                    and previous_significant.string == "."
                )
                if (
                    spec
                    and not after_dot
                    and not (
                        token.string in bound_names
                        and (
                            spec.category == "expression"
                            or spec.python_target in self._CALL_TARGETS
                        )
                    )
                    and (
                        spec.category in self._EXPRESSION_CATEGORIES
                        or spec.python_target in self._CALL_TARGETS
                    )
                ):
                    start = self._absolute_offset(text, *token.start)
                    end = self._absolute_offset(text, *token.end)
                    replacements.append((start, end, spec.python_target))
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

        if tokens:
            translated = self._apply(text, replacements)
        else:
            translated = self._fallback_translate(text)
        translated = self._replace_not_equal(translated)
        if condition:
            translated = self._replace_condition_equals(translated)
        return translated

    def _rewrite_advanced_expression(self, text: str, bound_names: Set[str]) -> str:
        stripped = text.strip()
        nested = self._rewrite_nested_advanced(stripped, bound_names)
        if nested != stripped:
            stripped = nested
        arrow = self._find_top_level(stripped, "=>")
        if arrow is not None:
            parameters = stripped[:arrow].strip()
            body = stripped[arrow + 2 :].strip()
            if parameters.startswith("(") and parameters.endswith(")"):
                parameters = parameters[1:-1]
            parameters = self._strip_lambda_parameter_types(parameters)
            translated_body = self.translate(body, bound_names=bound_names)
            return f"lambda {parameters}: {translated_body}"

        coalesce = self._find_top_level(stripped, "??")
        if coalesce is not None:
            left = stripped[:coalesce].strip()
            right = stripped[coalesce + 2 :].strip()
            translated_left = self.translate(left, bound_names=bound_names)
            translated_right = self.translate(right, bound_names=bound_names)
            return (
                "(lambda __ppy_value: __ppy_value if __ppy_value is not None "
                f"else {translated_right})({translated_left})"
            )

        question = self._find_top_level(stripped, "?")
        if question is not None:
            colon = self._find_top_level(stripped, ":", start=question + 1)
            if colon is not None:
                condition = stripped[:question].strip()
                truthy = stripped[question + 1 : colon].strip()
                falsy = stripped[colon + 1 :].strip()
                translated_condition = self.translate(
                    condition, condition=True, bound_names=bound_names
                )
                return (
                    f"({self.translate(truthy, bound_names=bound_names)} if "
                    f"{translated_condition} "
                    f"else {self.translate(falsy, bound_names=bound_names)})"
                )
        return stripped

    def _rewrite_nested_advanced(self, text: str, bound_names: Set[str]) -> str:
        stack: list[int] = []
        quote: str | None = None
        escaped = False
        pairs: list[tuple[int, int]] = []
        for index, char in enumerate(text):
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
            elif char == "(":
                stack.append(index)
            elif char == ")" and stack:
                pairs.append((stack.pop(), index))
        for start, end in pairs:
            inner = text[start + 1 : end]
            if any(
                self._find_top_level(inner, marker) is not None
                for marker in ("=>", "??", "?")
            ):
                replacement = f"({self.translate(inner, bound_names=bound_names)})"
                return text[:start] + replacement + text[end + 1 :]
        return text

    @staticmethod
    def _strip_lambda_parameter_types(parameters: str) -> str:
        cleaned: list[str] = []
        for parameter in parameters.split(","):
            item = parameter.strip()
            if not item:
                continue
            name, separator, remainder = item.partition(":")
            if separator:
                default = ""
                if "=" in remainder:
                    _, default_value = remainder.split("=", 1)
                    default = f"={default_value.strip()}"
                item = f"{name.strip()}{default}"
            cleaned.append(item)
        return ", ".join(cleaned)

    @staticmethod
    def _find_top_level(text: str, marker: str, *, start: int = 0) -> int | None:
        depth = 0
        quote: str | None = None
        escaped = False
        index = start
        while index <= len(text) - len(marker):
            char = text[index]
            if quote is not None:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
                index += 1
                continue
            if char in {"'", '"'}:
                quote = char
                index += 1
                continue
            if char in "([{":
                depth += 1
            elif char in ")]}":
                depth = max(0, depth - 1)
            elif depth == 0 and text.startswith(marker, index):
                return index
            index += 1
        return None

    @staticmethod
    def _rewrite_cpp_operators(text: str) -> str:
        output: list[str] = []
        quote: str | None = None
        escaped = False
        index = 0
        while index < len(text):
            char = text[index]
            if quote is not None:
                output.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
                index += 1
                continue
            if char in {"'", '"'}:
                quote = char
                output.append(char)
                index += 1
                continue
            if char == "#":
                output.append(text[index:])
                break
            if text.startswith("&&", index):
                output.append(" and ")
                index += 2
                continue
            if text.startswith("||", index):
                output.append(" or ")
                index += 2
                continue
            if char == "!" and not text.startswith("!=", index):
                output.append("not ")
                index += 1
                continue
            output.append(char)
            index += 1
        return "".join(output)

    @staticmethod
    def _absolute_offset(text: str, line: int, column: int) -> int:
        starts = [0]
        for match in re.finditer("\n", text):
            starts.append(match.end())
        if line <= 0 or line > len(starts):
            return len(text)
        return starts[line - 1] + column

    @staticmethod
    def _apply(text: str, replacements: Sequence[tuple[int, int, str]]) -> str:
        if not replacements:
            return text
        output: list[str] = []
        last = 0
        for start, end, replacement in sorted(replacements):
            output.append(text[last:start])
            output.append(replacement)
            last = end
        output.append(text[last:])
        return "".join(output)

    def _fallback_translate(self, text: str) -> str:
        output: list[str] = []
        index = 0
        quote: str | None = None
        escaped = False
        previous_non_space = ""
        while index < len(text):
            char = text[index]
            if quote is not None:
                output.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
                index += 1
                continue
            if char in {"'", '"'}:
                quote = char
                output.append(char)
                index += 1
                continue
            if char == "#":
                output.append(text[index:])
                break
            if char.isalpha() or char == "_":
                end = index + 1
                while end < len(text) and (text[end].isalnum() or text[end] == "_"):
                    end += 1
                name = text[index:end]
                spec = self.grammar.resolve(name)
                if (
                    spec
                    and previous_non_space != "."
                    and (
                        spec.category in self._EXPRESSION_CATEGORIES
                        or spec.python_target in self._CALL_TARGETS
                    )
                ):
                    output.append(spec.python_target)
                else:
                    output.append(name)
                previous_non_space = output[-1][-1:] or previous_non_space
                index = end
                continue
            output.append(char)
            if not char.isspace():
                previous_non_space = char
            index += 1
        return "".join(output)

    @staticmethod
    def _replace_not_equal(text: str) -> str:
        output: list[str] = []
        quote: str | None = None
        escaped = False
        index = 0
        while index < len(text):
            char = text[index]
            if quote is not None:
                output.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
                index += 1
                continue
            if char in {"'", '"'}:
                quote = char
                output.append(char)
                index += 1
                continue
            if char == "#":
                output.append(text[index:])
                break
            if text[index : index + 2] == "<>":
                output.append("!=")
                index += 2
                continue
            output.append(char)
            index += 1
        return "".join(output)

    @staticmethod
    def _replace_condition_equals(text: str) -> str:
        output: list[str] = []
        quote: str | None = None
        escaped = False
        depth = 0
        for index, char in enumerate(text):
            if quote is not None:
                output.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
                continue
            if char in {"'", '"'}:
                quote = char
                output.append(char)
                continue
            if char == "#":
                output.append(text[index:])
                break
            if char in "([{":
                depth += 1
            elif char in ")]}":
                depth = max(0, depth - 1)
            if char == "=" and depth == 0:
                previous = text[index - 1] if index else ""
                following = text[index + 1] if index + 1 < len(text) else ""
                if previous not in "<>=!:" and following != "=":
                    output.append("==")
                    continue
            output.append(char)
        return "".join(output)


class SyntaxParser:
    """Parse PsuedoPY's explicit-End block structure into generated Python lines."""

    _FUNCTION_WORDS = {"function", "func", "define", "def", "procedure", "method"}
    _IF_WORDS = {"when", "if"}
    _ELIF_WORDS = {"elseif", "otherwiseif", "elif"}
    _ELSE_WORDS = {"otherwise", "else"}
    _WHILE_WORDS = {"while", "loop"}
    _FOR_WORDS = {"repeat", "for", "foreach"}
    _IMPORT_WORDS = {"import", "include", "use"}
    _DECLARATION_WORDS = {"let", "set", "var", "declare", "const"}
    _MODIFIER_WORDS = {"public", "private", "protected", "static"}
    _SIMPLE_KEYWORDS: dict[str, str] = {
        "return": "return",
        "break": "break",
        "continue": "continue",
        "pass": "pass",
        "raise": "raise",
        "throw": "raise",
        "assert": "assert",
        "check": "assert",
        "delete": "del",
        "del": "del",
        "global": "global",
        "nonlocal": "nonlocal",
        "yield": "yield",
    }

    def __init__(self, grammar: Grammar) -> None:
        self.grammar = grammar
        self.expressions = ExpressionTranslator(grammar)
        self._binding_scopes: list[set[str]] = [set()]

    def parse(self, source: str, *, allow_incomplete: bool = False) -> ParsedProgram:
        source_lines = source.splitlines()
        if not source_lines:
            source_lines = [""]
        normalized_source = normalize_surface_syntax(source)
        output: list[GeneratedLine] = []
        stack: list[_BlockFrame] = []
        helpers: set[str] = set()
        constant_scopes: list[set[str]] = [set()]
        self._binding_scopes = [set()]
        statements, unclosed_line = logical_lines(normalized_source)
        if unclosed_line is not None:
            exc_type = IncompleteInputError if allow_incomplete else TranspilerError
            raise exc_type(
                "Multiline expression is missing a closing bracket",
                line=unclosed_line,
                source_line=source_lines[unclosed_line - 1],
            )

        for statement in statements:
            line_number = statement.start_line
            original = statement.text
            source_end = statement.end_line
            if "\n" in original:
                code, comment = original, ""
            else:
                code, comment = self._split_comment(original)
            stripped = code.strip()
            if not stripped:
                rendered = comment.strip() if comment else ""
                if rendered and stack:
                    rendered = self._indent(stack[-1].body_indent, rendered)
                output.append(GeneratedLine(rendered, line_number, source_end))
                continue

            stripped = self._without_trailing_colon(stripped)
            stripped = self._without_trailing_semicolon(stripped)
            match = _FIRST_WORD_RE.match(stripped)
            if not match:
                self._mark_body(stack, line_number)
                output.append(
                    GeneratedLine(
                        self._indent(self._current_indent(stack), stripped)
                        + self._comment(comment),
                        line_number,
                        source_end,
                    )
                )
                continue

            word = match.group(1)
            lowered = word.casefold()
            rest = match.group(2).strip()
            modifiers: set[str] = set()
            while lowered in self._MODIFIER_WORDS:
                modifiers.add(lowered)
                modifier_match = _FIRST_WORD_RE.match(rest)
                if not modifier_match:
                    self._error(
                        f"{word.title()} requires a declaration",
                        line_number,
                        original,
                    )
                word = modifier_match.group(1)
                lowered = word.casefold()
                rest = modifier_match.group(2).strip()
            if modifiers and (
                not stack or stack[-1].kind not in {"class", "interface", "enum"}
            ):
                self._error(
                    "Access and Static modifiers are only valid inside a type",
                    line_number,
                    original,
                )

            if lowered == "end":
                if self._close_block(stack, rest, line_number, original):
                    constant_scopes.pop()
                    self._binding_scopes.pop()
                rendered = comment.strip() if comment else ""
                output.append(
                    GeneratedLine(
                        self._indent(self._current_indent(stack), rendered)
                        if rendered
                        else "",
                        line_number,
                        source_end,
                    )
                )
                continue

            if lowered in self._ELIF_WORDS or lowered in self._ELSE_WORDS:
                rendered = self._parse_if_branch(
                    stack, lowered, rest, line_number, original
                )
                output.append(
                    GeneratedLine(
                        rendered + self._comment(comment), line_number, source_end
                    )
                )
                continue

            if lowered in {"catch", "except", "finally"}:
                rendered = self._parse_try_branch(
                    stack, lowered, rest, line_number, original
                )
                output.append(
                    GeneratedLine(
                        rendered + self._comment(comment), line_number, source_end
                    )
                )
                continue

            if lowered in {"case", "default"}:
                rendered = self._parse_case_branch(
                    stack, lowered, rest, line_number, original
                )
                output.append(
                    GeneratedLine(
                        rendered + self._comment(comment), line_number, source_end
                    )
                )
                continue

            self._mark_body(stack, line_number)
            indent = self._current_indent(stack)

            if lowered == "async" and rest:
                async_match = _FIRST_WORD_RE.match(rest)
                if (
                    async_match
                    and async_match.group(1).casefold() in self._FUNCTION_WORDS
                ):
                    function_rest = async_match.group(2).strip()
                    rendered, bindings = self._function_header(
                        function_rest, line_number, original, async_=True
                    )
                    self._register_function_binding(function_rest)
                    self._push_block(stack, "function", line_number, indent, scope=True)
                    constant_scopes.append(set())
                    self._binding_scopes.append(bindings)
                    output.append(
                        GeneratedLine(
                            self._indent(indent, rendered) + self._comment(comment),
                            line_number,
                            source_end,
                        )
                    )
                    continue

            if lowered in self._FUNCTION_WORDS:
                rendered, bindings = self._function_header(rest, line_number, original)
                if "static" in modifiers:
                    rendered = f"@staticmethod\n{rendered}"
                self._register_function_binding(rest)
                self._push_block(stack, "function", line_number, indent, scope=True)
                constant_scopes.append(set())
                self._binding_scopes.append(bindings)
            elif lowered == "constructor":
                rendered, bindings = self._constructor_header(
                    rest, line_number, original
                )
                self._push_block(stack, "function", line_number, indent, scope=True)
                constant_scopes.append(set())
                self._binding_scopes.append(bindings)
            elif lowered == "class":
                rendered, class_name = self._class_header(rest, line_number, original)
                self._binding_scopes[-1].add(class_name)
                self._push_block(stack, "class", line_number, indent, scope=True)
                constant_scopes.append(set())
                self._binding_scopes.append({"This"})
            elif lowered == "interface":
                rendered, interface_name = self._class_header(
                    rest, line_number, original, base="__PpyProtocol"
                )
                helpers.add("protocol")
                self._binding_scopes[-1].add(interface_name)
                self._push_block(stack, "interface", line_number, indent, scope=True)
                constant_scopes.append(set())
                self._binding_scopes.append({"This"})
            elif lowered == "enum":
                rendered, enum_name = self._class_header(
                    rest, line_number, original, base="__PpyEnum"
                )
                helpers.add("enum")
                self._binding_scopes[-1].add(enum_name)
                self._push_block(stack, "enum", line_number, indent, scope=True)
                constant_scopes.append(set())
                self._binding_scopes.append(set())
            elif lowered in self._IF_WORDS:
                condition = self._remove_suffix_word(rest, "then")
                self._require(
                    condition, "When requires a condition", line_number, original
                )
                rendered = f"if {self._translate(condition, condition=True)}:"
                self._push_block(stack, "if", line_number, indent)
            elif lowered in self._WHILE_WORDS:
                condition = self._remove_suffix_word(rest, "then")
                if condition.casefold() == "forever":
                    condition = "True"
                self._require(
                    condition, "While requires a condition", line_number, original
                )
                rendered = f"while {self._translate(condition, condition=True)}:"
                self._push_block(stack, "while", line_number, indent)
            elif lowered in self._FOR_WORDS:
                rendered, helper = self._repeat_header(
                    rest,
                    line_number,
                    original,
                    constant_scopes[-1],
                )
                if helper:
                    helpers.add(helper)
                self._push_block(stack, "for", line_number, indent)
            elif lowered == "try":
                if rest:
                    self._error(
                        "Try does not accept an expression", line_number, original
                    )
                rendered = "try:"
                self._push_block(stack, "try", line_number, indent)
            elif lowered in {"using", "with"}:
                self._require(
                    rest, "Using requires a context expression", line_number, original
                )
                rendered = f"with {self._translate(rest)}:"
                self._push_block(stack, "with", line_number, indent)
            elif lowered in {"match", "switch"}:
                self._require(rest, "Match requires a subject", line_number, original)
                subject = self._translate(self._strip_wrapping_parens(rest))
                rendered = f"match {subject}:"
                self._push_block(stack, "match", line_number, indent)
            elif lowered == "from":
                rendered = self._from_import(rest, line_number, original)
                self._register_import_bindings(rest, from_import=True)
            elif lowered in self._IMPORT_WORDS:
                self._require(rest, "Import requires a module", line_number, original)
                rendered = f"import {self._import_clause(rest)}"
                self._register_import_bindings(rest, from_import=False)
            elif lowered == "type":
                rendered = self._type_alias(rest, line_number, original)
            elif lowered == "field":
                rendered = self._field_declaration(rest, line_number, original, stack)
            elif lowered in self._DECLARATION_WORDS:
                rendered = self._declaration(
                    lowered, rest, line_number, original, constant_scopes[-1]
                )
            elif lowered in self._SIMPLE_KEYWORDS:
                rendered = self._simple_statement(
                    lowered, rest, line_number, original, stack
                )
            else:
                rendered = self._expression_statement(stripped, line_number, original)
                self._check_constant_assignment(
                    rendered, constant_scopes[-1], line_number, original
                )

            output.append(
                GeneratedLine(
                    self._indent(indent, rendered) + self._comment(comment),
                    line_number,
                    source_end,
                )
            )

        if stack:
            frame = stack[-1]
            message = f"{frame.kind.title()} block opened here needs End"
            exc_type = IncompleteInputError if allow_incomplete else TranspilerError
            raise exc_type(
                message,
                line=frame.opener_line,
                source_line=source_lines[frame.opener_line - 1],
            )

        return ParsedProgram(lines=output, required_helpers=helpers)

    def _translate(self, text: str, *, condition: bool = False) -> str:
        return self.expressions.translate(
            text,
            condition=condition,
            bound_names=self._visible_bindings(),
        )

    def _visible_bindings(self) -> set[str]:
        visible: set[str] = set()
        for scope in self._binding_scopes:
            visible.update(scope)
        return visible

    def _push_block(
        self,
        stack: list[_BlockFrame],
        kind: str,
        line: int,
        indent: int,
        *,
        scope: bool = False,
    ) -> None:
        stack.append(
            _BlockFrame(
                kind=kind,
                opener_line=line,
                indent=indent,
                body_indent=indent + 1,
                scope_opened=scope,
            )
        )

    def _close_block(
        self,
        stack: list[_BlockFrame],
        label: str,
        line: int,
        source_line: str,
    ) -> bool:
        if not stack:
            self._error("End has no matching open block", line, source_line)
        frame = stack[-1]
        expected = label.casefold().strip()
        aliases = {
            "function": {
                "function",
                "func",
                "procedure",
                "method",
                "constructor",
                "def",
            },
            "for": {"for", "repeat", "foreach"},
            "if": {"if", "when"},
            "while": {"while", "loop"},
            "match": {"match", "switch"},
        }
        if expected and expected not in aliases.get(frame.kind, {frame.kind}):
            self._error(
                f"End {label} does not match open {frame.kind.title()} block",
                line,
                source_line,
            )
        if frame.kind == "match" and not frame.branch_started:
            self._error("Match must contain at least one Case", line, source_line)
        if frame.kind == "try" and not frame.branch_started:
            self._error("Try must contain Catch or Finally", line, source_line)
        if not frame.has_body:
            self._error(
                f"{frame.kind.title()} branch is empty; use Pass if intentional",
                line,
                source_line,
            )
        return stack.pop().scope_opened

    def _parse_if_branch(
        self,
        stack: list[_BlockFrame],
        word: str,
        rest: str,
        line: int,
        source_line: str,
    ) -> str:
        if not stack:
            self._error(f"{word.title()} has no matching When", line, source_line)
        frame = stack[-1]
        if frame.kind == "match" and word in self._ELSE_WORDS:
            return self._parse_case_branch(stack, "default", rest, line, source_line)
        if frame.kind != "if":
            self._error(f"{word.title()} is only valid inside When", line, source_line)
        if not frame.has_body:
            self._error("Previous When branch is empty", line, source_line)
        if word in self._ELIF_WORDS:
            if frame.else_seen:
                self._error("ElseIf cannot appear after Otherwise", line, source_line)
            condition = self._remove_suffix_word(rest, "then")
            self._require(condition, "ElseIf requires a condition", line, source_line)
            result = f"elif {self._translate(condition, condition=True)}:"
        else:
            if frame.else_seen:
                self._error("Only one Otherwise branch is allowed", line, source_line)
            if rest:
                self._error("Otherwise does not accept a condition", line, source_line)
            frame.else_seen = True
            result = "else:"
        frame.has_body = False
        frame.body_indent = frame.indent + 1
        return self._indent(frame.indent, result)

    def _parse_try_branch(
        self,
        stack: list[_BlockFrame],
        word: str,
        rest: str,
        line: int,
        source_line: str,
    ) -> str:
        if not stack or stack[-1].kind != "try":
            self._error(f"{word.title()} is only valid inside Try", line, source_line)
        frame = stack[-1]
        if not frame.has_body:
            self._error("Previous Try branch is empty", line, source_line)
        if word == "finally":
            if rest:
                self._error("Finally does not accept an expression", line, source_line)
            if frame.finally_seen:
                self._error("Only one Finally branch is allowed", line, source_line)
            frame.finally_seen = True
            result = "finally:"
        else:
            if frame.finally_seen:
                self._error("Catch cannot appear after Finally", line, source_line)
            result = "except Exception:"
            if rest:
                result = f"except {self._translate(rest)}:"
                alias = re.search(r"\bAs\s+([A-Za-z_]\w*)\s*$", rest, re.IGNORECASE)
                if alias:
                    self._binding_scopes[-1].add(alias.group(1))
        frame.has_body = False
        frame.branch_started = True
        frame.body_indent = frame.indent + 1
        return self._indent(frame.indent, result)

    def _parse_case_branch(
        self,
        stack: list[_BlockFrame],
        word: str,
        rest: str,
        line: int,
        source_line: str,
    ) -> str:
        if not stack or stack[-1].kind != "match":
            self._error(f"{word.title()} is only valid inside Match", line, source_line)
        frame = stack[-1]
        if frame.branch_started and not frame.has_body:
            self._error("Previous Case branch is empty", line, source_line)
        if word == "default":
            if frame.else_seen:
                self._error("Only one Default branch is allowed", line, source_line)
            if rest:
                self._error("Default does not accept a pattern", line, source_line)
            pattern = "_"
            frame.else_seen = True
        else:
            if frame.else_seen:
                self._error("Case cannot appear after Default", line, source_line)
            self._require(rest, "Case requires a pattern", line, source_line)
            pattern = self._translate(rest)
        frame.branch_started = True
        frame.has_body = False
        frame.body_indent = frame.indent + 2
        return self._indent(frame.indent + 1, f"case {pattern}:")

    def _function_header(
        self,
        rest: str,
        line: int,
        source_line: str,
        *,
        async_: bool = False,
    ) -> tuple[str, set[str]]:
        self._require(
            rest, "Function requires a name and parameter list", line, source_line
        )
        match = re.match(
            r"^([A-Za-z_]\w*)(?:<[^>]+>)?\s*\((.*)\)\s*"
            r"(?:(?:Returns|->|:)\s*(.+))?$",
            rest,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            self._error(
                "Function syntax is `Function name(parameters) Returns Type`",
                line,
                source_line,
            )
        name, raw_parameters, return_type = match.groups()
        parameters, bindings = self._translate_parameters(raw_parameters)
        suffix = f" -> {self._translate_type(return_type)}" if return_type else ""
        prefix = "async def" if async_ else "def"
        return f"{prefix} {name}({parameters}){suffix}:", bindings

    def _constructor_header(
        self, rest: str, line: int, source_line: str
    ) -> tuple[str, set[str]]:
        parameters = rest.strip()
        if not (parameters.startswith("(") and parameters.endswith(")")):
            self._error(
                "Constructor syntax is `Constructor(parameters)`", line, source_line
            )
        raw = parameters[1:-1].strip()
        raw = f"This, {raw}" if raw else "This"
        translated, bindings = self._translate_parameters(raw)
        return f"def __init__({translated}):", bindings

    def _class_header(
        self,
        rest: str,
        line: int,
        source_line: str,
        *,
        base: str | None = None,
    ) -> tuple[str, str]:
        self._require(rest, "Class-like declaration requires a name", line, source_line)
        match = re.match(
            r"^([A-Za-z_]\w*)(?:<[^>]+>)?"
            r"(?:\s+Extends\s+(.+)|\s*(\(.*\)))?$",
            rest,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            self._error("Invalid class declaration", line, source_line)
        name, extends, parenthesized = match.groups()
        inherited = base
        if extends:
            inherited = self._translate(extends.strip())
        elif parenthesized:
            inherited = self._translate(parenthesized[1:-1].strip())
        suffix = f"({inherited})" if inherited else ""
        return f"class {name}{suffix}:", name

    def _translate_parameters(self, raw: str) -> tuple[str, set[str]]:
        parameters: list[str] = []
        bindings: set[str] = set()
        for item in self._split_top_level(raw, ","):
            parameter = item.strip()
            if not parameter:
                continue
            match = re.match(
                r"^([*]{0,2})([A-Za-z_]\w*)(\?)?\s*(?::\s*([^=]+?))?"
                r"(?:\s*=\s*(.+))?$",
                parameter,
                flags=re.DOTALL,
            )
            if not match:
                raise TranspilerError(f"Invalid function parameter: {parameter}")
            stars, name, optional, annotation, default = match.groups()
            bindings.add(name)
            rendered = f"{stars}{'self' if name == 'This' else name}"
            if annotation:
                translated_type = self._translate_type(annotation.strip())
                if optional:
                    translated_type = f"{translated_type} | None"
                rendered += f": {translated_type}"
            elif optional:
                rendered += ": object | None"
            if default:
                rendered += f" = {self._translate(default.strip())}"
            elif optional:
                rendered += " = None"
            parameters.append(rendered)
        return ", ".join(parameters), bindings

    def _translate_type(self, annotation: str) -> str:
        value = annotation.strip()
        while value.endswith("[]"):
            value = f"Array[{value[:-2].strip()}]"
        generic = re.compile(
            r"\b([A-Za-z_]\w*)<([^<>]+)>",
            flags=re.IGNORECASE,
        )
        while generic.search(value):
            value = generic.sub(self._replace_generic_type, value)
        aliases = {
            "Any": "object",
            "Array": "list",
            "Boolean": "bool",
            "Decimal": "float",
            "Integer": "int",
            "List": "list",
            "Map": "dict",
            "Never": "__PpyNever",
            "Number": "int | float",
            "Record": "dict",
            "Set": "set",
            "String": "str",
            "Tuple": "tuple",
            "Unknown": "object",
            "Void": "None",
        }
        for spelling, target in aliases.items():
            if spelling in self._visible_bindings():
                continue
            value = re.sub(rf"\b{spelling}\b", target, value)
        return self._translate(value)

    @staticmethod
    def _replace_generic_type(match: re.Match[str]) -> str:
        name, parameters = match.groups()
        if name.casefold() == "optional":
            return f"({parameters}) | None"
        return f"{name}[{parameters}]"

    @staticmethod
    def _split_top_level(text: str, separator: str) -> list[str]:
        if not text:
            return []
        result: list[str] = []
        depth = 0
        quote: str | None = None
        start = 0
        escaped = False
        for index, char in enumerate(text):
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
            elif char in "([{":
                depth += 1
            elif char in ")]}":
                depth = max(0, depth - 1)
            elif char == separator and depth == 0:
                result.append(text[start:index])
                start = index + 1
        result.append(text[start:])
        return result

    def _repeat_header(
        self,
        rest: str,
        line: int,
        source_line: str,
        constants: set[str],
    ) -> tuple[str, str | None]:
        self._require(rest, "Repeat requires a range or iterable", line, source_line)
        rest = self._strip_wrapping_parens(rest)
        if rest.casefold() == "forever":
            return "while True:", None

        c_style = re.match(
            r"^(?:Let\s+|Var\s+)?([A-Za-z_]\w*)\s*=\s*(.+?)\s*;\s*"
            r"\1\s*(<=|<|>=|>)\s*(.+?)\s*;\s*\1\s*"
            r"(\+\+|--|\+=\s*.+|-=\s*.+)$",
            rest,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if c_style:
            target, start, comparison, end, update = c_style.groups()
            if target in constants:
                self._error(f"Cannot assign to Const {target}", line, source_line)
            step = "1"
            if update == "--":
                step = "-1"
            elif update.startswith("+="):
                step = self._translate(update[2:].strip())
            elif update.startswith("-="):
                step = f"-({self._translate(update[2:].strip())})"
            translated_start = self._translate(start.strip())
            translated_end = self._translate(end.strip())
            self._binding_scopes[-1].add(target)
            if comparison in {"<=", ">="}:
                return (
                    f"for {target} in __ppy_inclusive_range({translated_start}, "
                    f"{translated_end}, {step}):",
                    "inclusive_range",
                )
            return (
                f"for {target} in range({translated_start}, {translated_end}, {step}):",
                None,
            )

        times = re.match(r"^(.+?)\s+Times$", rest, flags=re.IGNORECASE)
        if times:
            count = self._translate(times.group(1).strip())
            return (
                f"for __ppy_repeat_{line} in __ppy_repeat_times({count}):",
                "repeat_times",
            )

        ranged = re.match(
            r"^([A-Za-z_]\w*)\s*=\s*(.+?)\s+To\s+(.+?)(?:\s+Step\s+(.+))?$",
            rest,
            flags=re.IGNORECASE,
        )
        if ranged:
            target, start, end, step = ranged.groups()
            if target in constants:
                self._error(f"Cannot assign to Const {target}", line, source_line)
            translated_start = self._translate(start.strip())
            translated_end = self._translate(end.strip())
            translated_step = self._translate(step.strip()) if step else "1"
            self._binding_scopes[-1].add(target)
            return (
                f"for {target} in __ppy_inclusive_range({translated_start}, "
                f"{translated_end}, {translated_step}):",
                "inclusive_range",
            )

        iterable = re.match(r"^(.+?)\s+In\s+(.+)$", rest, flags=re.IGNORECASE)
        if iterable:
            target = iterable.group(1).strip()
            if target in constants:
                self._error(f"Cannot assign to Const {target}", line, source_line)
            expression = self._translate(iterable.group(2).strip())
            self._binding_scopes[-1].add(target)
            return f"for {target} in {expression}:", None

        self._error(
            "Repeat syntax is `Repeat item In values`, `Repeat i = 1 To 5`, "
            "or `Repeat n Times`",
            line,
            source_line,
        )
        raise AssertionError("unreachable")

    def _from_import(self, rest: str, line: int, source_line: str) -> str:
        match = re.match(r"^(.+?)\s+Import\s+(.+)$", rest, flags=re.IGNORECASE)
        if not match:
            self._error("From syntax is `From module Import name`", line, source_line)
        module, names = match.groups()
        return f"from {module.strip()} import {self._import_clause(names.strip())}"

    @staticmethod
    def _import_clause(text: str) -> str:
        return re.sub(r"\bAs\b", "as", text, flags=re.IGNORECASE)

    def _register_import_bindings(self, rest: str, *, from_import: bool) -> None:
        names = rest
        if from_import:
            match = re.match(r"^.+?\s+Import\s+(.+)$", rest, re.IGNORECASE | re.DOTALL)
            if not match:
                return
            names = match.group(1)
        for item in self._split_top_level(names, ","):
            value = item.strip()
            if not value or value == "*":
                continue
            alias = re.search(r"\bAs\s+([A-Za-z_]\w*)\s*$", value, re.IGNORECASE)
            if alias:
                binding = alias.group(1)
            else:
                imported = re.split(r"\s+", value, maxsplit=1)[0]
                binding = imported if from_import else imported.split(".", 1)[0]
            if re.fullmatch(r"[A-Za-z_]\w*", binding):
                self._binding_scopes[-1].add(binding)

    def _register_function_binding(self, rest: str) -> None:
        match = re.match(r"^([A-Za-z_]\w*)", rest)
        if match:
            self._binding_scopes[-1].add(match.group(1))

    def _type_alias(self, rest: str, line: int, source_line: str) -> str:
        match = re.match(r"^([A-Za-z_]\w*)\s*=\s*(.+)$", rest, flags=re.DOTALL)
        if not match:
            self._error("Type syntax is `Type Name = OtherType`", line, source_line)
        name, annotation = match.groups()
        rendered = f"{name} = {self._translate_type(annotation)}"
        self._binding_scopes[-1].add(name)
        return rendered

    def _field_declaration(
        self,
        rest: str,
        line: int,
        source_line: str,
        stack: Sequence[_BlockFrame],
    ) -> str:
        if not stack or stack[-1].kind not in {"class", "interface"}:
            self._error(
                "Field is only valid inside Class or Interface", line, source_line
            )
        match = re.match(
            r"^([A-Za-z_]\w*)\s*:\s*([^=]+?)(?:\s*=\s*(.+))?$",
            rest,
            flags=re.DOTALL,
        )
        if not match:
            self._error("Field syntax is `Field name: Type`", line, source_line)
        name, annotation, default = match.groups()
        rendered = f"{name}: {self._translate_type(annotation)}"
        if default:
            rendered += f" = {self._translate(default)}"
        self._binding_scopes[-1].add(name)
        return rendered

    def _declaration(
        self,
        kind: str,
        rest: str,
        line: int,
        source_line: str,
        constants: set[str],
    ) -> str:
        self._require(rest, f"{kind.title()} requires an assignment", line, source_line)
        if kind == "set" and "=" not in rest:
            match = re.match(
                r"^(.+?)\s+To\s+(.+)$",
                rest,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if match:
                rest = f"{match.group(1).strip()} = {match.group(2).strip()}"
        match = re.match(
            r"^([A-Za-z_]\w*)(\s*:\s*[^=]+)?\s*(=|:=|\+=|-=|\*=|/=|%=)\s*(.+)$",
            rest,
            flags=re.DOTALL,
        )
        if match:
            name, annotation, operator, value = match.groups()
            translated_annotation = ""
            if annotation:
                translated_annotation = f": {self._translate_type(annotation[1:])}"
            translated_value = self._translate(value.strip())
            rendered = f"{name}{translated_annotation} {operator} {translated_value}"
        else:
            rendered = self._translate(rest)
        assignment = _ASSIGNMENT_RE.match(rendered)
        if not assignment and not self._is_assignment(rendered):
            self._error(f"{kind.title()} requires `name = value`", line, source_line)
        if kind == "const":
            if not assignment:
                self._error("Const requires a simple name", line, source_line)
            name = assignment.group(1)
            if name in constants:
                self._error(f"Const {name} is already declared", line, source_line)
            constants.add(name)
        elif assignment:
            self._check_constant_assignment(rendered, constants, line, source_line)
        if assignment and kind != "set":
            self._binding_scopes[-1].add(assignment.group(1))
        return rendered

    @staticmethod
    def _is_assignment(rendered: str) -> bool:
        try:
            module = ast.parse(rendered, mode="exec")
        except SyntaxError:
            return False
        return len(module.body) == 1 and isinstance(
            module.body[0], (ast.Assign, ast.AnnAssign, ast.AugAssign)
        )

    def _simple_statement(
        self,
        word: str,
        rest: str,
        line: int,
        source_line: str,
        stack: Sequence[_BlockFrame],
    ) -> str:
        target = self._SIMPLE_KEYWORDS[word]
        if target in {"return", "yield"} and not any(
            frame.kind == "function" for frame in stack
        ):
            self._error(
                f"{word.title()} is only valid inside Function", line, source_line
            )
        if target in {"break", "continue"} and not any(
            frame.kind in {"for", "while"} for frame in stack
        ):
            self._error(
                f"{word.title()} is only valid inside a loop", line, source_line
            )
        no_value = {"break", "continue", "pass"}
        if target in no_value and rest:
            self._error(f"{word.title()} does not accept a value", line, source_line)
        if target in {"return", "yield"} and rest.casefold().startswith("from "):
            rest = "from " + self._translate(rest[5:].strip())
        else:
            rest = self._translate(rest)
        return f"{target}{(' ' + rest) if rest else ''}"

    def _expression_statement(self, source: str, line: int, source_line: str) -> str:
        increment = re.match(
            r"^([A-Za-z_]\w*(?:\.[A-Za-z_]\w*|\[[^\]]+\])*)\s*(\+\+|--)$",
            source,
        )
        if increment:
            target, operator = increment.groups()
            return f"{self._translate(target)} {'+=' if operator == '++' else '-='} 1"
        rendered = self._translate(source)
        try:
            module = ast.parse(rendered, mode="exec")
        except SyntaxError:
            return rendered
        if len(module.body) != 1:
            self._error(
                "A PsuedoPY statement must contain one operation", line, source_line
            )
        statement = module.body[0]
        if isinstance(statement, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            self._error(
                "Raw assignment is not PsuedoPY syntax; use Let, Var, Const, or Set",
                line,
                source_line,
            )
        forbidden = (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
            ast.ClassDef,
            ast.If,
            ast.For,
            ast.AsyncFor,
            ast.While,
            ast.Try,
            ast.With,
            ast.AsyncWith,
            ast.Import,
            ast.ImportFrom,
        )
        if isinstance(statement, forbidden):
            self._error(
                "Python-only statement is not allowed in .ppy source",
                line,
                source_line,
            )
        return rendered

    @staticmethod
    def _check_constant_assignment(
        rendered: str,
        constants: set[str],
        line: int,
        source_line: str,
    ) -> None:
        assignment = _ASSIGNMENT_RE.match(rendered)
        if assignment and assignment.group(1) in constants:
            name = assignment.group(1)
            raise TranspilerError(
                f"Cannot assign to Const {name}",
                line=line,
                source_line=source_line,
            )

    @staticmethod
    def _mark_body(stack: list[_BlockFrame], line: int) -> None:
        if not stack:
            return
        frame = stack[-1]
        if frame.kind == "match" and not frame.branch_started:
            raise TranspilerError(
                "Match statements must begin with Case or Default", line=line
            )
        frame.has_body = True

    @staticmethod
    def _current_indent(stack: Sequence[_BlockFrame]) -> int:
        return stack[-1].body_indent if stack else 0

    @staticmethod
    def _indent(level: int, text: str) -> str:
        if not text:
            return ""
        prefix = "    " * level
        return "\n".join(f"{prefix}{line}" for line in text.split("\n"))

    @staticmethod
    def _comment(comment: str) -> str:
        return f"  {comment.strip()}" if comment else ""

    @staticmethod
    def _without_trailing_colon(text: str) -> str:
        return text[:-1].rstrip() if text.endswith(":") else text

    @staticmethod
    def _without_trailing_semicolon(text: str) -> str:
        return text[:-1].rstrip() if text.endswith(";") else text

    @staticmethod
    def _strip_wrapping_parens(text: str) -> str:
        value = text.strip()
        if value.startswith("(") and value.endswith(")"):
            return value[1:-1].strip()
        return value

    @staticmethod
    def _remove_suffix_word(text: str, word: str) -> str:
        return re.sub(rf"\s+{re.escape(word)}$", "", text, flags=re.IGNORECASE).strip()

    @staticmethod
    def _split_comment(line: str) -> tuple[str, str]:
        quote: str | None = None
        escaped = False
        for index, char in enumerate(line):
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
                return line[:index], line[index:]
        return line, ""

    @staticmethod
    def _require(value: str, message: str, line: int, source_line: str) -> None:
        if not value:
            raise TranspilerError(message, line=line, source_line=source_line)

    @staticmethod
    def _error(message: str, line: int, source_line: str) -> None:
        raise TranspilerError(message, line=line, source_line=source_line)
