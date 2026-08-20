from pathlib import Path
from psuedopy.main import run_ppy_file

def test_run_prints_text(tmp_path, capsys):
    src = tmp_path / "hello.ppy"
    src.write_text('Text("hello")\n', encoding="utf-8")
    run_ppy_file(str(src))
    captured = capsys.readouterr()
    assert "hello" in captured.out
