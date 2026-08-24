
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


class PackageManager:
    def __init__(self) -> None:
        self._python_executable = shutil.which("python") or sys.executable

    def install(self, package: str) -> None:
        if not package or package.strip() == "":
            print("Usage: install <package-name>")
            return

        package = package.strip()
        print(f"Installing '{package}' from PyPI...")

        cmd = [sys.executable, "-m", "pip", "install", package]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="")

        if result.returncode != 0:
            raise RuntimeError(f"pip install failed with exit code {result.returncode}")

        print(f"Package '{package}' installed successfully.")