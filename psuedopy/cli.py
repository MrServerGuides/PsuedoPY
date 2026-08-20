
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from psuedopy import __version__
from psuedopy.main import (
    compile_ppy_file,
    format_ppy_file,
    run_ppy_file,
    check_ppy_file,
    start_repl,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ppyx",
        description="PsuedoPY — a simplified language that compiles to Python.",
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # run command
    run_parser = subparsers.add_parser("run", help="Run a .ppy file")
    run_parser.add_argument("file", type=str, help="Path to .ppy file")

    # compile command
    compile_parser = subparsers.add_parser("compile", help="Compile a .ppy file")
    compile_parser.add_argument("file", type=str, help="Path to .ppy file")
    compile_parser.add_argument(
        "-o",
        "--output",
        type=str,
        required=False,
        help="Output .cppy path. Defaults to source path with .cppy extension.",
    )

    # check command
    check_parser = subparsers.add_parser(
        "check", help="Check a .ppy file for syntax errors"
    )
    check_parser.add_argument("file", type=str, help="Path to .ppy file")

    # format command
    format_parser = subparsers.add_parser(
        "format", help="Format a .ppy source file"
    )
    format_parser.add_argument("file", type=str, help="Path to .ppy file")

    # repl command
    subparsers.add_parser("repl", help="Launch interactive REPL")

    # install command (package manager)
    install_parser = subparsers.add_parser(
        "install", help="Install a PyPI package"
    )
    install_parser.add_argument("package", type=str, help="Package name")

    args = parser.parse_args()

    # Handle no command (show help or prompt for file)
    if args.command is None:
        path_str = input("Enter the path to your .ppy file: ").strip()
        if not path_str:
            print("No file provided.", file=sys.stderr)
            raise SystemExit(1)
        run_ppy_file(path_str)
        return

    # Route to command handlers
    if args.command == "run":
        run_ppy_file(args.file)
    elif args.command == "compile":
        output = args.output or str(Path(args.file).with_suffix(".cppy"))
        compile_ppy_file(args.file, output)
    elif args.command == "check":
        check_ppy_file(args.file)
    elif args.command == "format":
        format_ppy_file(args.file)
    elif args.command == "repl":
        start_repl()
    elif args.command == "install":
        from psuedopy.pkg_manager import PackageManager

        PackageManager().install(args.package)
    else:
        parser.print_help()
