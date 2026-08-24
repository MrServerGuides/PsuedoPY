# Command-line reference

The primary executable is `psuedopy`; `pseudopy` and `ppyx` are aliases.

## Global options

```text
--version          Show the installed version
--grammar PATH     Load a custom grammar JSON file
--debug            Include generated Python in diagnostics
--no-color         Disable ANSI colors
```

Global options appear before the subcommand.

## `run`

Run source or a compiled artifact:

```console
psuedopy run program.ppy
psuedopy run program.cppy
psuedopy run program.ppy -- first-argument second-argument
```

Program arguments are available through `sys.argv` after importing `sys`.

## `check`

Parse and compile without executing:

```console
psuedopy check program.ppy
```

Exit status is `0` for valid source, `1` for a language error, and `2` for an I/O or
configuration error.

## `format`

Canonicalize keywords and indentation in place:

```console
psuedopy format program.ppy
psuedopy format program.ppy --check
```

`--check` writes nothing and exits with status `1` when formatting is needed.

## `transpile`

Create readable Python:

```console
psuedopy transpile program.ppy
psuedopy transpile program.ppy -o generated/program.py
```

Generated files may import `psuedopy.runtime` for inclusive or fixed-count repeat
helpers, so the package must remain installed.

## `compile`

Create a portable `.cppy` version-2 artifact:

```console
psuedopy compile program.ppy
psuedopy compile program.ppy -o dist/program.cppy
```

The artifact stores UTF-8 generated and original source plus a versioned JSON
manifest and SHA-256 integrity hashes. It does not store Python `marshal` or pickle
data, so it works across supported Python versions. Rebuild artifacts when moving
between incompatible PsuedoPY major versions.

Compiled programs are executable code, not a security boundary. Only run artifacts
from trusted sources.

## `repl`

Launch the persistent interactive environment:

```console
psuedopy repl
```

Commands are `:help`, `:reset`, `:quit`, `cancel`, and `install <package>`.

## `install`

Install a validated PyPI requirement with the running Python interpreter:

```console
psuedopy install requests
psuedopy install "requests>=2.32"
psuedopy install requests --upgrade
psuedopy install requests --dry-run
```

URLs, local paths, whitespace, and pip flags are rejected. Installation still runs
third-party packaging code and should be performed only inside a virtual environment.
