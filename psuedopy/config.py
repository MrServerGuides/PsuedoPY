
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None


@dataclass
class PsuedoPYConfig:

    grammar_path: Optional[Path] = None
    theme: str = "dark"
    color_enabled: bool = True
    verbose: bool = False


class ConfigManager:

    def __init__(self, cwd: Optional[Path] = None) -> None:
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
                self._merge_dict(config, table)

        return config

    @staticmethod
    def _read_toml(path: Path) -> Dict[str, Any]:
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
        self._merge_dict(config, table)

    @staticmethod
    def _merge_dict(config: PsuedoPYConfig, table: Dict[str, Any]) -> None:
        if "grammar_path" in table:
            raw = table["grammar_path"]
            if raw:
                config.grammar_path = Path(raw)
        if "theme" in table:
            config.theme = str(table["theme"])
        if "color_enabled" in table:
            config.color_enabled = bool(table["color_enabled"])
        if "verbose" in table:
            config.verbose = bool(table["verbose"])