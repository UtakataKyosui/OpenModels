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
        description="Generate a migration plan between two OpenModels inputs."
    )
    parser.add_argument("--from-input", required=True, help="Previous model input path.")
    parser.add_argument("--to-input", required=True, help="Next model input path.")
    parser.add_argument("--out", required=True, help="Output JSON file path.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        process = run_rust_cli(
            [
                "plan-migration",
                "--from-input",
                args.from_input,
                "--to-input",
                args.to_input,
                "--out",
                args.out,
            ]
        )
    except subprocess.CalledProcessError as error:
        print_subprocess_error(error)
        raise SystemExit(error.returncode) from error
    print_process_output(process)


if __name__ == "__main__":
    main()
