from __future__ import annotations

import ast
import io
import re
import tokenize
from collections.abc import Sequence
from dataclasses import dataclass, field

from psuedopy.errors import IncompleteInputError, TranspilerError
from psuedopy.grammar import Grammar

_FIRST_WORD_RE = re.compile(r"^([A-Za-z_]\w*)\b(.*)$", re.UNICODE)
_ASSIGNMENT_RE = re.compile(r"^([A-Za-z_]\w*)\s*(?::[^=]+)?\s*(?:[+\-*/%]?=|:=)")


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

    def translate(self, text: str, *, condition: bool = False) -> str:
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
                    and (
                        spec.category in self._EXPRESSION_CATEGORIES
                        or spec.python_target in self._CALL_TARGETS
                    )
                ):
                    replacements.append(
                        (token.start[1], token.end[1], spec.python_target)
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

        if tokens:
            translated = self._apply(text, replacements)
        else:
            translated = self._fallback_translate(text)
        translated = self._replace_not_equal(translated)
        if condition:
            translated = self._replace_condition_equals(translated)
        return translated

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
    _FOR_WORDS = {"repeat", "for"}
    _IMPORT_WORDS = {"import", "include", "use"}
    _DECLARATION_WORDS = {"let", "set", "var", "declare", "const"}
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

    def parse(self, source: str, *, allow_incomplete: bool = False) -> ParsedProgram:
        source_lines = source.splitlines()
        if not source_lines:
            source_lines = [""]
        output: list[GeneratedLine] = []
        stack: list[_BlockFrame] = []
        helpers: set[str] = set()
        constant_scopes: list[set[str]] = [set()]
        protected_lines = multiline_string_continuation_lines(source)

        for line_number, original in enumerate(source_lines, start=1):
            if line_number in protected_lines:
                output.append(GeneratedLine(original, line_number))
                continue
            code, comment = self._split_comment(original)
            stripped = code.strip()
            if not stripped:
                rendered = comment.strip() if comment else ""
                if rendered and stack:
                    rendered = self._indent(stack[-1].body_indent, rendered)
                output.append(GeneratedLine(rendered, line_number))
                continue

            stripped = self._without_trailing_colon(stripped)
            match = _FIRST_WORD_RE.match(stripped)
            if not match:
                self._mark_body(stack, line_number)
                output.append(
                    GeneratedLine(
                        self._indent(self._current_indent(stack), stripped)
                        + self._comment(comment),
                        line_number,
                    )
                )
                continue

            word = match.group(1)
            lowered = word.casefold()
            rest = match.group(2).strip()

            if lowered == "end":
                if self._close_block(stack, rest, line_number, original):
                    constant_scopes.pop()
                rendered = comment.strip() if comment else ""
                output.append(
                    GeneratedLine(
                        self._indent(self._current_indent(stack), rendered)
                        if rendered
                        else "",
                        line_number,
                    )
                )
                continue

            if lowered in self._ELIF_WORDS or lowered in self._ELSE_WORDS:
                rendered = self._parse_if_branch(
                    stack, lowered, rest, line_number, original
                )
                output.append(
                    GeneratedLine(rendered + self._comment(comment), line_number)
                )
                continue

            if lowered in {"catch", "except", "finally"}:
                rendered = self._parse_try_branch(
                    stack, lowered, rest, line_number, original
                )
                output.append(
                    GeneratedLine(rendered + self._comment(comment), line_number)
                )
                continue

            if lowered in {"case", "default"}:
                rendered = self._parse_case_branch(
                    stack, lowered, rest, line_number, original
                )
                output.append(
                    GeneratedLine(rendered + self._comment(comment), line_number)
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
                    rendered = self._function_header(
                        function_rest, line_number, original, async_=True
                    )
                    self._push_block(stack, "function", line_number, indent, scope=True)
                    constant_scopes.append(set())
                    output.append(
                        GeneratedLine(
                            self._indent(indent, rendered) + self._comment(comment),
                            line_number,
                        )
                    )
                    continue

            if lowered in self._FUNCTION_WORDS:
                rendered = self._function_header(rest, line_number, original)
                self._push_block(stack, "function", line_number, indent, scope=True)
                constant_scopes.append(set())
            elif lowered == "class":
                self._require(rest, "Class requires a name", line_number, original)
                rendered = f"class {self.expressions.translate(rest)}:"
                self._push_block(stack, "class", line_number, indent, scope=True)
                constant_scopes.append(set())
            elif lowered in self._IF_WORDS:
                condition = self._remove_suffix_word(rest, "then")
                self._require(
                    condition, "When requires a condition", line_number, original
                )
                rendered = (
                    f"if {self.expressions.translate(condition, condition=True)}:"
                )
                self._push_block(stack, "if", line_number, indent)
            elif lowered in self._WHILE_WORDS:
                condition = self._remove_suffix_word(rest, "then")
                if condition.casefold() == "forever":
                    condition = "True"
                self._require(
                    condition, "While requires a condition", line_number, original
                )
                rendered = (
                    f"while {self.expressions.translate(condition, condition=True)}:"
                )
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
                rendered = f"with {self.expressions.translate(rest)}:"
                self._push_block(stack, "with", line_number, indent)
            elif lowered == "match":
                self._require(rest, "Match requires a subject", line_number, original)
                rendered = f"match {self.expressions.translate(rest)}:"
                self._push_block(stack, "match", line_number, indent)
            elif lowered == "from":
                rendered = self._from_import(rest, line_number, original)
            elif lowered in self._IMPORT_WORDS:
                self._require(rest, "Import requires a module", line_number, original)
                rendered = f"import {self._import_clause(rest)}"
            elif lowered in self._DECLARATION_WORDS:
                rendered = self._declaration(
                    lowered, rest, line_number, original, constant_scopes[-1]
                )
            elif lowered in self._SIMPLE_KEYWORDS:
                rendered = self._simple_statement(
                    lowered, rest, line_number, original, stack
                )
            else:
                rendered = self.expressions.translate(stripped)
                self._check_constant_assignment(
                    rendered, constant_scopes[-1], line_number, original
                )

            output.append(
                GeneratedLine(
                    self._indent(indent, rendered) + self._comment(comment), line_number
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
            "function": {"function", "func", "procedure", "method", "def"},
            "for": {"for", "repeat"},
            "if": {"if", "when"},
            "while": {"while", "loop"},
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
            result = f"elif {self.expressions.translate(condition, condition=True)}:"
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
                result = f"except {self.expressions.translate(rest)}:"
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
            pattern = self.expressions.translate(rest)
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
    ) -> str:
        self._require(
            rest, "Function requires a name and parameter list", line, source_line
        )
        if "(" not in rest or not rest.rstrip().endswith(")"):
            self._error(
                "Function syntax is `Function name(parameters)`",
                line,
                source_line,
            )
        prefix = "async def" if async_ else "def"
        return f"{prefix} {self.expressions.translate(rest)}:"

    def _repeat_header(
        self,
        rest: str,
        line: int,
        source_line: str,
        constants: set[str],
    ) -> tuple[str, str | None]:
        self._require(rest, "Repeat requires a range or iterable", line, source_line)
        if rest.casefold() == "forever":
            return "while True:", None

        times = re.match(r"^(.+?)\s+Times$", rest, flags=re.IGNORECASE)
        if times:
            count = self.expressions.translate(times.group(1).strip())
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
            translated_start = self.expressions.translate(start.strip())
            translated_end = self.expressions.translate(end.strip())
            translated_step = self.expressions.translate(step.strip()) if step else "1"
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
            expression = self.expressions.translate(iterable.group(2).strip())
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
            match = re.match(r"^(.+?)\s+To\s+(.+)$", rest, flags=re.IGNORECASE)
            if match:
                rest = f"{match.group(1).strip()} = {match.group(2).strip()}"
        rendered = self.expressions.translate(rest)
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
            rest = "from " + self.expressions.translate(rest[5:].strip())
        else:
            rest = self.expressions.translate(rest)
        return f"{target}{(' ' + rest) if rest else ''}"

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
        return f"{'    ' * level}{text}" if text else ""

    @staticmethod
    def _comment(comment: str) -> str:
        return f"  {comment.strip()}" if comment else ""

    @staticmethod
    def _without_trailing_colon(text: str) -> str:
        return text[:-1].rstrip() if text.endswith(":") else text

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
