from __future__ import annotations

from typing import Any

from .adapter import GeneratedFile
from .registry import get_adapter


DEFAULT_OUTPUT = {
    "target": "drizzle-pg",
    "filename": "schema.ts",
}


def generate_artifacts(
    canonical_model: dict[str, Any],
    target: str | None = None,
    filename: str | None = None,
) -> list[GeneratedFile]:
    if target is not None:
        adapter = get_adapter(target)
        return adapter.generate_files(canonical_model, filename=filename)

    outputs = canonical_model.get("outputs")
    if not outputs:
        outputs = [DEFAULT_OUTPUT]

    if filename is not None and len(outputs) != 1:
        raise ValueError(
            "A filename override can only be used when a single output target is selected."
        )

    generated_files: list[GeneratedFile] = []
    for output in outputs:
        adapter = get_adapter(output["target"])
        generated_files.extend(
            adapter.generate_files(
                canonical_model,
                filename=filename or output.get("filename"),
                options=output.get("options"),
            )
        )

    return generated_files
