from __future__ import annotations

import argparse
from pathlib import Path

from .adapter import GeneratedFile
from .common import ensure_directory
from .generate import generate_artifacts
from .loader import load_openapi_document
from .normalize import normalize_openapi_document
from .registry import list_adapters


def _write_generated_files(
    generated_files: list[GeneratedFile],
    out_dir: str | Path,
) -> list[Path]:
    out_path = Path(out_dir)
    ensure_directory(out_path)
    written_paths: list[Path] = []
    for generated_file in generated_files:
        target_path = out_path / generated_file.path
        target_path.write_text(generated_file.content)
        written_paths.append(target_path)
    return written_paths


def generate_artifacts_to_directory(
    input_path: str | Path,
    out_dir: str | Path,
    target: str | None = None,
    filename: str | None = None,
) -> list[Path]:
    document = load_openapi_document(input_path)
    canonical_model = normalize_openapi_document(document)
    generated_files = generate_artifacts(
        canonical_model,
        target=target,
        filename=filename,
    )
    return _write_generated_files(generated_files, out_dir)


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
    written_paths = generate_artifacts_to_directory(
        args.input,
        args.out_dir,
        target=args.target,
        filename=args.filename,
    )
    for path in written_paths:
        if args.target:
            print(f"Generated {args.target} artifact: {path}")
        else:
            print(f"Generated declared artifact: {path}")


if __name__ == "__main__":
    main()
