#!/usr/bin/env python3

import argparse
import sys
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from openmodels.rust_cli import print_process_output, print_subprocess_error, run_rust_cli


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate DTO mapper files from an OpenAPI + x-openmodels document."
    )
    parser.add_argument("--input", required=True, help="Path to the OpenAPI document.")
    parser.add_argument(
        "--out-dir",
        required=True,
        help="Directory to write generated mapper files into.",
    )
    parser.add_argument(
        "--filename",
        default="dto-mappers.ts",
        help="Mapper file name. Defaults to dto-mappers.ts.",
    )
    parser.add_argument(
        "--diagnostics-filename",
        default="dto-mappers.diagnostics.json",
        help="Diagnostics JSON file name. Defaults to dto-mappers.diagnostics.json.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        process = run_rust_cli(
            [
                "generate-mappers",
                "--input",
                args.input,
                "--out-dir",
                args.out_dir,
                "--filename",
                args.filename,
                "--diagnostics-filename",
                args.diagnostics_filename,
            ]
        )
    except subprocess.CalledProcessError as error:
        print_subprocess_error(error)
        raise SystemExit(error.returncode) from error
    print_process_output(process)


if __name__ == "__main__":
    main()
