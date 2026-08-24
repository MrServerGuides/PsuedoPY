"""
Integration tests for CLI end-to-end functionality.
These tests verify that the CLI works correctly with actual file I/O.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from psuedopy.main import (
    check_ppy_file,
    compile_ppy_file,
    format_ppy_file,
    run_ppy_file,
)


class TestRunIntegration:
    """Integration tests for run_ppy_file."""

    def test_run_simple_text(self, capsys):
        """Test running a simple Text statement."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ppy", delete=False) as f:
            f.write('Text("Hello")\n')
            f.flush()
            ppy_file = f.name

        try:
            run_ppy_file(ppy_file)
            captured = capsys.readouterr()
            assert "Hello" in captured.out
        finally:
            Path(ppy_file).unlink()

    def test_run_with_control_flow(self, capsys):
        """Test running code with control flow."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ppy", delete=False) as f:
            f.write("When 1 > 0\n")
            f.write('    Text("True")\n')
            f.write("End\n")
            f.flush()
            ppy_file = f.name

        try:
            run_ppy_file(ppy_file)
            captured = capsys.readouterr()
            assert "True" in captured.out
        finally:
            Path(ppy_file).unlink()

    def test_run_file_not_found(self):
        """Test error handling when file doesn't exist."""
        with pytest.raises(SystemExit) as exc_info:
            run_ppy_file("nonexistent.ppy")
        assert exc_info.value.code == 2

    def test_run_with_function(self, capsys):
        """Test running code with function definition."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ppy", delete=False) as f:
            f.write("Function greet(name)\n")
            f.write('    Text("Hello, " + name)\n')
            f.write("End\n")
            f.write('greet("World")\n')
            f.flush()
            ppy_file = f.name

        try:
            run_ppy_file(ppy_file)
            captured = capsys.readouterr()
            assert "Hello, World" in captured.out
        finally:
            Path(ppy_file).unlink()


class TestCompileIntegration:
    """Integration tests for compile_ppy_file."""

    def test_compile_creates_file(self, capsys):
        """Test that compile creates a .cppy file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ppy", delete=False) as f:
            f.write('Text("test")\n')
            f.flush()
            ppy_file = f.name

        cppy_file = ppy_file.replace(".ppy", ".cppy")

        try:
            compile_ppy_file(ppy_file)
            captured = capsys.readouterr()
            assert "Compiled" in captured.out
            assert Path(cppy_file).exists()

            # Verify it has the magic header
            with open(cppy_file, "rb") as f:
                magic = f.read(5)
                assert magic == b"PPY\x00\x02"
        finally:
            Path(ppy_file).unlink()
            if Path(cppy_file).exists():
                Path(cppy_file).unlink()

    def test_compile_with_explicit_output(self, capsys):
        """Test compile with explicit output path."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ppy", delete=False) as f:
            f.write('Text("test")\n')
            f.flush()
            ppy_file = f.name

        with tempfile.NamedTemporaryFile(suffix=".cppy", delete=False) as f:
            cppy_file = f.name

        try:
            compile_ppy_file(ppy_file, cppy_file)
            captured = capsys.readouterr()
            assert "Compiled" in captured.out
            assert Path(cppy_file).exists()
        finally:
            Path(ppy_file).unlink()
            if Path(cppy_file).exists():
                Path(cppy_file).unlink()

    def test_compile_invalid_syntax(self):
        """Test compile with invalid syntax."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ppy", delete=False) as f:
            f.write("x = \n")  # Incomplete statement
            f.flush()
            ppy_file = f.name

        try:
            with pytest.raises(SystemExit) as exc_info:
                compile_ppy_file(ppy_file)
            assert exc_info.value.code == 1
        finally:
            Path(ppy_file).unlink()


class TestFormatIntegration:
    """Integration tests for format_ppy_file."""

    def test_format_normalizes_keywords(self, capsys):
        """Test that format normalizes keyword casing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ppy", delete=False) as f:
            f.write("when x > 5\n")
            f.write('    text("yes")\n')
            f.write("end\n")
            f.flush()
            ppy_file = f.name

        try:
            format_ppy_file(ppy_file)
            captured = capsys.readouterr()
            assert "Formatted" in captured.out

            # Verify file was actually modified
            content = Path(ppy_file).read_text()
            assert "When" in content
            assert "Text" in content or "End" in content
        finally:
            Path(ppy_file).unlink()

    def test_format_file_not_found(self):
        """Test format with non-existent file."""
        with pytest.raises(SystemExit) as exc_info:
            format_ppy_file("nonexistent.ppy")
        assert exc_info.value.code == 2


class TestCheckIntegration:
    """Integration tests for check_ppy_file."""

    def test_check_valid_file(self, capsys):
        """Test check on valid file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ppy", delete=False) as f:
            f.write('Text("hello")\n')
            f.flush()
            ppy_file = f.name

        try:
            check_ppy_file(ppy_file)
            captured = capsys.readouterr()
            assert "OK" in captured.out
        finally:
            Path(ppy_file).unlink()

    def test_check_invalid_syntax(self):
        """Test check on file with syntax errors."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ppy", delete=False) as f:
            f.write("x = \n")  # Incomplete
            f.flush()
            ppy_file = f.name

        try:
            with pytest.raises(SystemExit) as exc_info:
                check_ppy_file(ppy_file)
            assert exc_info.value.code == 1
        finally:
            Path(ppy_file).unlink()

    def test_check_file_not_found(self):
        """Test check on non-existent file."""
        with pytest.raises(SystemExit) as exc_info:
            check_ppy_file("nonexistent.ppy")
        assert exc_info.value.code == 2
