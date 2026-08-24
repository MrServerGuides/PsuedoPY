"""
Wrapper functions that bridge the CLI to the current compiler/transpiler architecture.
These functions provide a clean interface for the CLI.
"""

from __future__ import annotations

import sys
from pathlib import Path

from psuedopy.compiler import Compiler, CompilerError
from psuedopy.exceptions import print_ppy_error
from psuedopy.formatter import PsuedoPYFormatter, FormatterError
from psuedopy.repl import PsuedoPYRepl
from psuedopy.transpiler import TranspilerError


def run_ppy_file(file_path: str) -> None:
    """
    Read a .ppy file, transpile it, compile it, and execute it.
    
    Args:
        file_path: Path to the .ppy file
        
    Raises:
        SystemExit on file not found or execution errors
    """
    path = Path(file_path)
    
    if not path.exists():
        print(f"Error: File '{file_path}' not found.", file=sys.stderr)
        raise SystemExit(2)
    
    if not path.is_file():
        print(f"Error: '{file_path}' is not a file.", file=sys.stderr)
        raise SystemExit(2)
    
    try:
        source = path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error reading file '{file_path}': {e}", file=sys.stderr)
        raise SystemExit(2)
    
    compiler = Compiler()
    
    try:
        # Transpile and compile
        translated = compiler.transpile(source)
        code_obj = compiler.compile_to_code(source, filename=str(path))
        
        # Execute with proper globals/locals
        globs = {'__name__': '__main__', '__file__': str(path)}
        exec(code_obj, globs, globs)
        
    except TranspilerError as e:
        print_ppy_error(e, compiler.transpiler.translate(source).source_map)
        raise SystemExit(1)
    except CompilerError as e:
        print(f"Compilation error: {e}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as e:
        # Try to provide context-aware error reporting
        try:
            translated = compiler.transpile(source)
            print_ppy_error(e, translated.source_map)
        except:
            # Fallback: print raw exception
            print(f"Runtime error: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
        raise SystemExit(1)


def compile_ppy_file(input_path: str, output_path: str | None = None) -> None:
    """
    Compile a .ppy file to a .cppy file.
    
    Args:
        input_path: Path to the .ppy file
        output_path: Path to write compiled file. Defaults to input with .cppy extension.
        
    Raises:
        SystemExit on file not found or compilation errors
    """
    path = Path(input_path)
    
    if not path.exists():
        print(f"Error: File '{input_path}' not found.", file=sys.stderr)
        raise SystemExit(2)
    
    if not path.is_file():
        print(f"Error: '{input_path}' is not a file.", file=sys.stderr)
        raise SystemExit(2)
    
    try:
        source = path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error reading file '{input_path}': {e}", file=sys.stderr)
        raise SystemExit(2)
    
    # Determine output path
    if output_path is None:
        output_path = str(path.with_suffix('.cppy'))
    
    compiler = Compiler()
    
    try:
        output = compiler.write_compiled(source, output_path, filename=str(path))
        print(f"Compiled: {input_path} -> {output}")
    except CompilerError as e:
        print(f"Compilation error: {e}", file=sys.stderr)
        raise SystemExit(1)
    except TranspilerError as e:
        print(f"Transpiler error: {e}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as e:
        print(f"Error compiling file: {e}", file=sys.stderr)
        raise SystemExit(1)


def format_ppy_file(file_path: str) -> None:
    """
    Format a .ppy file in-place using canonical keyword casing and indentation.
    
    Args:
        file_path: Path to the .ppy file
        
    Raises:
        SystemExit on file not found or formatting errors
    """
    path = Path(file_path)
    
    if not path.exists():
        print(f"Error: File '{file_path}' not found.", file=sys.stderr)
        raise SystemExit(2)
    
    if not path.is_file():
        print(f"Error: '{file_path}' is not a file.", file=sys.stderr)
        raise SystemExit(2)
    
    formatter = PsuedoPYFormatter()
    
    try:
        formatter.format_file(path)
        print(f"Formatted: {file_path}")
    except FormatterError as e:
        print(f"Formatting error: {e}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as e:
        print(f"Error formatting file: {e}", file=sys.stderr)
        raise SystemExit(1)


def check_ppy_file(file_path: str) -> None:
    """
    Check a .ppy file for syntax errors without running or formatting it.
    
    Args:
        file_path: Path to the .ppy file
        
    Raises:
        SystemExit if there are syntax errors
    """
    path = Path(file_path)
    
    if not path.exists():
        print(f"Error: File '{file_path}' not found.", file=sys.stderr)
        raise SystemExit(2)
    
    if not path.is_file():
        print(f"Error: '{file_path}' is not a file.", file=sys.stderr)
        raise SystemExit(2)
    
    try:
        source = path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error reading file '{file_path}': {e}", file=sys.stderr)
        raise SystemExit(2)
    
    compiler = Compiler()
    
    try:
        # Just transpile and compile, don't execute
        compiler.transpile(source)
        compiler.compile_to_code(source, filename=str(path))
        print(f"OK: {file_path}")
    except CompilerError as e:
        print(f"Compilation error in {file_path}: {e}", file=sys.stderr)
        raise SystemExit(1)
    except TranspilerError as e:
        print(f"Syntax error in {file_path}: {e}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as e:
        print(f"Error checking file: {e}", file=sys.stderr)
        raise SystemExit(1)


def start_repl() -> None:
    """
    Start the interactive PsuedoPY REPL.
    """
    repl = PsuedoPYRepl()
    repl.run()
