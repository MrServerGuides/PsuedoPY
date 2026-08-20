
from __future__ import annotations

import sys
import traceback
from typing import List, Optional

from psuedopy.source_map import SourceMap


def _ansi_red(text: str) -> str:
    return f"\033[31m{text}\033[0m"


def _ansi_yellow(text: str) -> str:
    return f"\033[33m{text}\033[0m"


def _ansi_bold(text: str) -> str:
    return f"\033[1m{text}\033[0m"


def print_ppy_error(
    exc: BaseException,
    source_map: SourceMap,
    *,
    show_translated: bool = False,
) -> None:

    tb = traceback.extract_tb(sys.exc_info()[2]) if sys.exc_info()[2] else []
    print(_ansi_red(f"PsuedoPY Error: {type(exc).__name__}: {exc}"))

    for frame in reversed(tb):
        filename = frame.filename
        lineno = frame.lineno
        original_lineno = source_map.original_line_no(lineno)
        source_line = source_map.original_source_line(lineno)

        print(f"  File \"{filename}\", line {original_lineno}", end="")
        if source_line is not None:
            print(f"\n    {_ansi_yellow(source_line.strip())}")
        else:
            print()

    if show_translated:
        print(_ansi_bold("\nGenerated Python (for debugging only):"))
        for i, line in enumerate(source_map.ppy_lines, start=1):
            print(f"{i:4d}: {line}")