from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from psuedopy import __version__
from psuedopy.config import ConfigManager
from psuedopy.main import (
    check_ppy_file,
    compile_ppy_file,
    format_ppy_file,
    run_ppy_file,
    start_repl,
    transpile_ppy_file,
)
from psuedopy.pkg_manager import PackageManager


def build_parser() -> argparse.ArgumentParser:
    invoked = Path(sys.argv[0]).stem.casefold()
    program = invoked if invoked in {"ppyx", "psuedopy", "pseudopy"} else "ppyx"
    parser = argparse.ArgumentParser(
        prog=program,
        description=(
            "PsuedoPY - typed pseudocode with modern expressions and a Python backend."
        ),
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument("--grammar", help="Path to a custom grammar JSON file")
    parser.add_argument(
        "--debug", action="store_true", help="Show generated Python in diagnostics"
    )
    parser.add_argument(
        "--no-color", action="store_true", help="Disable colored diagnostics"
    )

    commands = parser.add_subparsers(dest="command", title="commands")

    run_parser = commands.add_parser("run", help="Run a .ppy or .cppy program")
    run_parser.add_argument("file", help="Source or compiled program")
    run_parser.add_argument(
        "program_args",
        nargs=argparse.REMAINDER,
        help="Arguments passed to the program (place after --)",
    )

    compile_parser = commands.add_parser(
        "compile", help="Create a portable .cppy artifact"
    )
    compile_parser.add_argument("file", help="Source .ppy program")
    compile_parser.add_argument("-o", "--output", help="Output .cppy path")

    transpile_parser = commands.add_parser(
        "transpile", help="Generate readable Python source"
    )
    transpile_parser.add_argument("file", help="Source .ppy program")
    transpile_parser.add_argument("-o", "--output", help="Output .py path")

    check_parser = commands.add_parser(
        "check", help="Parse and compile without executing"
    )
    check_parser.add_argument("file", help="Source .ppy program")

    format_parser = commands.add_parser(
        "format", help="Canonicalize keywords and indentation"
    )
    format_parser.add_argument("file", help="Source .ppy program")
    format_parser.add_argument(
        "--check", action="store_true", help="Check formatting without writing"
    )

    commands.add_parser("repl", help="Launch the interactive language shell")

    install_parser = commands.add_parser(
        "install", help="Install a validated PyPI package into this Python environment"
    )
    install_parser.add_argument("package", help="Package name and optional version")
    install_parser.add_argument("--upgrade", action="store_true")
    install_parser.add_argument(
        "--dry-run", action="store_true", help="Ask pip to resolve without installing"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return

    try:
        config = ConfigManager().load()
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    grammar = Path(args.grammar).expanduser() if args.grammar else config.grammar_path
    debug = bool(args.debug or config.verbose)
    color = None if config.color_enabled and not args.no_color else False

    if args.command == "run":
        program_args = list(args.program_args)
        if program_args[:1] == ["--"]:
            program_args = program_args[1:]
        run_ppy_file(
            args.file,
            program_args,
            grammar_file=grammar,
            debug=debug,
            color=color,
        )
    elif args.command == "compile":
        compile_ppy_file(args.file, args.output, grammar_file=grammar)
    elif args.command == "transpile":
        transpile_ppy_file(args.file, args.output, grammar_file=grammar)
    elif args.command == "check":
        check_ppy_file(args.file, grammar_file=grammar)
    elif args.command == "format":
        format_ppy_file(args.file, check=args.check, grammar_file=grammar)
    elif args.command == "repl":
        start_repl(grammar_file=grammar)
    elif args.command == "install":
        try:
            PackageManager().install(
                args.package, upgrade=args.upgrade, dry_run=args.dry_run
            )
        except (ValueError, RuntimeError) as exc:
            print(f"Package error: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
