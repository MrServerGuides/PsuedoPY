
from __future__ import annotations

import marshal
import sys
from pathlib import Path
from typing import Any, Optional

from psuedopy.transpiler import Transpiler, TranslatedSource

class CompilerError(Exception):
    pass

class Compiler:

    _CPPY_MAGIC = b"PPY\x00\x01"

    def __init__(self) -> None:
        self.transpiler = Transpiler()

    def transpile(self, source: str) -> TranslatedSource:
        return self.transpiler.translate(source)

    def compile_to_code(self, source: str, filename: str = "<psuedopy>") -> Any:
        translated = self.transpile(source)
        try:
            return compile(translated.python_code, filename, "exec")
        except SyntaxError as exc:
            raise CompilerError(f"Python compilation failed: {exc}") from exc

    def write_compiled(self, source: str, output_path: str | Path,
                       filename: str = "<psuedopy>") -> Path:

        code_obj = self.compile_to_code(source, filename)
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        with output.open("wb") as fh:
            fh.write(self._CPPY_MAGIC)
            fh.write(b"\n")
            fh.write(marshal.dumps(code_obj))

        return output

    def load_compiled(self, path: str | Path) -> Any:

        path = Path(path)
        with path.open("rb") as fh:
            magic = fh.read(len(self._CPPY_MAGIC))
            if magic != self._CPPY_MAGIC:
                raise CompilerError(f"Invalid .cppy file: {path}")
            fh.read(1)
            return marshal.load(fh)

    def run_compiled(self, path: str | Path) -> None:
        code_obj = self.load_compiled(path)
        exec(code_obj, {"__name__": "__main__"})
