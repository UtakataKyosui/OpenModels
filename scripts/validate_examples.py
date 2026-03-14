#!/usr/bin/env python3

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from openmodels.registry import list_adapters


KNOWN_ADAPTER_TARGETS = {adapter.key for adapter in list_adapters()}


def load_json(path: Path):
    return json.loads(path.read_text())


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text())


@dataclass(frozen=True)
class Diagnostic:
    code: str
    path: str
    message: str


def _field_names_by_entity(entities: dict[str, Any]) -> dict[str, set[str]]:
    names: dict[str, set[str]] = {}
    for entity_name, entity in entities.items():
        names[entity_name] = set(entity.get("fields", {}).keys())
    return names


def _x_openmodels_foreign_key_owner(
    entity_name: str, relation: dict[str, Any]
) -> tuple[str | None, str | None]:
    kind = relation.get("kind")
    target = relation.get("target")

    if kind == "belongsTo":
        return entity_name, target
    if kind in {"hasOne", "hasMany"}:
        return target, entity_name
    return None, target


def validate_x_openmodels_semantics(extension: dict[str, Any]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    entities = extension.get("entities", {})
    enum_names = set(extension.get("enums", {}).keys())
    entity_names = set(entities.keys())
    field_names = _field_names_by_entity(entities)

    for output_index, output in enumerate(extension.get("outputs", [])):
        target = output.get("target")
        if target not in KNOWN_ADAPTER_TARGETS:
            diagnostics.append(
                Diagnostic(
                    code="unknown-output-target",
                    path=f"outputs[{output_index}].target",
                    message=f"Unknown output target '{target}'.",
                )
            )

    for entity_name, entity in entities.items():
        for field_name, field in entity.get("fields", {}).items():
            enum_name = field.get("enum")
            if enum_name and enum_name not in enum_names:
                diagnostics.append(
                    Diagnostic(
                        code="unknown-enum",
                        path=f"entities.{entity_name}.fields.{field_name}.enum",
                        message=f"Unknown enum '{enum_name}'.",
                    )
                )

        for relation_name, relation in entity.get("relations", {}).items():
            target = relation.get("target")
            if target not in entity_names:
                diagnostics.append(
                    Diagnostic(
                        code="unknown-relation-target",
                        path=f"entities.{entity_name}.relations.{relation_name}.target",
                        message=f"Unknown relation target '{target}'.",
                    )
                )
                continue

            foreign_key = relation.get("foreignKey")
            owner_entity, referenced_entity = _x_openmodels_foreign_key_owner(
                entity_name, relation
            )
            if foreign_key and owner_entity and foreign_key not in field_names[owner_entity]:
                diagnostics.append(
                    Diagnostic(
                        code="unknown-foreign-key-field",
                        path=f"entities.{entity_name}.relations.{relation_name}.foreignKey",
                        message=(
                            f"Unknown foreign key field '{foreign_key}' on entity "
                            f"'{owner_entity}'."
                        ),
                    )
                )

            references = relation.get("references")
            if (
                references
                and referenced_entity
                and references not in field_names[referenced_entity]
            ):
                diagnostics.append(
                    Diagnostic(
                        code="unknown-reference-field",
                        path=f"entities.{entity_name}.relations.{relation_name}.references",
                        message=(
                            f"Unknown referenced field '{references}' on entity "
                            f"'{referenced_entity}'."
                        ),
                    )
                )

        for index_index, index in enumerate(entity.get("indexes", [])):
            for field_name in index.get("fields", []):
                if field_name not in field_names[entity_name]:
                    diagnostics.append(
                        Diagnostic(
                            code="unknown-index-field",
                            path=f"entities.{entity_name}.indexes[{index_index}]",
                            message=f"Unknown index field '{field_name}'.",
                        )
                    )

        for constraint_index, constraint in enumerate(entity.get("constraints", [])):
            for field_name in constraint.get("fields", []):
                if field_name not in field_names[entity_name]:
                    diagnostics.append(
                        Diagnostic(
                            code="unknown-constraint-field",
                            path=f"entities.{entity_name}.constraints[{constraint_index}]",
                            message=f"Unknown constraint field '{field_name}'.",
                        )
                    )

            if constraint.get("kind") == "foreignKey":
                references = constraint.get("references")
                if not references:
                    diagnostics.append(
                        Diagnostic(
                            code="missing-foreign-key-reference",
                            path=f"entities.{entity_name}.constraints[{constraint_index}]",
                            message="Foreign key constraint must define references.",
                        )
                    )
                    continue

                target = references.get("entity")
                if target not in entity_names:
                    diagnostics.append(
                        Diagnostic(
                            code="unknown-constraint-target",
                            path=f"entities.{entity_name}.constraints[{constraint_index}].references.entity",
                            message=f"Unknown foreign key target '{target}'.",
                        )
                    )
                    continue

                for target_field in references.get("fields", []):
                    if target_field not in field_names[target]:
                        diagnostics.append(
                            Diagnostic(
                                code="unknown-constraint-reference-field",
                                path=f"entities.{entity_name}.constraints[{constraint_index}].references.fields",
                                message=f"Unknown referenced field '{target_field}' on entity '{target}'.",
                            )
                        )

    return diagnostics


def _field_names_by_canonical_entity(entities: list[dict[str, Any]]) -> dict[str, set[str]]:
    names: dict[str, set[str]] = {}
    for entity in entities:
        names[entity["name"]] = {field["name"] for field in entity.get("fields", [])}
    return names


def _canonical_relation_owner(
    entity_name: str, relation: dict[str, Any]
) -> tuple[str | None, str | None]:
    ownership = relation.get("ownership")
    target = relation.get("targetEntity")

    if ownership == "owner":
        return entity_name, target
    if ownership == "inverse":
        return target, entity_name
    return None, target


def validate_canonical_model_semantics(model: dict[str, Any]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    entities = model.get("entities", [])
    entity_names = {entity["name"] for entity in entities}
    field_names = _field_names_by_canonical_entity(entities)
    enum_names = {enum["name"] for enum in model.get("enums", [])}

    for output_index, output in enumerate(model.get("outputs", [])):
        target = output.get("target")
        if target not in KNOWN_ADAPTER_TARGETS:
            diagnostics.append(
                Diagnostic(
                    code="unknown-output-target",
                    path=f"outputs[{output_index}].target",
                    message=f"Unknown output target '{target}'.",
                )
            )

    for entity in entities:
        entity_name = entity["name"]
        for field in entity.get("fields", []):
            enum_name = field.get("enum")
            if enum_name and enum_name not in enum_names:
                diagnostics.append(
                    Diagnostic(
                        code="unknown-enum",
                        path=f"entities.{entity_name}.fields.{field['name']}.enum",
                        message=f"Unknown enum '{enum_name}'.",
                    )
                )

        for relation in entity.get("relations", []):
            relation_name = relation["name"]
            target = relation["targetEntity"]
            if target not in entity_names:
                diagnostics.append(
                    Diagnostic(
                        code="unknown-relation-target",
                        path=f"entities.{entity_name}.relations.{relation_name}.targetEntity",
                        message=f"Unknown relation target '{target}'.",
                    )
                )
                continue

            foreign_key = relation.get("foreignKey")
            owner_entity, referenced_entity = _canonical_relation_owner(
                entity_name, relation
            )
            if foreign_key and owner_entity and foreign_key not in field_names[owner_entity]:
                diagnostics.append(
                    Diagnostic(
                        code="unknown-foreign-key-field",
                        path=f"entities.{entity_name}.relations.{relation_name}.foreignKey",
                        message=(
                            f"Unknown foreign key field '{foreign_key}' on entity "
                            f"'{owner_entity}'."
                        ),
                    )
                )

            references = relation.get("references")
            if (
                references
                and referenced_entity
                and references not in field_names[referenced_entity]
            ):
                diagnostics.append(
                    Diagnostic(
                        code="unknown-reference-field",
                        path=f"entities.{entity_name}.relations.{relation_name}.references",
                        message=(
                            f"Unknown referenced field '{references}' on entity "
                            f"'{referenced_entity}'."
                        ),
                    )
                )

        for index in entity.get("indexes", []):
            for field_name in index.get("fields", []):
                if field_name not in field_names[entity_name]:
                    diagnostics.append(
                        Diagnostic(
                            code="unknown-index-field",
                            path=f"entities.{entity_name}.indexes.{index.get('name', '<unnamed>')}",
                            message=f"Unknown index field '{field_name}'.",
                        )
                    )

        for constraint in entity.get("constraints", []):
            constraint_name = constraint.get("name", "<unnamed>")
            for field_name in constraint.get("fields", []):
                if field_name not in field_names[entity_name]:
                    diagnostics.append(
                        Diagnostic(
                            code="unknown-constraint-field",
                            path=f"entities.{entity_name}.constraints.{constraint_name}",
                            message=f"Unknown constraint field '{field_name}'.",
                        )
                    )

            if constraint.get("kind") == "foreignKey":
                references = constraint.get("references")
                if not references:
                    diagnostics.append(
                        Diagnostic(
                            code="missing-foreign-key-reference",
                            path=f"entities.{entity_name}.constraints.{constraint_name}",
                            message="Foreign key constraint must define references.",
                        )
                    )
                    continue

                target = references.get("entity")
                if target not in entity_names:
                    diagnostics.append(
                        Diagnostic(
                            code="unknown-constraint-target",
                            path=f"entities.{entity_name}.constraints.{constraint_name}.references.entity",
                            message=f"Unknown foreign key target '{target}'.",
                        )
                    )
                    continue

                for target_field in references.get("fields", []):
                    if target_field not in field_names[target]:
                        diagnostics.append(
                            Diagnostic(
                                code="unknown-constraint-reference-field",
                                path=f"entities.{entity_name}.constraints.{constraint_name}.references.fields",
                                message=f"Unknown referenced field '{target_field}' on entity '{target}'.",
                            )
                        )

    return diagnostics


def validate_examples() -> list[Diagnostic]:
    x_openmodels_schema = load_json(ROOT / "schemas" / "x-openmodels.schema.json")
    canonical_schema = load_json(ROOT / "schemas" / "canonical-model.schema.json")
    openapi_document = load_yaml(ROOT / "examples" / "openapi" / "blog-api.yaml")
    canonical_document = load_json(ROOT / "examples" / "canonical" / "blog-model.json")

    jsonschema.Draft202012Validator.check_schema(x_openmodels_schema)
    jsonschema.Draft202012Validator.check_schema(canonical_schema)

    jsonschema.validate(openapi_document["x-openmodels"], x_openmodels_schema)
    jsonschema.validate(canonical_document, canonical_schema)

    diagnostics: list[Diagnostic] = []
    diagnostics.extend(validate_x_openmodels_semantics(openapi_document["x-openmodels"]))
    diagnostics.extend(validate_canonical_model_semantics(canonical_document))
    return diagnostics


def main() -> None:
    diagnostics = validate_examples()
    if diagnostics:
        for diagnostic in diagnostics:
            print(f"{diagnostic.code}: {diagnostic.path}: {diagnostic.message}")
        raise SystemExit(1)

    print("Validation passed for x-openmodels and canonical model examples.")


if __name__ == "__main__":
    main()
