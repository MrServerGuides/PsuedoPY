
from __future__ import annotations

from pathlib import Path

from psuedopy.compiler import Compiler
from psuedopy.exceptions import print_ppy_error
from psuedopy.formatter import PsuedoPYFormatter
from psuedopy.repl import PsuedoPYRepl
from psuedopy.transpiler import Transpiler


def run_ppy_file(path: str | Path) -> None:
    path = Path(path)
    source = path.read_text(encoding="utf-8")
    transpiler = Transpiler()
    translated = transpiler.translate(source)

    try:
        code = compile(translated.python_code, str(path), "exec")
        exec(code, {"__name__": "__main__"})
    except Exception as exc:
        print_ppy_error(exc, translated.source_map)
        raise SystemExit(1)


def compile_ppy_file(path: str | Path, output: str | Path) -> None:
    path = Path(path)
    output = Path(output)
    source = path.read_text(encoding="utf-8")

    compiler = Compiler()
    try:
        compiler.write_compiled(source, output, filename=str(path))
        print(f"Compiled {path} -> {output}")
    except Exception as exc:
        print(f"Compilation error: {exc}")
        raise SystemExit(1)


def start_repl() -> None:
    PsuedoPYRepl().run()


def format_ppy_file(path: str | Path) -> None:
    path = Path(path)
    formatter = PsuedoPYFormatter()
    formatter.format_file(path)
    print(f"Formatted {path}")