from __future__ import annotations

from pathlib import Path
from typing import Any

import jsonschema

from .common import ROOT, load_json, load_yaml


def _load_document(path: Path) -> Any:
    if path.suffix in {".yaml", ".yml"}:
        return load_yaml(path)
    if path.suffix == ".json":
        return load_json(path)
    raise ValueError(f"Unsupported input file type: {path.suffix}")


def load_openapi_document(path: str | Path) -> dict[str, Any]:
    document = _load_document(Path(path))
    if not isinstance(document, dict):
        raise ValueError("OpenAPI document must be an object.")
    if "openapi" not in document:
        raise ValueError("Input document is missing the top-level 'openapi' field.")
    version = str(document["openapi"])
    if not (version.startswith("3.0.") or version.startswith("3.1.")):
        raise ValueError(
            f"Unsupported OpenAPI version '{version}'. Only 3.0.x and 3.1.x are supported."
        )
    if "x-openmodels" not in document:
        raise ValueError("Input document is missing the top-level 'x-openmodels' field.")

    extension_schema = load_json(ROOT / "schemas" / "x-openmodels.schema.json")
    jsonschema.Draft202012Validator.check_schema(extension_schema)
    jsonschema.validate(document["x-openmodels"], extension_schema)
    return document
