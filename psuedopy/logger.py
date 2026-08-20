
from __future__ import annotations

import os
import sys
from enum import Enum
from typing import Optional


class LogLevel(Enum):

    DEBUG = "DEBUG"
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"


class Logger:

    _COLORS = {
        LogLevel.DEBUG: "\033[36m",
        LogLevel.INFO: "\033[0m",
        LogLevel.SUCCESS: "\033[32m",
        LogLevel.WARNING: "\033[33m",
        LogLevel.ERROR: "\033[31m",
    }
    _RESET = "\033[0m"
    _BOLD = "\033[1m"

    def __init__(self, color_enabled: bool = True, verbose: bool = False) -> None:
        self.color_enabled = color_enabled and self._terminal_supports_color()
        self.verbose = verbose

    @staticmethod
    def _terminal_supports_color() -> bool:
        if os.environ.get("NO_COLOR"):
            return False
        return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

    def _emit(
        self,
        level: LogLevel,
        message: str,
        *,
        stream: Optional[object] = None,
        bold: bool = False,
    ) -> None:
        if level == LogLevel.DEBUG and not self.verbose:
            return

        target = stream or (sys.stderr if level in {LogLevel.WARNING, LogLevel.ERROR} else sys.stdout)

        if self.color_enabled:
            color = self._COLORS[level]
            prefix = f"{self._BOLD if bold else ''}{color}{level.value}{self._RESET}"
            text = f"{color}{message}{self._RESET}" if level != LogLevel.INFO else message
        else:
            prefix = f"{level.value}"
            text = message

        print(f"{prefix}: {text}", file=target)

    def debug(self, message: str) -> None:
        self._emit(LogLevel.DEBUG, message)

    def info(self, message: str) -> None:
        self._emit(LogLevel.INFO, message)

    def success(self, message: str) -> None:
        self._emit(LogLevel.SUCCESS, message)

    def warning(self, message: str) -> None:
        self._emit(LogLevel.WARNING, message)

    def error(self, message: str) -> None:
        self._emit(LogLevel.ERROR, message)

    def transpile_step(self, message: str) -> None:
        self._emit(LogLevel.DEBUG, message, bold=True)

    def banner(self, text: str) -> None:
        line = "=" * max(60, len(text) + 8)
        print(line)
        if self.color_enabled:
            print(f"{self._BOLD}{text}{self._RESET}")
        else:
            print(text)
        print(line)

    def repl_banner(self, version: str) -> None:
        self.banner(f"PsuedoPY REPL v{version}")