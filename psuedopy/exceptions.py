from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path
from typing import TextIO

from psuedopy.errors import PsuedoPYError
from psuedopy.source_map import SourceMap


def _supports_color(stream: TextIO) -> bool:
    return not os.environ.get("NO_COLOR") and bool(
        hasattr(stream, "isatty") and stream.isatty()
    )


def _paint(text: str, code: str, enabled: bool) -> str:
    return f"\033[{code}m{text}\033[0m" if enabled else text


def print_ppy_error(
    exc: BaseException,
    source_map: SourceMap | None = None,
    *,
    filename: str | None = None,
    show_translated: bool = False,
    color: bool | None = None,
    stream: TextIO | None = None,
) -> None:
    """Print one concise, source-mapped diagnostic for a language error."""

    target = stream or sys.stderr
    enabled = _supports_color(target) if color is None else color
    error_name = type(exc).__name__
    if error_name.endswith("Error") and error_name not in {
        "SyntaxError",
        "TypeError",
        "ValueError",
        "NameError",
    }:
        error_name = "Error"
    message = getattr(exc, "message", str(exc))
    print(_paint(f"PsuedoPY {error_name}: {message}", "31;1", enabled), file=target)

    shown = False
    if isinstance(exc, PsuedoPYError) and exc.location is not None:
        location = exc.location
        _print_location(
            filename,
            location.line,
            location.column,
            location.source_line,
            enabled,
            target,
        )
        shown = True
    elif isinstance(exc, SyntaxError):
        generated_line = exc.lineno or 1
        original_line = (
            source_map.original_line_no(generated_line)
            if source_map
            else generated_line
        )
        source_line = (
            source_map.original_source_line(generated_line) if source_map else exc.text
        )
        if original_line <= 0 and source_map is not None:
            _print_generated_location(
                filename or exc.filename,
                generated_line,
                source_map.generated_source_line(generated_line),
                enabled,
                target,
            )
        else:
            _print_location(
                filename or exc.filename,
                original_line,
                exc.offset or 1,
                source_line,
                enabled,
                target,
            )
        shown = True
    elif source_map is not None:
        frames = traceback.extract_tb(exc.__traceback__)
        selected = None
        if filename:
            wanted = str(Path(filename).resolve())
            for frame in reversed(frames):
                try:
                    candidate = str(Path(frame.filename).resolve())
                except OSError:
                    candidate = frame.filename
                if candidate == wanted or frame.filename == filename:
                    selected = frame
                    break
        if selected is None and frames:
            selected = frames[-1]
        if selected is not None:
            original_line = source_map.original_line_no(selected.lineno)
            source_line = source_map.original_source_line(selected.lineno)
            if original_line <= 0:
                _print_generated_location(
                    filename or selected.filename,
                    selected.lineno,
                    source_map.generated_source_line(selected.lineno),
                    enabled,
                    target,
                )
            else:
                _print_location(
                    filename or selected.filename,
                    original_line,
                    1,
                    source_line,
                    enabled,
                    target,
                )
            shown = True

    if not shown and filename:
        print(f'  File "{filename}"', file=target)

    if show_translated and source_map and source_map.python_lines:
        print("\nGenerated Python:", file=target)
        for number, line in enumerate(source_map.python_lines, start=1):
            print(f"{number:4d}: {line}", file=target)


def _print_location(
    filename: str | None,
    line: int,
    column: int,
    source_line: str | None,
    color: bool,
    stream: TextIO,
) -> None:
    display_name = filename or "<input>"
    print(f'  File "{display_name}", line {line}, column {column}', file=stream)
    if source_line is not None:
        clean = source_line.rstrip("\n")
        print(f"    {_paint(clean, '33', color)}", file=stream)
        if clean:
            caret_column = max(1, min(column, len(clean) + 1))
            print(
                f"    {' ' * (caret_column - 1)}{_paint('^', '31;1', color)}",
                file=stream,
            )


def _print_generated_location(
    filename: str | None,
    line: int,
    source_line: str | None,
    color: bool,
    stream: TextIO,
) -> None:
    display_name = filename or "<generated>"
    print(f'  Generated Python for "{display_name}", line {line}', file=stream)
    if source_line is not None:
        print(f"    {_paint(source_line.rstrip(), '33', color)}", file=stream)
