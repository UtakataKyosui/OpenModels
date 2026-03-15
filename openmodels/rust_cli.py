from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .common import ROOT


def rust_binary_command() -> list[str]:
    override = os.environ.get("OPENMODELS_RS_BIN")
    if override:
        return [override]

    binary_name = "openmodels-rs.exe" if sys.platform == "win32" else "openmodels-rs"
    binary_path = ROOT / "target" / "debug" / binary_name
    if binary_path.exists():
        return [str(binary_path)]

    return ["cargo", "run", "-q", "-p", "openmodels-rs", "--"]


def run_rust_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        rust_binary_command() + args,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def print_process_output(process: subprocess.CompletedProcess[str]) -> None:
    if process.stdout:
        print(process.stdout, end="")
    if process.stderr:
        print(process.stderr, file=sys.stderr, end="")


def print_subprocess_error(error: subprocess.CalledProcessError) -> None:
    if error.stdout:
        print(error.stdout, end="")
    if error.stderr:
        print(error.stderr, file=sys.stderr, end="")


def parse_generated_paths(stdout: str) -> list[Path]:
    paths: list[Path] = []
    marker = " artifact: "
    for line in stdout.splitlines():
        if line.startswith("Generated ") and marker in line:
            paths.append(Path(line.split(marker, 1)[1]))
    return paths
