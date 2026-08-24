from __future__ import annotations

import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

from psuedopy.compiler import Compiler
from psuedopy.errors import CompilerError, FormatterError, TranspilerError
from psuedopy.exceptions import print_ppy_error
from psuedopy.formatter import PsuedoPYFormatter
from psuedopy.repl import PsuedoPYRepl


def run_ppy_file(
    file_path: str,
    program_args: Sequence[str] | None = None,
    *,
    grammar_file: str | Path | None = None,
    debug: bool = False,
    color: bool | None = None,
) -> None:
    path = _source_path(file_path)
    compiler = Compiler(grammar_file)

    if path.suffix.casefold() == ".cppy":
        _run_compiled(path, compiler, program_args, debug=debug, color=color)
        return

    source = _read_source(path)
    translated = None
    try:
        translated = compiler.transpile(source)
        code = compiler.compile_translated(translated, str(path))
        namespace = {
            "__name__": "__main__",
            "__file__": str(path),
            "__package__": None,
        }
        with _script_environment(path, program_args):
            exec(code, namespace, namespace)
    except (TranspilerError, CompilerError) as exc:
        print_ppy_error(
            exc,
            translated.source_map if translated else None,
            filename=str(path),
            show_translated=debug,
            color=color,
        )
        raise SystemExit(1) from exc
    except Exception as exc:
        print_ppy_error(
            exc,
            translated.source_map if translated else None,
            filename=str(path),
            show_translated=debug,
            color=color,
        )
        raise SystemExit(1) from exc


def compile_ppy_file(
    input_path: str,
    output_path: str | None = None,
    *,
    grammar_file: str | Path | None = None,
) -> Path:
    path = _source_path(input_path)
    source = _read_source(path)
    output = Path(output_path) if output_path else path.with_suffix(".cppy")
    compiler = Compiler(grammar_file)
    try:
        result = compiler.write_compiled(source, output, filename=str(path))
    except (CompilerError, TranspilerError) as exc:
        print_ppy_error(exc, filename=str(path))
        raise SystemExit(1) from exc
    except OSError as exc:
        print(f"Error writing '{output}': {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    print(f"Compiled: {path} -> {result}")
    return result


def transpile_ppy_file(
    input_path: str,
    output_path: str | None = None,
    *,
    grammar_file: str | Path | None = None,
) -> Path:
    path = _source_path(input_path)
    source = _read_source(path)
    output = Path(output_path) if output_path else path.with_suffix(".py")
    compiler = Compiler(grammar_file)
    try:
        translated = compiler.transpile(source)
        compiler.compile_translated(translated, str(path))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(translated.python_code + "\n", encoding="utf-8", newline="\n")
    except (CompilerError, TranspilerError) as exc:
        print_ppy_error(exc, filename=str(path))
        raise SystemExit(1) from exc
    except OSError as exc:
        print(f"Error writing '{output}': {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    print(f"Transpiled: {path} -> {output}")
    return output


def format_ppy_file(
    file_path: str,
    *,
    check: bool = False,
    grammar_file: str | Path | None = None,
) -> bool:
    path = _source_path(file_path)
    source = _read_source(path)
    formatter = PsuedoPYFormatter(grammar_file)
    try:
        formatted = formatter.format(source)
    except FormatterError as exc:
        print_ppy_error(exc, filename=str(path))
        raise SystemExit(1) from exc

    changed = formatted != source
    if check:
        if changed:
            print(f"Needs formatting: {path}", file=sys.stderr)
            raise SystemExit(1)
        print(f"Already formatted: {path}")
        return False
    if changed:
        try:
            path.write_text(formatted, encoding="utf-8", newline="\n")
        except OSError as exc:
            print(f"Error writing '{path}': {exc}", file=sys.stderr)
            raise SystemExit(2) from exc
        print(f"Formatted: {path}")
    else:
        print(f"Unchanged: {path}")
    return changed


def check_ppy_file(
    file_path: str,
    *,
    grammar_file: str | Path | None = None,
) -> None:
    path = _source_path(file_path)
    source = _read_source(path)
    compiler = Compiler(grammar_file)
    translated = None
    try:
        translated = compiler.transpile(source)
        compiler.compile_translated(translated, str(path))
    except (CompilerError, TranspilerError) as exc:
        print_ppy_error(
            exc,
            translated.source_map if translated else None,
            filename=str(path),
        )
        raise SystemExit(1) from exc
    print(f"OK: {path}")


def start_repl(*, grammar_file: str | Path | None = None) -> None:
    PsuedoPYRepl(grammar_file).run()


def _run_compiled(
    path: Path,
    compiler: Compiler,
    program_args: Sequence[str] | None,
    *,
    debug: bool,
    color: bool | None,
) -> None:
    translated = None
    try:
        artifact = compiler.load_artifact(path)
        filename = str(artifact.metadata.get("source_filename", path))
        translated = compiler.transpile(artifact.original_source)
        if translated.python_code != artifact.python_code:
            raise CompilerError(
                "Compiled artifact does not match this language runtime; rebuild it"
            )
        code = compile(artifact.python_code, filename, "exec")
        namespace = {
            "__name__": "__main__",
            "__file__": filename,
            "__package__": None,
        }
        with _script_environment(Path(filename), program_args):
            exec(code, namespace, namespace)
    except Exception as exc:
        print_ppy_error(
            exc,
            translated.source_map if translated else None,
            filename=str(path),
            show_translated=debug,
            color=color,
        )
        raise SystemExit(1) from exc


def _source_path(file_path: str) -> Path:
    path = Path(file_path).expanduser()
    if not path.exists():
        print(f"Error: File '{file_path}' not found.", file=sys.stderr)
        raise SystemExit(2)
    if not path.is_file():
        print(f"Error: '{file_path}' is not a file.", file=sys.stderr)
        raise SystemExit(2)
    return path.resolve()


def _read_source(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        print(f"Error reading '{path}': {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


@contextmanager
def _script_environment(
    path: Path, program_args: Sequence[str] | None
) -> Iterator[None]:
    old_argv = sys.argv[:]
    old_path = sys.path[:]
    sys.argv = [str(path), *(program_args or [])]
    sys.path.insert(0, str(path.parent.resolve()))
    try:
        yield
    finally:
        sys.argv = old_argv
        sys.path[:] = old_path
