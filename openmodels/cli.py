from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from .registry import list_adapters
from .rust_cli import parse_generated_paths, print_subprocess_error, run_rust_cli


def generate_artifacts_to_directory(
    input_path: str | Path,
    out_dir: str | Path,
    target: str | None = None,
    filename: str | None = None,
) -> list[Path]:
    args = [
        "generate",
        "--input",
        str(input_path),
        "--out-dir",
        str(out_dir),
    ]
    if filename:
        args.extend(["--filename", filename])
    if target:
        args.extend(["--target", target])
    args.append("--json")

    process = run_rust_cli(args)
    return parse_generated_paths(process.stdout)


def generate_to_directory(
    input_path: str | Path,
    out_dir: str | Path,
    filename: str = "schema.ts",
) -> Path:
    generated_paths = generate_artifacts_to_directory(
        input_path,
        out_dir,
        target="drizzle-pg",
        filename=filename,
    )
    return generated_paths[0]


def build_parser() -> argparse.ArgumentParser:
    available_targets = [adapter.key for adapter in list_adapters()]
    parser = argparse.ArgumentParser(
        description="Generate ORM model files from OpenAPI + x-openmodels."
    )
    parser.add_argument("--input", required=True, help="Path to the OpenAPI document.")
    parser.add_argument(
        "--out-dir",
        required=True,
        help="Directory to write generated files into.",
    )
    parser.add_argument(
        "--filename",
        help="Override the generated file name for single-file targets.",
    )
    parser.add_argument(
        "--target",
        choices=available_targets,
        help="Override the backend adapter target declared in x-openmodels.outputs.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        written_paths = generate_artifacts_to_directory(
            args.input,
            args.out_dir,
            target=args.target,
            filename=args.filename,
        )
    except subprocess.CalledProcessError as error:
        print_subprocess_error(error)
        raise SystemExit(error.returncode) from error

    for path in written_paths:
        if args.target:
            print(f"Generated {args.target} artifact: {path}")
        else:
            print(f"Generated declared artifact: {path}")


if __name__ == "__main__":
    main()
