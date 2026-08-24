
from __future__ import annotations

import io
import json
import tokenize
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Set
from enum import Enum

from psuedopy.source_map import SourceMap


class TranspilerError(Exception):
    pass


class KeywordContext(Enum):
    """Syntactic contexts where keywords may appear."""
    ATTRIBUTE = "attribute"           # obj.Print → do not translate
    ASSIGNMENT_TARGET = "assignment"  # Print = 123 → do not translate
    DICT_KEY = "dict_key"             # {"Print": ...} → do not translate (strings)
    STATEMENT_START = "statement"     # Print(...) at line start → translate
    CONTROL_FLOW = "control_flow"     # If, While, For → translate
    DECLARATION = "declaration"       # Function, Class → translate
    OPERATOR = "operator"             # and, or, not → translate
    LITERAL = "literal"               # True, False, None → translate
    IMPORT = "import"                 # Import, From → translate
    OTHER = "other"                   # Unknown context


class _Replacement(NamedTuple):
    start: int
    end: int
    text: str


class TranslatedSource(NamedTuple):
    python_code: str
    source_map: SourceMap
    original_source: str


class Transpiler:
    """
    Context-aware transpiler for PsuedoPY.

    Transforms PsuedoPY syntax to Python while preserving:
    - Attribute access (obj.Print() stays unchanged)
    - Variable assignments (Print = 123 stays unchanged)
    - String literals and comments
    - Normal Python code
    - Imports and module names
    - Dictionary keys
    """

    _BLOCK_OPENERS = {
        "def", "if", "elif", "else", "for", "while", "class",
        "try", "except", "finally", "with", "match", "case",
    }

    _EMPTY = "__EMPTY__"
    _END = "__END__"

    # Keywords that can only appear at statement start (column-aware)
    _STATEMENT_START_KEYWORDS = {
        "Print", "Display", "Write", "Echo", "Output", "Text",
        "Ask", "Input", "Read", "Prompt",
    }

    # Control flow keywords (if/while/for context)
    _CONTROL_FLOW_KEYWORDS = {
        "If", "When", "Elif", "ElseIf", "Else", "Otherwise",
        "For", "Repeat", "While", "Loop",
        "Try", "Except", "Catch", "Finally",
        "Match", "Case",
    }

    # Declaration keywords
    _DECLARATION_KEYWORDS = {
        "Function", "Func", "Define", "Def", "Procedure", "Method",
        "Class",
    }

    # Import keywords
    _IMPORT_KEYWORDS = {
        "Import", "From", "Include", "Use",
    }

    # Keywords that should be removed/replaced with empty
    _SYNTAX_MARKERS = {
        "End", "Then", "Let", "Set", "Var", "Declare", "Const",
    }

    # Literal values
    _LITERAL_KEYWORDS = {
        "True", "Yes", "On",
        "False", "No", "Off",
        "None", "Null", "Nil", "Nothing",
    }

    # Operators
    _OPERATOR_KEYWORDS = {
        "And", "Or", "Not", "In", "Is",
    }

    def __init__(self, grammar_file: str | Path | None = None) -> None:
        if grammar_file is None:
            grammar_file = Path(__file__).parent / "data" / "grammar_map.json"
        self.grammar_map: Dict[str, str] = self._load_grammar(grammar_file)
        self._categorize_keywords()

    def _categorize_keywords(self) -> None:
        """Build keyword category lookup from grammar map."""
        self.keyword_categories: Dict[str, KeywordContext] = {}
        
        for keyword in self._STATEMENT_START_KEYWORDS:
            if keyword in self.grammar_map:
                self.keyword_categories[keyword] = KeywordContext.STATEMENT_START
        
        for keyword in self._CONTROL_FLOW_KEYWORDS:
            if keyword in self.grammar_map:
                self.keyword_categories[keyword] = KeywordContext.CONTROL_FLOW
        
        for keyword in self._DECLARATION_KEYWORDS:
            if keyword in self.grammar_map:
                self.keyword_categories[keyword] = KeywordContext.DECLARATION
        
        for keyword in self._IMPORT_KEYWORDS:
            if keyword in self.grammar_map:
                self.keyword_categories[keyword] = KeywordContext.IMPORT
        
        for keyword in self._LITERAL_KEYWORDS:
            if keyword in self.grammar_map:
                self.keyword_categories[keyword] = KeywordContext.LITERAL
        
        for keyword in self._OPERATOR_KEYWORDS:
            if keyword in self.grammar_map:
                self.keyword_categories[keyword] = KeywordContext.OPERATOR
        
        for keyword in self._SYNTAX_MARKERS:
            if keyword in self.grammar_map:
                self.keyword_categories[keyword] = KeywordContext.STATEMENT_START

    @staticmethod
    def _load_grammar(path: str | Path) -> Dict[str, str]:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise TranspilerError("grammar_map.json must contain a JSON object")
        return data

    def _is_after_dot(self, tokens_up_to: List) -> bool:
        """
        Check if the most recent significant token is a DOT.
        
        This detects attribute access like obj.Print()
        Attribute access should NOT be transformed.
        
        Also checks for indexing like obj[...].Print()
        """
        if not tokens_up_to:
            return False
        
        # Scan backwards for the nearest non-whitespace, non-newline token
        for token in reversed(tokens_up_to):
            if token.type in (tokenize.INDENT, tokenize.DEDENT, 
                             tokenize.NEWLINE, tokenize.NL,
                             tokenize.ERRORTOKEN, tokenize.COMMENT):
                continue
            # Attribute access: preceded by dot
            if token.type == tokenize.DOT:
                return True
            # If we hit something else substantial, not an attribute
            return False
        
        return False

    def _is_assignment_target(self, token_list: List, token_index: int) -> bool:
        """
        Check if a NAME token is the target of an assignment.
        
        Examples of assignment targets:
        - Print = 123
        - Text = "hello"
        - obj.Print = value
        
        These should NOT be transformed.
        """
        if token_index >= len(token_list) - 1:
            return False
        
        # Look ahead for '=' sign (skipping whitespace/newlines)
        for i in range(token_index + 1, min(token_index + 5, len(token_list))):
            tok = token_list[i]
            if tok.type == tokenize.OP and tok.string == "=":
                # Make sure it's not ==, !=, <=, >=
                # (they are single = in tokenization)
                if i + 1 < len(token_list) and token_list[i + 1].string != "=":
                    return True
                return tok.string == "="
            elif tok.type not in (tokenize.INDENT, tokenize.DEDENT, 
                                 tokenize.NL, tokenize.NEWLINE,
                                 tokenize.COMMENT):
                # Hit something else - not an assignment
                break
        
        return False

    def _is_in_import_statement(self, token_list: List, token_index: int) -> bool:
        """
        Check if a NAME token is part of an import statement context.
        
        Examples where we should NOT translate:
        - from package import Print  (Print is imported name, not keyword)
        - import package.Print        (Print is module name, not keyword)
        - from package.Print import x (Print is module path)
        
        Only the actual import keywords (Import, From) should be translated.
        """
        if token_index == 0:
            return False
        
        # Look backwards for "import" or "from" keyword
        for i in range(token_index - 1, max(0, token_index - 10), -1):
            tok = token_list[i]
            if tok.type == tokenize.NAME:
                if tok.string in ("import", "from"):
                    # We're in an import context
                    # But only translate if THIS token is the keyword itself
                    # not a module/name that follows it
                    return True
                # If we hit another keyword/name that's not import, stop looking
                if tok.string not in ("as",):
                    return True
            elif tok.type == tokenize.NEWLINE:
                # We've crossed a line boundary, stop searching
                break
        
        return False

    def _is_import_keyword_itself(self, token_list: List, token_index: int, 
                                 token_string: str) -> bool:
        """
        Check if a token is actually an import keyword (Import/From)
        vs a module name following it.
        """
        if token_string not in ("Import", "From"):
            return False
        
        # Look backwards - if we hit another NAME before this, skip
        for i in range(token_index - 1, max(0, token_index - 3), -1):
            tok = token_list[i]
            if tok.type in (tokenize.INDENT, tokenize.DEDENT, 
                           tokenize.NL, tokenize.NEWLINE,
                           tokenize.COMMENT):
                continue
            if tok.type == tokenize.NAME:
                # Another name before us - we're not the keyword
                return False
            break
        
        return True

    def _get_statement_context(self, line: str, token_col: int) -> bool:
        """
        Check if token appears at a valid statement-start position.
        
        A statement keyword must appear:
        - After leading whitespace (indent)
        - Not after a dot
        - Not as assignment target
        - Typically at the beginning of a logical line
        """
        # For statement keywords, check if they're at the beginning of the line
        # (after indentation)
        before_token = line[:token_col].strip()
        
        # If there's code before the token (other than indent), it's not a statement start
        return len(before_token) == 0

    def _should_transform_keyword(self, token: tokenize.TokenInfo, 
                                 all_tokens: List,
                                 token_index: int,
                                 line: str) -> bool:
        """
        Determine if a keyword should be transformed based on syntactic context.
        
        Returns False if:
        - The keyword is used as an attribute (after .)
        - The keyword is an assignment target
        - The keyword is a module/package name in an import
        - The keyword appears in a non-statement context for statement keywords
        
        Returns True if:
        - The keyword is a statement start (Print, If, While, etc.)
        - The keyword is an operator (and, or, not)
        - The keyword is a literal value (True, False, None)
        - The keyword is an import/declaration keyword at statement start
        """
        keyword = token.string
        
        # Get keyword category
        category = self.keyword_categories.get(keyword)
        if category is None:
            return False
        
        # FIRST: Check if it's after a dot (attribute access)
        # This takes precedence over everything else
        if self._is_after_dot(all_tokens[:token_index]):
            return False
        
        # SECOND: Check if it's an assignment target
        if self._is_assignment_target(all_tokens, token_index):
            return False
        
        # THIRD: Special handling for import keywords
        if category == KeywordContext.IMPORT:
            # Import/From keywords should only be translated if they're the keyword itself
            # not a module name following them
            return self._is_import_keyword_itself(all_tokens, token_index, keyword)
        
        # FOURTH: For statement start keywords, check column position
        if category == KeywordContext.STATEMENT_START:
            # Statement keywords should only be at statement start
            return self._get_statement_context(line, token.start[1])
        
        # Operators, literals, control flow, declaration, syntax markers
        # can be transformed (they're safe to translate outside statement start)
        if category in (KeywordContext.OPERATOR, KeywordContext.LITERAL,
                       KeywordContext.CONTROL_FLOW, KeywordContext.DECLARATION):
            return True
        
        return False

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
        """
        Translate PsuedoPY source to Python with context-aware keyword replacement.
        """
        ppy_lines = source.splitlines()
        if not ppy_lines:
            ppy_lines = [""]

        replacements_by_line: Dict[int, List[_Replacement]] = {}
        header_lines: set[int] = set()
        blank_lines: set[int] = set()

        try:
            tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
        except tokenize.TokenError as exc:
            raise TranspilerError(f"Lexical error: {exc}") from exc

        for token_index, token in enumerate(tokens):
            if token.type != tokenize.NAME:
                continue

            line_no = token.start[0]
            original = token.string
            mapped = self.grammar_map.get(original)

            if mapped is None:
                continue

            # Check if this keyword should be transformed based on context
            if not self._should_transform_keyword(token, tokens, token_index, ppy_lines[line_no - 1]):
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
