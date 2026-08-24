
from __future__ import annotations

import sys
from typing import Dict, List, Optional

from psuedopy.compiler import Compiler
from psuedopy.exceptions import print_ppy_error
from psuedopy.pkg_manager import PackageManager
from psuedopy.transpiler import Transpiler, TranspilerError


class PsuedoPYRepl:

    _PROMPT = "\033[36mPsuedoPY >>>\033[0m "
    _CONT_PROMPT = "\033[36m      ...\033[0m "

    def __init__(self) -> None:
        self.transpiler = Transpiler()
        self.compiler = Compiler()
        self.pkg_manager = PackageManager()
        self.namespace: Dict[str, object] = {"__name__": "__main__"}

    def _is_magic(self, line: str) -> bool:
        stripped = line.strip()
        return stripped.startswith("install ") or stripped in {"exit", "quit"}

    def _handle_magic(self, line: str) -> bool:
        stripped = line.strip()
        if stripped in {"exit", "quit"}:
            return True
        if stripped.startswith("install "):
            package = stripped.removeprefix("install ").strip()
            try:
                self.pkg_manager.install(package)
            except RuntimeError as exc:
                print(f"Package error: {exc}")
        return False

    def _needs_continuation(self, buffer: List[str]) -> bool:
        if not buffer:
            return False
        last = buffer[-1].rstrip()
        if last.endswith(":"):
            return True
        joined = "\n".join(buffer)
        try:
            compile(self.transpiler.translate(joined).python_code, "<repl>", "exec")
            return False
        except (SyntaxError, IndentationError, TranspilerError):
            return True

    def run(self) -> None:
        print("PsuedoPY REPL. Type `exit` to quit, `install <pkg>` to install packages.")
        buffer: List[str] = []

        while True:
            prompt = self._CONT_PROMPT if buffer else self._PROMPT
            try:
                line = input(prompt)
            except (KeyboardInterrupt, EOFError):
                print()
                break

            if not buffer and self._is_magic(line):
                if self._handle_magic(line):
                    break
                continue

            buffer.append(line)

            if self._needs_continuation(buffer):
                continue

            source = "\n".join(buffer)
            buffer.clear()

            try:
                translated = self.transpiler.translate(source)
                code = compile(translated.python_code, "<psuedopy-repl>", "exec")
                exec(code, self.namespace)
            except Exception as exc:
                print_ppy_error(exc, translated.source_map)
