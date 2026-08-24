from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Sequence


class PackageManager:
    _PACKAGE_SPEC = re.compile(
        r"^[A-Za-z0-9][A-Za-z0-9._-]*"
        r"(?:\[[A-Za-z0-9_,.-]+\])?"
        r"(?:(?:==|!=|~=|>=|<=|>|<)[A-Za-z0-9][A-Za-z0-9.*+_-]*)?$"
    )

    def __init__(self, python_executable: str | None = None) -> None:
        self._python_executable = python_executable or sys.executable

    def install(
        self,
        package: str,
        *,
        upgrade: bool = False,
        dry_run: bool = False,
    ) -> None:
        if not package or package.strip() == "":
            raise ValueError("Package name cannot be empty")

        package = package.strip()
        if not self._PACKAGE_SPEC.fullmatch(package):
            raise ValueError(
                "Package must be a PyPI name with an optional version constraint; "
                "URLs, paths, spaces, and pip flags are not accepted"
            )

        command = [
            self._python_executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
        ]
        if upgrade:
            command.append("--upgrade")
        if dry_run:
            command.append("--dry-run")
        command.append(package)

        action = "Checking" if dry_run else "Installing"
        print(f"{action} '{package}' from PyPI using {self._python_executable}...")

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=600,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"Unable to run pip: {exc}") from exc

        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)

        if result.returncode != 0:
            raise RuntimeError(f"pip install failed with exit code {result.returncode}")

        if not dry_run:
            print(f"Package '{package}' installed successfully.")

    @property
    def command_prefix(self) -> Sequence[str]:
        return (self._python_executable, "-m", "pip")
