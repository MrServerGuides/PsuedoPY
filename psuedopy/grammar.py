from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from psuedopy.errors import TranspilerError


@dataclass(frozen=True)
class KeywordSpec:
    spelling: str
    python_target: str
    category: str
    canonical: str
    blocks: bool = False


class Grammar:
    """Loaded, case-insensitive keyword grammar used by every language tool."""

    def __init__(self, specs: Iterable[KeywordSpec]) -> None:
        by_name: dict[str, KeywordSpec] = {}
        for spec in specs:
            by_name[spec.spelling.casefold()] = spec
        self._by_name = by_name

    @classmethod
    def load(cls, path: str | Path | None = None) -> Grammar:
        try:
            if path is None:
                resource = resources.files("psuedopy").joinpath("data", "keywords.json")
                with resource.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
            else:
                with Path(path).open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise TranspilerError(f"Unable to load grammar: {exc}") from exc

        if not isinstance(data, Mapping):
            raise TranspilerError("Grammar must contain a JSON object")

        if "keywords" in data:
            return cls._from_structured(data["keywords"])
        return cls._from_simple_map(data)

    @classmethod
    def _from_structured(cls, raw: object) -> Grammar:
        if not isinstance(raw, Mapping):
            raise TranspilerError("The grammar `keywords` field must be an object")

        specs = []
        for spelling, value in raw.items():
            if not isinstance(spelling, str) or not isinstance(value, Mapping):
                raise TranspilerError("Every grammar keyword must be an object")
            target = value.get("python_target")
            category = value.get("category")
            if not isinstance(target, str) or not isinstance(category, str):
                raise TranspilerError(
                    f"Keyword {spelling!r} needs string python_target and category"
                )
            canonical = value.get("canonical", spelling)
            if not isinstance(canonical, str):
                raise TranspilerError(
                    f"Keyword {spelling!r} has a non-string canonical form"
                )
            spec = KeywordSpec(
                spelling=spelling,
                python_target=target,
                category=category,
                canonical=canonical,
                blocks=bool(value.get("blocks", False)),
            )
            specs.append(spec)
            aliases = value.get("aliases", [])
            if not isinstance(aliases, list) or not all(
                isinstance(alias, str) for alias in aliases
            ):
                raise TranspilerError(
                    f"Keyword {spelling!r} has an invalid aliases list"
                )
            specs.extend(
                KeywordSpec(
                    spelling=alias,
                    python_target=target,
                    category=category,
                    canonical=canonical,
                    blocks=spec.blocks,
                )
                for alias in aliases
            )
        return cls(specs)

    @classmethod
    def _from_simple_map(cls, raw: Mapping[object, object]) -> Grammar:
        built_in = cls.load()
        specs = []
        for spelling, target in raw.items():
            if not isinstance(spelling, str) or not isinstance(target, str):
                raise TranspilerError(
                    "Simple grammar entries must map strings to strings"
                )
            previous = built_in.resolve(spelling)
            specs.append(
                KeywordSpec(
                    spelling=spelling,
                    python_target=target,
                    category=previous.category if previous else "expression",
                    canonical=previous.canonical if previous else spelling,
                    blocks=previous.blocks if previous else False,
                )
            )
        return cls(specs)

    def resolve(self, spelling: str) -> KeywordSpec | None:
        return self._by_name.get(spelling.casefold())

    def canonical(self, spelling: str) -> str | None:
        spec = self.resolve(spelling)
        return spec.canonical if spec else None

    def items(self) -> Iterable[tuple[str, KeywordSpec]]:
        return self._by_name.items()

    @property
    def simple_map(self) -> dict[str, str]:
        return {spec.spelling: spec.python_target for spec in self._by_name.values()}
