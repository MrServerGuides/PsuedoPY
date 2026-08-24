# Configuration

PsuedoPY loads configuration in this order; later sources override earlier ones:

1. `~/.psuedopyrc`
2. `.psuedopyrc` in the current directory
3. `[tool.psuedopy]` in the current `pyproject.toml`
4. command-line flags

`.psuedopyrc` may be TOML:

```toml
grammar_path = "grammar.json"
theme = "auto"
color_enabled = true
verbose = false
```

It may also be JSON:

```json
{
  "grammar_path": "grammar.json",
  "theme": "dark",
  "color_enabled": true,
  "verbose": false
}
```

Relative grammar paths are resolved relative to the configuration file. Valid themes
are `auto`, `dark`, and `light`. Set the standard `NO_COLOR` environment variable or
use `--no-color` to disable ANSI output.

Custom grammar files can use the structured format of
`psuedopy/data/keywords.json` or a simple mapping such as:

```json
{
  "Say": "print",
  "ReadValue": "input"
}
```

Structured grammars are preferred because they specify category, canonical spelling,
aliases, and block behavior.
