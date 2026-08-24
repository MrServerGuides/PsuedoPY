# Contributing

Thank you for improving PsuedoPY.

## Development setup

1. Fork and clone the repository.
2. Create and activate a Python 3.10+ virtual environment.
3. Run `python -m pip install -e ".[dev]"`.
4. Create a focused branch.

Before opening a pull request, run:

```console
ruff check .
ruff format --check .
pytest --cov=psuedopy
python -m build
```

## Language changes

A language change must include:

- A clear syntax and semantic description
- Parser/transpiler tests for valid and invalid forms
- Formatter coverage
- Runtime or compiled-artifact tests when applicable
- Updates to `keywords.json`, the language reference, and changelog
- Backward-compatibility notes

Do not add a keyword only to `grammar_map.json`; `keywords.json` is authoritative.

## Pull requests

Keep changes narrowly scoped, include tests, and explain user-visible behavior. CI must
pass on all supported platforms. Maintainers may request a design discussion before
accepting syntax that creates ambiguity or breaks Python interoperability.
