from __future__ import annotations

import argparse
from pathlib import Path

from .common import ensure_directory
from .drizzle import generate_drizzle_schema
from .loader import load_openapi_document
from .normalize import normalize_openapi_document


def generate_to_directory(
    input_path: str | Path,
    out_dir: str | Path,
    filename: str = "schema.ts",
) -> Path:
    document = load_openapi_document(input_path)
    canonical_model = normalize_openapi_document(document)
    output = generate_drizzle_schema(canonical_model)

    out_path = Path(out_dir)
    ensure_directory(out_path)
    target_path = out_path / filename
    target_path.write_text(output)
    return target_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate Drizzle schema files from OpenAPI + x-openmodels."
    )
    parser.add_argument("--input", required=True, help="Path to the OpenAPI document.")
    parser.add_argument(
        "--out-dir",
        required=True,
        help="Directory to write generated files into.",
    )
    parser.add_argument(
        "--filename",
        default="schema.ts",
        help="Generated file name. Defaults to schema.ts.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    target_path = generate_to_directory(args.input, args.out_dir, args.filename)
    print(f"Generated Drizzle schema: {target_path}")


if __name__ == "__main__":
    main()
