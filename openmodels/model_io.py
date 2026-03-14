from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import load_json, load_yaml
from .loader import load_openapi_document
from .normalize import normalize_openapi_document


def _load_raw_document(path: Path) -> Any:
    if path.suffix in {".yaml", ".yml"}:
        return load_yaml(path)
    if path.suffix == ".json":
        return load_json(path)
    raise ValueError(f"Unsupported input file type: {path.suffix}")


def load_canonical_model(path: str | Path) -> dict[str, Any]:
    source_path = Path(path)
    raw_document = _load_raw_document(source_path)
    if not isinstance(raw_document, dict):
        raise ValueError("Model input must be a JSON or YAML object.")

    if "openapi" in raw_document:
        document = load_openapi_document(source_path)
        return normalize_openapi_document(document)

    if "version" in raw_document and "entities" in raw_document:
        return raw_document

    raise ValueError(
        "Input must be either an OpenAPI document with x-openmodels or a canonical model JSON document."
    )
