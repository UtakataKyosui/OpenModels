from __future__ import annotations

from typing import Any

from .adapter import AdapterError, BackendAdapter, GeneratedFile
from .common import snake_case, upper_camel_case


SEAORM_RUST_TARGET = "seaorm-rust"


def _seaorm_type_hint(field: dict[str, Any]) -> str:
    if "enum" in field:
        return upper_camel_case(field["enum"])

    field_type = field["type"]
    if field_type == "uuid":
        return "Uuid"
    if field_type in {"varchar", "text"}:
        return "String"
    if field_type == "integer":
        return "i32"
    if field_type == "boolean":
        return "bool"
    if field_type == "timestamp":
        return "DateTime"
    if field_type == "timestamptz":
        return "DateTimeWithTimeZone"
    return "Unsupported"


def _seaorm_entity_config(entity: dict[str, Any]) -> dict[str, Any]:
    return entity.get("adapters", {}).get(SEAORM_RUST_TARGET, {})


def _seaorm_field_config(field: dict[str, Any]) -> dict[str, Any]:
    return field.get("adapters", {}).get(SEAORM_RUST_TARGET, {})


def _module_name(entity: dict[str, Any]) -> str:
    adapter_config = _seaorm_entity_config(entity)
    return adapter_config.get("moduleName", snake_case(entity["name"]))


def _entity_contract_file(entity: dict[str, Any], module_root: str) -> GeneratedFile:
    module_name = _module_name(entity)
    lines = [
        f"//! SeaORM Phase 1 contract placeholder for `{entity['name']}`.",
        "//!",
        "//! Planned generated items in Phase 2:",
        "//! - `Entity`",
        "//! - `Model`",
        "//! - `ActiveModel`",
        "//! - `Column`",
        "//! - `PrimaryKey`",
        "//!",
        f"//! Planned module path: `{module_root}/{module_name}.rs`",
        f"//! Planned table name: `{entity['table']}`",
        "//!",
        "//! Canonical field-to-Rust type preview:",
    ]

    for field in entity.get("fields", []):
        field_config = _seaorm_field_config(field)
        rust_type = field_config.get("rustType", _seaorm_type_hint(field))
        lines.append(
            f"//! - `{field['name']}` -> `{rust_type}`"
        )

    lines.extend(
        [
            "//!",
            "//! Unsupported in Phase 1:",
            "//! - compiled SeaORM entity definitions",
            "//! - relation traits",
            "//! - indexes and constraints",
            "//! - generated/computed column behavior",
            "//! - composite key emission",
        ]
    )
    return GeneratedFile(path=f"{module_root}/{module_name}.rs", content="\n".join(lines) + "\n")


def _mod_file(entities: list[dict[str, Any]], module_root: str) -> GeneratedFile:
    lines = [
        "//! SeaORM Phase 1 output layout contract.",
        "//!",
        "//! This file fixes the planned module topology before the full generator",
        "//! arrives in SeaORM Phase 2.",
        "",
        "pub mod prelude;",
    ]
    for entity in sorted(entities, key=lambda item: _module_name(item)):
        lines.append(f"pub mod {_module_name(entity)};")
    return GeneratedFile(path=f"{module_root}/mod.rs", content="\n".join(lines) + "\n")


def _prelude_file(entities: list[dict[str, Any]], module_root: str) -> GeneratedFile:
    lines = [
        "//! SeaORM Phase 1 prelude contract placeholder.",
        "//!",
        "//! Planned public exports after Entity generation:",
    ]
    for entity in sorted(entities, key=lambda item: item["name"]):
        lines.append(
            f"//! - `{upper_camel_case(entity['name'])}` from `super::{_module_name(entity)}`"
        )
    return GeneratedFile(path=f"{module_root}/prelude.rs", content="\n".join(lines) + "\n")


class SeaOrmRustContractAdapter(BackendAdapter):
    key = SEAORM_RUST_TARGET
    description = "SeaORM Rust output contract placeholder"
    default_filename = "entity/mod.rs"

    def generate_files(
        self,
        canonical_model: dict[str, Any],
        filename: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> list[GeneratedFile]:
        if filename is not None:
            raise AdapterError(
                "The seaorm-rust adapter uses a fixed multi-file layout and does not accept filename overrides."
            )

        options = options or {}
        module_root = options.get("moduleRoot", "entity")
        if not isinstance(module_root, str) or not module_root:
            raise AdapterError("The seaorm-rust adapter requires a non-empty string for options.moduleRoot.")

        entities = canonical_model.get("entities", [])
        files = [
            _mod_file(entities, module_root),
            _prelude_file(entities, module_root),
        ]
        files.extend(
            _entity_contract_file(entity, module_root)
            for entity in sorted(entities, key=lambda item: _module_name(item))
        )
        return files


SEAORM_RUST_ADAPTER = SeaOrmRustContractAdapter()
