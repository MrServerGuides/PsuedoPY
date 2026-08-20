
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from psuedopy.cli import main


class TestRunCommand:
    """Test the 'ppyx run' command."""

    def test_run_simple_program(self, monkeypatch):
        """Test running a simple .ppy file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ppy', delete=False) as f:
            f.write('Text("Hello from PsuedoPY")\n')
            f.flush()
            ppy_file = f.name

        try:
            monkeypatch.setattr(sys, "argv", ["ppyx", "run", ppy_file])
            with patch('builtins.print') as mock_print:
                main()
                # The Text(...) should be transpiled to print(...) and executed
                mock_print.assert_called()
        finally:
            Path(ppy_file).unlink()

    def test_run_missing_file(self, monkeypatch, capsys):
        """Test running a non-existent file."""
        monkeypatch.setattr(sys, "argv", ["ppyx", "run", "nonexistent.ppy"])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "not found" in captured.err


class TestCompileCommand:
    """Test the 'ppyx compile' command."""

    def test_compile_program(self, monkeypatch, capsys):
        """Test compiling a .ppy file to .cppy."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ppy', delete=False) as f:
            f.write('Text("test")\n')
            f.flush()
            ppy_file = f.name

        try:
            cppy_file = ppy_file.replace('.ppy', '.cppy')
            monkeypatch.setattr(sys, "argv", ["ppyx", "compile", ppy_file])
            main()
            
            captured = capsys.readouterr()
            assert "Compiled" in captured.out
            assert Path(cppy_file).exists()
            
            Path(cppy_file).unlink()
        finally:
            Path(ppy_file).unlink()

    def test_compile_with_output(self, monkeypatch, capsys):
        """Test compiling with explicit output path."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ppy', delete=False) as f:
            f.write('Text("test")\n')
            f.flush()
            ppy_file = f.name

        with tempfile.NamedTemporaryFile(mode='w', suffix='.cppy', delete=False) as f:
            cppy_file = f.name

        try:
            monkeypatch.setattr(sys, "argv", ["ppyx", "compile", ppy_file, "-o", cppy_file])
            main()
            
            captured = capsys.readouterr()
            assert "Compiled" in captured.out
            assert Path(cppy_file).exists()
        finally:
            Path(ppy_file).unlink()
            if Path(cppy_file).exists():
                Path(cppy_file).unlink()

    def test_compile_missing_file(self, monkeypatch, capsys):
        """Test compiling a non-existent file."""
        monkeypatch.setattr(sys, "argv", ["ppyx", "compile", "nonexistent.ppy"])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2


class TestFormatCommand:
    """Test the 'ppyx format' command."""

    def test_format_program(self, monkeypatch, capsys):
        """Test formatting a .ppy file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ppy', delete=False) as f:
            # Use lowercase keywords that should be canonicalized
            f.write('when x > 5\n')
            f.write('    text("yes")\n')
            f.write('end\n')
            f.flush()
            ppy_file = f.name

        try:
            monkeypatch.setattr(sys, "argv", ["ppyx", "format", ppy_file])
            main()
            
            captured = capsys.readouterr()
            assert "Formatted" in captured.out
            
            # Read the formatted file
            content = Path(ppy_file).read_text()
            assert "When" in content  # Should be canonicalized
        finally:
            Path(ppy_file).unlink()

    def test_format_missing_file(self, monkeypatch, capsys):
        """Test formatting a non-existent file."""
        monkeypatch.setattr(sys, "argv", ["ppyx", "format", "nonexistent.ppy"])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2


class TestCheckCommand:
    """Test the 'ppyx check' command."""

    def test_check_valid_program(self, monkeypatch, capsys):
        """Test checking a valid .ppy file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ppy', delete=False) as f:
            f.write('Text("hello")\n')
            f.flush()
            ppy_file = f.name

        try:
            monkeypatch.setattr(sys, "argv", ["ppyx", "check", ppy_file])
            main()
            
            captured = capsys.readouterr()
            assert "OK" in captured.out
        finally:
            Path(ppy_file).unlink()

    def test_check_invalid_program(self, monkeypatch, capsys):
        """Test checking an invalid .ppy file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ppy', delete=False) as f:
            # Invalid Python syntax
            f.write('x = \n')  # Incomplete statement
            f.flush()
            ppy_file = f.name

        try:
            monkeypatch.setattr(sys, "argv", ["ppyx", "check", ppy_file])
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
        finally:
            Path(ppy_file).unlink()

    def test_check_missing_file(self, monkeypatch, capsys):
        """Test checking a non-existent file."""
        monkeypatch.setattr(sys, "argv", ["ppyx", "check", "nonexistent.ppy"])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2


class TestReplCommand:
    """Test the 'ppyx repl' command."""

    def test_repl_exit(self, monkeypatch):
        """Test that REPL can be started and exited."""
        monkeypatch.setattr(sys, "argv", ["ppyx", "repl"])
        # Mock input to immediately exit
        monkeypatch.setattr("builtins.input", lambda _: "exit")
        
        main()  # Should not raise


class TestVersionFlag:
    """Test the --version flag."""

    def test_version_flag(self, monkeypatch, capsys):
        """Test --version flag."""
        monkeypatch.setattr(sys, "argv", ["ppyx", "--version"])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "0.1.0" in captured.out


class TestHelpFlag:
    """Test the --help flag."""

    def test_help_flag(self, monkeypatch, capsys):
        """Test --help flag."""
        monkeypatch.setattr(sys, "argv", ["ppyx", "--help"])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "ppyx" in captured.out.lower()
        assert "run" in captured.out.lower()
