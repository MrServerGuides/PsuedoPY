from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None


@dataclass
class PsuedoPYConfig:
    grammar_path: Path | None = None
    theme: str = "dark"
    color_enabled: bool = True
    verbose: bool = False


class ConfigManager:
    def __init__(self, cwd: Path | None = None) -> None:
        self.cwd = Path(cwd or Path.cwd())

    def load(self) -> PsuedoPYConfig:
        config = PsuedoPYConfig()

        home_rc = Path.home() / ".psuedopyrc"
        if home_rc.exists():
            self._merge_rc(config, home_rc)

        project_rc = self.cwd / ".psuedopyrc"
        if project_rc.exists():
            self._merge_rc(config, project_rc)

        pyproject = self.cwd / "pyproject.toml"
        if pyproject.exists():
            data = self._read_toml(pyproject)
            table = data.get("tool", {}).get("psuedopy", {})
            if table:
                self._merge_dict(config, table, self.cwd)

        return config

    @staticmethod
    def _read_toml(path: Path) -> dict[str, Any]:
        if tomllib is None:
            raise RuntimeError(
                "TOML support requires Python 3.11+ or the `tomli` package."
            )
        with path.open("rb") as fh:
            return tomllib.load(fh)

    def _merge_rc(self, config: PsuedoPYConfig, path: Path) -> None:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return

        if text.startswith("{"):
            import json

            data = json.loads(text)
        else:
            data = self._read_toml(path)

        table = data.get("psuedopy", data)
        if not isinstance(table, dict):
            raise ValueError(f"Configuration in {path} must be an object")
        self._merge_dict(config, table, path.parent)

    @staticmethod
    def _merge_dict(
        config: PsuedoPYConfig, table: dict[str, Any], base_dir: Path
    ) -> None:
        if "grammar_path" in table:
            raw = table["grammar_path"]
            if raw:
                if not isinstance(raw, str):
                    raise ValueError("grammar_path must be a string")
                candidate = Path(raw).expanduser()
                config.grammar_path = (
                    candidate if candidate.is_absolute() else base_dir / candidate
                ).resolve()
        if "theme" in table:
            theme = table["theme"]
            if theme not in {"auto", "dark", "light"}:
                raise ValueError("theme must be auto, dark, or light")
            config.theme = theme
        if "color_enabled" in table:
            color_enabled = table["color_enabled"]
            if not isinstance(color_enabled, bool):
                raise ValueError("color_enabled must be true or false")
            config.color_enabled = color_enabled
        if "verbose" in table:
            verbose = table["verbose"]
            if not isinstance(verbose, bool):
                raise ValueError("verbose must be true or false")
            config.verbose = verbose
