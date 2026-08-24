from __future__ import annotations

import ast
from pathlib import Path

from psuedopy import __version__
from psuedopy.errors import IncompleteInputError, TranspilerError
from psuedopy.exceptions import print_ppy_error
from psuedopy.pkg_manager import PackageManager
from psuedopy.transpiler import TranslatedSource, Transpiler


class PsuedoPYRepl:
    _PROMPT = "PsuedoPY >>> "
    _CONT_PROMPT = "          ... "

    def __init__(self, grammar_file: str | Path | None = None) -> None:
        self.transpiler = Transpiler(grammar_file)
        self.pkg_manager = PackageManager()
        self.namespace: dict[str, object] = {"__name__": "__main__"}

    @staticmethod
    def _is_magic(line: str) -> bool:
        stripped = line.strip()
        return stripped.startswith("install ") or stripped.casefold() in {
            "exit",
            "quit",
            ":exit",
            ":quit",
            ":help",
            ":reset",
            "cancel",
        }

    def _handle_magic(self, line: str) -> str:
        stripped = line.strip()
        lowered = stripped.casefold()
        if lowered in {"exit", "quit", ":exit", ":quit"}:
            return "exit"
        if lowered == ":help":
            print(
                "Commands: :help, :reset, :quit, cancel, install <package>. "
                "Blocks finish with End."
            )
            return "handled"
        if lowered == ":reset":
            self.namespace = {"__name__": "__main__"}
            print("Namespace reset.")
            return "handled"
        if lowered == "cancel":
            return "cancel"
        if lowered.startswith("install "):
            package = stripped[len("install ") :].strip()
            try:
                self.pkg_manager.install(package)
            except RuntimeError as exc:
                print(f"Package error: {exc}")
            return "handled"
        return "none"

    def _needs_continuation(self, buffer: list[str]) -> bool:
        if not buffer:
            return False
        try:
            self.transpiler.translate("\n".join(buffer), allow_incomplete=True)
            return False
        except IncompleteInputError:
            return True
        except TranspilerError:
            return False

    def run(self) -> None:
        print(
            f"PsuedoPY REPL v{__version__}. Type :help for commands; "
            "finish blocks with End."
        )
        buffer: list[str] = []
        while True:
            prompt = self._CONT_PROMPT if buffer else self._PROMPT
            try:
                line = input(prompt)
            except KeyboardInterrupt:
                if buffer:
                    buffer.clear()
                    print("\nInput cancelled.")
                    continue
                print()
                break
            except EOFError:
                print()
                break

            if self._is_magic(line):
                action = self._handle_magic(line)
                if action == "exit":
                    break
                if action == "cancel":
                    buffer.clear()
                    print("Input cancelled.")
                if action != "none":
                    continue

            buffer.append(line)
            if self._needs_continuation(buffer):
                continue

            source = "\n".join(buffer)
            buffer.clear()
            translated: TranslatedSource | None = None
            try:
                translated = self.transpiler.translate(source)
                self._execute(translated)
            except Exception as exc:
                print_ppy_error(
                    exc,
                    translated.source_map if translated else None,
                    filename="<repl>",
                )

    def _execute(self, translated: TranslatedSource) -> None:
        module = ast.parse(translated.python_code, filename="<repl>", mode="exec")
        if not module.body or not isinstance(module.body[-1], ast.Expr):
            exec(compile(module, "<repl>", "exec"), self.namespace, self.namespace)
            return

        leading = ast.Module(body=module.body[:-1], type_ignores=[])
        if leading.body:
            exec(compile(leading, "<repl>", "exec"), self.namespace, self.namespace)
        expression = ast.Expression(module.body[-1].value)
        value = eval(
            compile(expression, "<repl>", "eval"), self.namespace, self.namespace
        )
        if value is not None:
            print(repr(value))
