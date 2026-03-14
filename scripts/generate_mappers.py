#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from openmodels.common import ensure_directory
from openmodels.loader import load_openapi_document
from openmodels.mappers import generate_mapper_files
from openmodels.normalize import normalize_openapi_document


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

    document = load_openapi_document(args.input)
    canonical_model = normalize_openapi_document(document)
    generated_files = generate_mapper_files(
        document,
        canonical_model,
        filename=args.filename,
        diagnostics_filename=args.diagnostics_filename,
    )

    out_dir = Path(args.out_dir)
    ensure_directory(out_dir)
    for generated_file in generated_files:
        target_path = out_dir / generated_file.path
        target_path.write_text(generated_file.content)
        print(f"Generated mapper artifact: {target_path}")


if __name__ == "__main__":
    main()
