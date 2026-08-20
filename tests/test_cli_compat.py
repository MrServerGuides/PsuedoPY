def test_cli_exports_exist():
    import psuedopy.main as main

    assert hasattr(main, "compile_ppy_file")
    assert hasattr(main, "format_ppy_file")
    assert hasattr(main, "run_ppy_file")
    assert hasattr(main, "start_repl")
