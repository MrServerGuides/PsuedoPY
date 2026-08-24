from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from psuedopy import __version__
from psuedopy.errors import CompiledFileError, CompilerError
from psuedopy.transpiler import TranslatedSource, Transpiler


@dataclass(frozen=True)
class CompiledArtifact:
    metadata: dict[str, object]
    python_code: str
    original_source: str


class Compiler:
    """Compile PsuedoPY to Python code objects or portable .cppy artifacts."""

    _CPPY_MAGIC = b"PPY\x00\x02"
    _MAX_MANIFEST_BYTES = 64 * 1024
    _MAX_ARTIFACT_BYTES = 64 * 1024 * 1024

    def __init__(self, grammar_file: str | Path | None = None) -> None:
        self.transpiler = Transpiler(grammar_file)

    def transpile(self, source: str) -> TranslatedSource:
        return self.transpiler.translate(source)

    def compile_to_code(self, source: str, filename: str = "<psuedopy>") -> Any:
        translated = self.transpile(source)
        return self.compile_translated(translated, filename)

    @staticmethod
    def compile_translated(
        translated: TranslatedSource, filename: str = "<psuedopy>"
    ) -> Any:
        try:
            return compile(translated.python_code, filename, "exec")
        except (SyntaxError, IndentationError) as exc:
            generated_line = exc.lineno or 1
            original_line = translated.source_map.original_line_no(generated_line)
            source_line = translated.source_map.original_source_line(generated_line)
            message = exc.msg if isinstance(exc, SyntaxError) else str(exc)
            if original_line <= 0:
                raise CompilerError(
                    f"Internal generated Python is invalid on generated line "
                    f"{generated_line}: {message}"
                ) from exc
            raise CompilerError(
                f"Generated Python is invalid: {message}",
                line=original_line,
                column=exc.offset or 1,
                source_line=source_line,
            ) from exc

    def write_compiled(
        self,
        source: str,
        output_path: str | Path,
        filename: str = "<psuedopy>",
    ) -> Path:
        translated = self.transpile(source)
        self.compile_translated(translated, filename)

        python_bytes = translated.python_code.encode("utf-8")
        source_bytes = source.encode("utf-8")
        metadata: dict[str, object] = {
            "format": "psuedopy-portable-source",
            "format_version": 2,
            "language_version": __version__,
            "source_filename": filename,
            "python_length": len(python_bytes),
            "source_length": len(source_bytes),
            "python_sha256": hashlib.sha256(python_bytes).hexdigest(),
            "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        }
        manifest = json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        if len(manifest) > self._MAX_MANIFEST_BYTES:
            raise CompilerError("Compiled artifact manifest is unexpectedly large")

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("wb") as handle:
            handle.write(self._CPPY_MAGIC)
            handle.write(struct.pack(">I", len(manifest)))
            handle.write(manifest)
            handle.write(python_bytes)
            handle.write(source_bytes)
        return output

    def load_artifact(self, path: str | Path) -> CompiledArtifact:
        target = Path(path)
        try:
            size = target.stat().st_size
        except OSError as exc:
            raise CompiledFileError(f"Cannot read compiled file: {exc}") from exc
        if size > self._MAX_ARTIFACT_BYTES:
            raise CompiledFileError("Compiled file exceeds the 64 MiB safety limit")

        try:
            with target.open("rb") as handle:
                magic = handle.read(len(self._CPPY_MAGIC))
                if magic != self._CPPY_MAGIC:
                    raise CompiledFileError(
                        "Unsupported or corrupt .cppy file (expected format version 2)"
                    )
                length_bytes = handle.read(4)
                if len(length_bytes) != 4:
                    raise CompiledFileError("Compiled file has a truncated manifest")
                manifest_length = struct.unpack(">I", length_bytes)[0]
                if manifest_length > self._MAX_MANIFEST_BYTES:
                    raise CompiledFileError(
                        "Compiled manifest exceeds its safety limit"
                    )
                manifest_bytes = handle.read(manifest_length)
                if len(manifest_bytes) != manifest_length:
                    raise CompiledFileError("Compiled file has a truncated manifest")
                metadata = json.loads(manifest_bytes.decode("utf-8"))
                if not isinstance(metadata, dict):
                    raise CompiledFileError("Compiled manifest must be an object")
                python_length = self._manifest_length(metadata, "python_length")
                source_length = self._manifest_length(metadata, "source_length")
                python_bytes = handle.read(python_length)
                source_bytes = handle.read(source_length)
                if (
                    len(python_bytes) != python_length
                    or len(source_bytes) != source_length
                ):
                    raise CompiledFileError("Compiled file payload is truncated")
                if handle.read(1):
                    raise CompiledFileError(
                        "Compiled file contains unexpected trailing data"
                    )
        except CompiledFileError:
            raise
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, struct.error) as exc:
            raise CompiledFileError(f"Invalid compiled file: {exc}") from exc

        self._verify_hash(metadata, "python_sha256", python_bytes)
        self._verify_hash(metadata, "source_sha256", source_bytes)
        if metadata.get("format") != "psuedopy-portable-source":
            raise CompiledFileError("Compiled file has an unknown format")
        if metadata.get("format_version") != 2:
            raise CompiledFileError("Compiled file version is not supported")
        language_version = metadata.get("language_version")
        if not isinstance(language_version, str):
            raise CompiledFileError("Compiled file has no language version")
        if language_version.split(".", 1)[0] != __version__.split(".", 1)[0]:
            raise CompiledFileError(
                f"Compiled file targets PsuedoPY {language_version}; "
                f"this runtime is {__version__}"
            )

        try:
            python_code = python_bytes.decode("utf-8")
            original_source = source_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CompiledFileError("Compiled payload is not valid UTF-8") from exc
        return CompiledArtifact(metadata, python_code, original_source)

    def load_compiled(self, path: str | Path) -> Any:
        artifact = self.load_artifact(path)
        filename = str(artifact.metadata.get("source_filename", path))
        try:
            return compile(artifact.python_code, filename, "exec")
        except (SyntaxError, IndentationError) as exc:
            raise CompiledFileError(f"Compiled payload is invalid: {exc}") from exc

    def run_compiled(self, path: str | Path) -> None:
        artifact = self.load_artifact(path)
        filename = str(artifact.metadata.get("source_filename", path))
        try:
            code = compile(artifact.python_code, filename, "exec")
        except (SyntaxError, IndentationError) as exc:
            raise CompiledFileError(f"Compiled payload is invalid: {exc}") from exc
        namespace = {"__name__": "__main__", "__file__": filename}
        exec(code, namespace, namespace)

    @staticmethod
    def _manifest_length(metadata: dict[str, object], name: str) -> int:
        value = metadata.get(name)
        if not isinstance(value, int) or value < 0:
            raise CompiledFileError(f"Compiled manifest has invalid {name}")
        return value

    @staticmethod
    def _verify_hash(metadata: dict[str, object], name: str, payload: bytes) -> None:
        expected = metadata.get(name)
        actual = hashlib.sha256(payload).hexdigest()
        if not isinstance(expected, str) or expected != actual:
            raise CompiledFileError(f"Compiled payload failed {name} verification")


__all__ = ["CompiledArtifact", "CompiledFileError", "Compiler", "CompilerError"]
