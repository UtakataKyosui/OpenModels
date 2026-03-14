from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .common import snake_case


@dataclass(frozen=True)
class NormalizationError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


def _decode_pointer_token(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def resolve_json_pointer(document: dict[str, Any], pointer: str) -> Any:
    if pointer == "#":
        return document
    if not pointer.startswith("#/"):
        raise NormalizationError(f"Unsupported JSON pointer: {pointer}")

    current: Any = document
    for raw_token in pointer[2:].split("/"):
        token = _decode_pointer_token(raw_token)
        if isinstance(current, list):
            try:
                current = current[int(token)]
            except (ValueError, IndexError) as exc:
                raise NormalizationError(f"Invalid list pointer segment '{token}' in {pointer}") from exc
            continue

        if not isinstance(current, dict) or token not in current:
            raise NormalizationError(f"Pointer not found: {pointer}")
        current = current[token]

    return current


def resolve_schema_node(document: dict[str, Any], pointer: str) -> Any:
    node = resolve_json_pointer(document, pointer)
    visited: set[str] = set()
    while isinstance(node, dict) and "$ref" in node:
        ref = node["$ref"]
        if ref in visited:
            raise NormalizationError(f"Cyclic $ref detected at {ref}")
        visited.add(ref)
        node = resolve_json_pointer(document, ref)
    _ensure_supported_schema_node(node, pointer)
    return node


def _ensure_supported_schema_node(node: Any, pointer: str) -> None:
    if not isinstance(node, dict):
        return
    for keyword in ("oneOf", "anyOf", "allOf", "discriminator"):
        if keyword in node:
            raise NormalizationError(
                f"Unsupported OpenAPI construct '{keyword}' at {pointer}."
            )


def _property_context(pointer: str) -> tuple[str | None, str | None]:
    marker = "/properties/"
    if marker not in pointer:
        return None, None
    parent_pointer, property_name = pointer.rsplit(marker, 1)
    return property_name, parent_pointer


def _property_is_required(document: dict[str, Any], pointer: str) -> bool | None:
    property_name, parent_pointer = _property_context(pointer)
    if not property_name or not parent_pointer:
        return None
    parent_schema = resolve_schema_node(document, parent_pointer)
    required = parent_schema.get("required", [])
    return property_name in required


def _schema_allows_null(document: dict[str, Any], pointer: str) -> bool:
    node = resolve_schema_node(document, pointer)
    if node.get("nullable") is True:
        return True
    node_type = node.get("type")
    if isinstance(node_type, list):
        return "null" in node_type
    return node_type == "null"


def _infer_nullable(document: dict[str, Any], field: dict[str, Any]) -> bool:
    column = field.get("column", {})
    if "nullable" in column:
        return bool(column["nullable"])
    if column.get("primaryKey"):
        return False
    if column.get("generated") in {"database", "application"}:
        return False

    required_values: list[bool] = []
    for pointer in field.get("schema", {}).values():
        if _schema_allows_null(document, pointer):
            return True
        required_value = _property_is_required(document, pointer)
        if required_value is not None:
            required_values.append(required_value)

    if required_values and all(required_values):
        return False

    return False


def _copy_adapters(definition: dict[str, Any]) -> dict[str, Any] | None:
    adapters = definition.get("adapters")
    if adapters is None:
        return None
    return deepcopy(adapters)


def _normalize_enum(
    name: str, enum_definition: dict[str, Any], document: dict[str, Any]
) -> dict[str, Any]:
    for pointer in enum_definition.get("schema", {}).values():
        resolve_schema_node(document, pointer)

    normalized_enum = {
        "name": name,
        "description": enum_definition.get("description"),
        "sourceSchemas": enum_definition.get("schema", {}),
        "values": enum_definition["values"],
    }
    adapters = _copy_adapters(enum_definition)
    if adapters:
        normalized_enum["adapters"] = adapters
    return normalized_enum


def _normalize_field(
    field_name: str, field_definition: dict[str, Any], document: dict[str, Any]
) -> dict[str, Any]:
    column = field_definition.get("column", {})
    computed = field_definition.get("computed")
    persisted = not field_definition.get("virtual", False)
    if computed and not computed.get("stored", False):
        persisted = False

    for pointer in field_definition.get("schema", {}).values():
        resolve_schema_node(document, pointer)

    normalized_field = {
        "name": field_name,
        "storageName": snake_case(field_name),
        "type": column.get("type", "unknown"),
        "nullable": _infer_nullable(document, field_definition),
        "persisted": persisted,
        "generated": column.get("generated", "none"),
        "sourceSchemas": field_definition.get("schema", {}),
    }

    if "enum" in field_definition:
        normalized_field["enum"] = field_definition["enum"]
    if "default" in column:
        normalized_field["default"] = column["default"]
    if computed:
        normalized_field["computed"] = computed
    if "length" in column:
        normalized_field["length"] = column["length"]
    if "precision" in column:
        normalized_field["precision"] = column["precision"]
    if "scale" in column:
        normalized_field["scale"] = column["scale"]
    if "primaryKey" in column:
        normalized_field["primaryKey"] = bool(column["primaryKey"])
    if "unique" in column:
        normalized_field["unique"] = bool(column["unique"])
    adapters = _copy_adapters(field_definition)
    if adapters:
        normalized_field["adapters"] = adapters

    return normalized_field


def _entity_primary_key_fields(entity_definition: dict[str, Any]) -> list[str]:
    fields = [
        field_name
        for field_name, field in entity_definition.get("fields", {}).items()
        if field.get("column", {}).get("primaryKey")
    ]
    for constraint in entity_definition.get("constraints", []):
        if constraint.get("kind") == "primaryKey":
            fields.extend(constraint.get("fields", []))
    return fields


def _normalize_relation(
    entity_name: str,
    relation_name: str,
    relation_definition: dict[str, Any],
    entities: dict[str, Any],
) -> dict[str, Any]:
    target_entity = relation_definition["target"]
    if target_entity not in entities:
        raise NormalizationError(
            f"Relation '{entity_name}.{relation_name}' references unknown entity '{target_entity}'."
        )

    kind = relation_definition["kind"]
    ownership = "owner" if kind == "belongsTo" else "inverse"
    current_primary_keys = _entity_primary_key_fields(entities[entity_name])
    target_primary_keys = _entity_primary_key_fields(entities[target_entity])

    if ownership == "owner":
        reference_field = relation_definition.get("references") or (
            target_primary_keys[0] if target_primary_keys else None
        )
    else:
        reference_field = relation_definition.get("references") or (
            current_primary_keys[0] if current_primary_keys else None
        )

    normalized_relation = {
        "name": relation_name,
        "kind": kind,
        "targetEntity": target_entity,
        "ownership": ownership,
    }

    if "foreignKey" in relation_definition:
        normalized_relation["foreignKey"] = relation_definition["foreignKey"]
    if reference_field:
        normalized_relation["references"] = reference_field
    if "through" in relation_definition:
        normalized_relation["throughEntity"] = relation_definition["through"]
    adapters = _copy_adapters(relation_definition)
    if adapters:
        normalized_relation["adapters"] = adapters

    return normalized_relation


def _normalize_constraint(
    entity_name: str,
    constraint_definition: dict[str, Any],
    entities: dict[str, Any],
    field_names: set[str],
) -> dict[str, Any]:
    normalized_constraint: dict[str, Any] = {"kind": constraint_definition["kind"]}
    if "name" in constraint_definition:
        normalized_constraint["name"] = constraint_definition["name"]

    for field_name in constraint_definition.get("fields", []):
        if field_name not in field_names:
            raise NormalizationError(
                f"Constraint on entity '{entity_name}' references unknown field '{field_name}'."
            )
    if "fields" in constraint_definition:
        normalized_constraint["fields"] = constraint_definition["fields"]

    if constraint_definition["kind"] == "foreignKey":
        references = constraint_definition.get("references")
        if not references:
            raise NormalizationError(
                f"Foreign key constraint on '{entity_name}' must define references."
            )
        target_entity = references["entity"]
        if target_entity not in entities:
            raise NormalizationError(
                f"Foreign key constraint on '{entity_name}' references unknown entity '{target_entity}'."
            )
        target_fields = {
            name for name in entities[target_entity].get("fields", {}).keys()
        }
        for target_field in references.get("fields", []):
            if target_field not in target_fields:
                raise NormalizationError(
                    f"Foreign key constraint on '{entity_name}' references unknown field "
                    f"'{target_entity}.{target_field}'."
                )
        normalized_constraint["references"] = references

    if "expression" in constraint_definition:
        normalized_constraint["expression"] = constraint_definition["expression"]
    adapters = _copy_adapters(constraint_definition)
    if adapters:
        normalized_constraint["adapters"] = adapters

    return normalized_constraint


def _normalize_index(index_definition: dict[str, Any], field_names: set[str]) -> dict[str, Any]:
    for field_name in index_definition.get("fields", []):
        if field_name not in field_names:
            raise NormalizationError(f"Index references unknown field '{field_name}'.")

    normalized_index = {
        "fields": index_definition["fields"],
        "unique": bool(index_definition.get("unique", False)),
    }
    if "name" in index_definition:
        normalized_index["name"] = index_definition["name"]
    adapters = _copy_adapters(index_definition)
    if adapters:
        normalized_index["adapters"] = adapters
    return normalized_index


def normalize_openapi_document(document: dict[str, Any]) -> dict[str, Any]:
    extension = document["x-openmodels"]
    entities = extension["entities"]
    enum_names = set(extension.get("enums", {}).keys())

    normalized = {
        "version": extension["version"],
        "enums": [
            _normalize_enum(name, enum_definition, document)
            for name, enum_definition in extension.get("enums", {}).items()
        ],
        "entities": [],
    }
    adapters = _copy_adapters(extension)
    if adapters:
        normalized["adapters"] = adapters
    if "outputs" in extension:
        normalized["outputs"] = deepcopy(extension["outputs"])

    for entity_name, entity_definition in entities.items():
        field_names = set(entity_definition.get("fields", {}).keys())
        normalized_fields = []
        for field_name, field_definition in entity_definition.get("fields", {}).items():
            if "enum" in field_definition and field_definition["enum"] not in enum_names:
                raise NormalizationError(
                    f"Field '{entity_name}.{field_name}' references unknown enum "
                    f"'{field_definition['enum']}'."
                )
            normalized_fields.append(_normalize_field(field_name, field_definition, document))

        normalized_entity = {
            "name": entity_name,
            "table": entity_definition["table"],
            "sourceSchemas": entity_definition.get("sourceSchemas", {}),
            "fields": normalized_fields,
            "relations": [
                _normalize_relation(entity_name, relation_name, relation_definition, entities)
                for relation_name, relation_definition in entity_definition.get(
                    "relations", {}
                ).items()
            ],
            "indexes": [
                _normalize_index(index_definition, field_names)
                for index_definition in entity_definition.get("indexes", [])
            ],
            "constraints": [
                _normalize_constraint(entity_name, constraint_definition, entities, field_names)
                for constraint_definition in entity_definition.get("constraints", [])
            ],
        }
        adapters = _copy_adapters(entity_definition)
        if adapters:
            normalized_entity["adapters"] = adapters
        normalized["entities"].append(normalized_entity)

    return normalized
