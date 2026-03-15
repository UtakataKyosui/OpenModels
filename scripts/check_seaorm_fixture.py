#!/usr/bin/env python3

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from openmodels.cli import generate_artifacts_to_directory
from openmodels.common import ensure_directory


def prepare_fixture(
    input_path: Path,
    fixture_dir: Path,
    work_dir: Path,
) -> list[Path]:
    if not fixture_dir.exists():
        raise FileNotFoundError(f"Fixture directory does not exist: {fixture_dir}")

    ensure_directory(work_dir)
    shutil.copytree(fixture_dir, work_dir, dirs_exist_ok=True)
    return generate_artifacts_to_directory(
        input_path,
        work_dir / "src",
        target="seaorm-rust",
    )


def cargo_check_fixture(work_dir: Path) -> None:
    subprocess.run(
        ["cargo", "check", "--manifest-path", str(work_dir / "Cargo.toml")],
        check=True,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare and optionally cargo-check the SeaORM blog fixture."
    )
    parser.add_argument(
        "--input",
        default=str(ROOT_DIR / "examples" / "openapi" / "blog-api.yaml"),
        help="Path to the OpenAPI document used for SeaORM generation.",
    )
    parser.add_argument(
        "--fixture-dir",
        default=str(ROOT_DIR / "examples" / "fixtures" / "seaorm-blog"),
        help="Path to the SeaORM fixture template directory.",
    )
    parser.add_argument(
        "--work-dir",
        help="Directory where the prepared fixture should be written. Defaults to a temp directory.",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Prepare the fixture files but skip cargo check.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    work_dir = (
        Path(args.work_dir)
        if args.work_dir
        else Path(tempfile.mkdtemp(prefix="openmodels-seaorm-fixture-"))
    )
    written_paths = prepare_fixture(
        input_path=Path(args.input),
        fixture_dir=Path(args.fixture_dir),
        work_dir=work_dir,
    )
    print(f"Prepared SeaORM fixture at: {work_dir}")
    for path in written_paths:
        print(f"  - {path}")

    if args.prepare_only:
        return

    cargo_check_fixture(work_dir)
    print(f"cargo check passed for fixture: {work_dir}")


if __name__ == "__main__":
    main()
