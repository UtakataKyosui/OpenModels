from __future__ import annotations

import json
from typing import Any

from .adapter import GeneratedFile
from .common import to_json_literal
from .normalize import resolve_schema_node


def _schema_name_from_pointer(pointer: str | None) -> str | None:
    if not pointer or not pointer.startswith("#/components/schemas/"):
        return None
    return pointer.split("/", 4)[-1]


def _property_name_from_pointer(pointer: str | None) -> str | None:
    if not pointer or "/properties/" not in pointer:
        return None
    return pointer.rsplit("/properties/", 1)[-1]


def _storage_type_to_ts(field: dict[str, Any]) -> str:
    field_type = field["type"]
    if field_type in {"uuid", "varchar", "text"}:
        base = "string"
    elif field_type in {"integer"}:
        base = "number"
    elif field_type in {"boolean"}:
        base = "boolean"
    elif field_type in {"timestamp", "timestamptz"}:
        base = "Date"
    else:
        base = "unknown"
    if field.get("nullable"):
        return f"{base} | null"
    return base


def _ts_type_from_openapi_node(node: Any) -> str:
    if not isinstance(node, dict):
        return "unknown"
    if "$ref" in node:
        return _schema_name_from_pointer(node["$ref"]) or "unknown"
    if "enum" in node:
        return " | ".join(to_json_literal(value) for value in node["enum"])

    node_type = node.get("type")
    if isinstance(node_type, list):
        non_null_types = [item for item in node_type if item != "null"]
        if len(non_null_types) == 1:
            base = _ts_type_from_openapi_node({"type": non_null_types[0], **{
                key: value for key, value in node.items() if key != "type"
            }})
            return f"{base} | null"
        return "unknown"

    if node_type == "string":
        return "string"
    if node_type in {"integer", "number"}:
        return "number"
    if node_type == "boolean":
        return "boolean"
    if node_type == "array":
        item_type = _ts_type_from_openapi_node(node.get("items", {}))
        return f"Array<{item_type}>"
    if node_type == "object":
        return "Record<string, unknown>"
    return "unknown"


def _schema_properties(
    document: dict[str, Any],
    schema_pointer: str | None,
) -> tuple[list[dict[str, Any]], set[str]]:
    if not schema_pointer:
        return [], set()
    schema_node = resolve_schema_node(document, schema_pointer)
    properties = schema_node.get("properties", {})
    required = set(schema_node.get("required", []))
    items = []
    for property_name, property_node in properties.items():
        items.append(
            {
                "name": property_name,
                "type": _ts_type_from_openapi_node(
                    resolve_schema_node(document, property_node["$ref"])
                    if isinstance(property_node, dict) and "$ref" in property_node
                    else property_node
                ),
            }
        )
    return items, required


def _build_record_interface(entity: dict[str, Any]) -> str:
    lines = [f"export interface {entity['name']}Record {{"]
    for field in entity.get("fields", []):
        if not field.get("persisted", True):
            continue
        lines.append(f"  {field['name']}: {_storage_type_to_ts(field)};")
    lines.append("}")
    return "\n".join(lines)


def _build_dto_interface(
    document: dict[str, Any],
    schema_name: str,
) -> str:
    schema_pointer = f"#/components/schemas/{schema_name}"
    properties, required = _schema_properties(document, schema_pointer)
    lines = [f"export interface {schema_name} {{"]
    for property_item in properties:
        optional = "" if property_item["name"] in required else "?"
        lines.append(
            f"  {property_item['name']}{optional}: {property_item['type']};"
        )
    lines.append("}")
    return "\n".join(lines)


def _create_mapping_diagnostics(entity: dict[str, Any], document: dict[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    create_schema_pointer = entity.get("sourceSchemas", {}).get("create")
    create_schema_name = _schema_name_from_pointer(create_schema_pointer)
    if not create_schema_pointer or not create_schema_name:
        return diagnostics

    create_properties, _required = _schema_properties(document, create_schema_pointer)
    mapped_properties = {
        _property_name_from_pointer(field.get("sourceSchemas", {}).get("create"))
        for field in entity.get("fields", [])
        if field.get("sourceSchemas", {}).get("create")
    }
    mapped_properties.discard(None)

    for field in entity.get("fields", []):
        if field.get("sourceSchemas", {}).get("create"):
            continue
        if (
            field.get("persisted", True)
            and field.get("generated") == "none"
            and "default" not in field
            and not field.get("nullable", False)
        ):
            diagnostics.append(
                {
                    "code": "unmapped-entity-field",
                    "direction": "create",
                    "entity": entity["name"],
                    "schema": create_schema_name,
                    "field": field["name"],
                    "message": (
                        f"Field '{entity['name']}.{field['name']}' has no direct create "
                        "mapping and requires a transform or manual assignment."
                    ),
                }
            )

    for property_item in create_properties:
        if property_item["name"] in mapped_properties:
            continue
        diagnostics.append(
            {
                "code": "unmapped-dto-property",
                "direction": "create",
                "entity": entity["name"],
                "schema": create_schema_name,
                "property": property_item["name"],
                "message": (
                    f"Property '{create_schema_name}.{property_item['name']}' is not mapped "
                    "to any persistence field."
                ),
            }
        )

    return diagnostics


def _read_mapping_diagnostics(entity: dict[str, Any], document: dict[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    read_schema_pointer = entity.get("sourceSchemas", {}).get("read")
    read_schema_name = _schema_name_from_pointer(read_schema_pointer)
    if not read_schema_pointer or not read_schema_name:
        return diagnostics

    read_properties, _required = _schema_properties(document, read_schema_pointer)
    mapped_properties = {
        _property_name_from_pointer(field.get("sourceSchemas", {}).get("read"))
        for field in entity.get("fields", [])
        if field.get("sourceSchemas", {}).get("read")
    }
    mapped_properties.discard(None)

    for property_item in read_properties:
        if property_item["name"] in mapped_properties:
            continue
        diagnostics.append(
            {
                "code": "unmapped-dto-property",
                "direction": "read",
                "entity": entity["name"],
                "schema": read_schema_name,
                "property": property_item["name"],
                "message": (
                    f"Property '{read_schema_name}.{property_item['name']}' is not mapped "
                    "from any persistence field."
                ),
            }
        )

    return diagnostics


def _mapping_function_name(entity_name: str, direction: str) -> str:
    if direction == "create":
        return f"map{entity_name}CreateInputTo{entity_name}Record"
    if direction == "update":
        return f"map{entity_name}UpdateInputTo{entity_name}RecordPatch"
    if direction == "read":
        return f"map{entity_name}RecordTo{entity_name}Response"
    raise ValueError(f"Unsupported mapping direction: {direction}")


def _build_create_mapper(entity: dict[str, Any], document: dict[str, Any]) -> str | None:
    schema_pointer = entity.get("sourceSchemas", {}).get("create")
    schema_name = _schema_name_from_pointer(schema_pointer)
    if not schema_name:
        return None

    assignments: list[str] = []
    for field in entity.get("fields", []):
        property_pointer = field.get("sourceSchemas", {}).get("create")
        property_name = _property_name_from_pointer(property_pointer)
        if property_name:
            expression = f"input.{property_name}"
            if field["type"] in {"timestamp", "timestamptz"}:
                property_node = resolve_schema_node(document, property_pointer)
                if property_node.get("type") == "string":
                    expression = f"new Date(input.{property_name})"
            assignments.append(f"    {field['name']}: {expression},")

    todo_comments = [
        diagnostic["message"]
        for diagnostic in _create_mapping_diagnostics(entity, document)
        if diagnostic["code"] == "unmapped-entity-field"
    ]

    lines = [
        f"export function {_mapping_function_name(entity['name'], 'create')}(input: {schema_name}): Partial<{entity['name']}Record> {{",
    ]
    for comment in todo_comments:
        lines.append(f"  // TODO(openmodels): {comment}")
    lines.append("  return {")
    lines.extend(assignments)
    lines.append("  };")
    lines.append("}")
    return "\n".join(lines)


def _build_update_mapper(entity: dict[str, Any]) -> str | None:
    schema_pointer = entity.get("sourceSchemas", {}).get("update")
    schema_name = _schema_name_from_pointer(schema_pointer)
    if not schema_name:
        return None

    assignments: list[str] = []
    for field in entity.get("fields", []):
        property_name = _property_name_from_pointer(field.get("sourceSchemas", {}).get("update"))
        if property_name:
            assignments.append(
                f"    ...(input.{property_name} !== undefined ? {{ {field['name']}: input.{property_name} }} : {{}}),"
            )

    lines = [
        f"export function {_mapping_function_name(entity['name'], 'update')}(input: {schema_name}): Partial<{entity['name']}Record> {{",
        "  return {",
    ]
    lines.extend(assignments)
    lines.append("  };")
    lines.append("}")
    return "\n".join(lines)


def _build_read_mapper(entity: dict[str, Any], document: dict[str, Any]) -> str | None:
    schema_pointer = entity.get("sourceSchemas", {}).get("read")
    schema_name = _schema_name_from_pointer(schema_pointer)
    if not schema_name:
        return None

    assignments: list[str] = []
    for field in entity.get("fields", []):
        property_pointer = field.get("sourceSchemas", {}).get("read")
        property_name = _property_name_from_pointer(property_pointer)
        if property_name:
            expression = f"record.{field['name']}"
            if field["type"] in {"timestamp", "timestamptz"}:
                property_node = resolve_schema_node(document, property_pointer)
                if property_node.get("type") == "string":
                    if field.get("nullable"):
                        expression = (
                            f"record.{field['name']} ? record.{field['name']}.toISOString() : null"
                        )
                    else:
                        expression = f"record.{field['name']}.toISOString()"
            assignments.append(f"    {property_name}: {expression},")

    lines = [
        f"export function {_mapping_function_name(entity['name'], 'read')}(record: {entity['name']}Record): Partial<{schema_name}> {{",
        "  return {",
    ]
    lines.extend(assignments)
    lines.append("  };")
    lines.append("}")
    return "\n".join(lines)


def build_mapper_report(
    document: dict[str, Any],
    canonical_model: dict[str, Any],
) -> dict[str, Any]:
    diagnostics: list[dict[str, Any]] = []
    for entity in canonical_model.get("entities", []):
        diagnostics.extend(_create_mapping_diagnostics(entity, document))
        diagnostics.extend(_read_mapping_diagnostics(entity, document))

    return {
        "formatVersion": "0.1",
        "diagnostics": diagnostics,
        "summary": {
            "totalDiagnostics": len(diagnostics),
            "entities": len(canonical_model.get("entities", [])),
        },
    }


def generate_mapper_files(
    document: dict[str, Any],
    canonical_model: dict[str, Any],
    filename: str = "dto-mappers.ts",
    diagnostics_filename: str = "dto-mappers.diagnostics.json",
) -> list[GeneratedFile]:
    dto_schema_names = {
        schema_name
        for entity in canonical_model.get("entities", [])
        for schema_name in (
            _schema_name_from_pointer(entity.get("sourceSchemas", {}).get("create")),
            _schema_name_from_pointer(entity.get("sourceSchemas", {}).get("read")),
            _schema_name_from_pointer(entity.get("sourceSchemas", {}).get("update")),
        )
        if schema_name
    }

    sections = [
        "// Generated by OpenModels. DTO interfaces are inferred from OpenAPI schemas.",
    ]

    record_interfaces = [
        _build_record_interface(entity) for entity in canonical_model.get("entities", [])
    ]
    sections.append("\n\n".join(record_interfaces))

    dto_interfaces = [
        _build_dto_interface(document, schema_name)
        for schema_name in sorted(dto_schema_names)
    ]
    if dto_interfaces:
        sections.append("\n\n".join(dto_interfaces))

    mapper_blocks: list[str] = []
    for entity in canonical_model.get("entities", []):
        for block in (
            _build_create_mapper(entity, document),
            _build_update_mapper(entity),
            _build_read_mapper(entity, document),
        ):
            if block:
                mapper_blocks.append(block)
    if mapper_blocks:
        sections.append("\n\n".join(mapper_blocks))

    mapper_report = build_mapper_report(document, canonical_model)

    return [
        GeneratedFile(path=filename, content="\n\n".join(sections) + "\n"),
        GeneratedFile(
            path=diagnostics_filename,
            content=json.dumps(mapper_report, indent=2, ensure_ascii=False) + "\n",
        ),
    ]
