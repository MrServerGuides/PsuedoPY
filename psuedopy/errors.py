from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceLocation:
    line: int
    column: int = 1
    source_line: str | None = None


class PsuedoPYError(Exception):
    """Base class for user-facing PsuedoPY toolchain errors."""

    def __init__(
        self,
        message: str,
        *,
        line: int | None = None,
        column: int = 1,
        source_line: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.location = (
            SourceLocation(line, column, source_line) if line is not None else None
        )

    def __str__(self) -> str:
        if self.location is None:
            return self.message
        return f"line {self.location.line}: {self.message}"


class TranspilerError(PsuedoPYError):
    """Raised when PsuedoPY source cannot be parsed or translated."""


class IncompleteInputError(TranspilerError):
    """Raised when an interactive input buffer needs one or more `End` lines."""


class FormatterError(PsuedoPYError):
    """Raised when a source file cannot be formatted safely."""


class CompilerError(PsuedoPYError):
    """Raised when generated Python or a compiled artifact is invalid."""


class CompiledFileError(CompilerError):
    """Raised when a .cppy artifact is corrupt or unsupported."""
