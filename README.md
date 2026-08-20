# PsuedoPY

PsuedoPY is a beginner-friendly language that compiles to Python.

Think of it like this:

- Python is the engine.
- PsuedoPY is a friendly steering wheel on top of that engine.

You write simple, English-like code in `.ppy` files, and PsuedoPY translates it into real Python before running it.

## Why PsuedoPY?

- Uses words like `Text`, `Function`, `When`, and `Otherwise`
- Easier to read for first-time programmers
- Still 100% compatible with Python packages
- You can still use normal Python code if you want

## Features

- Run `.ppy` files directly
- Compile `.ppy` into `.cppy` bytecode
- Built-in interactive REPL
- Install Python packages from inside PsuedoPY
- Token-aware transpiler that does not touch strings or comments
- Friendly error messages that show your original `.ppy` line numbers

- Python 3.10, 3.11, or 3.12
- pip


1. Install PsuedoPY:
pip install -e .