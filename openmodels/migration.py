from __future__ import annotations

from copy import deepcopy
from typing import Any


def _entity_map(model: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {entity["name"]: entity for entity in model.get("entities", [])}


def _field_map(entity: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {field["name"]: field for field in entity.get("fields", [])}


def _index_key(index: dict[str, Any]) -> str:
    if index.get("name"):
        return f"name:{index['name']}"
    unique = "unique" if index.get("unique") else "plain"
    fields = ",".join(index.get("fields", []))
    return f"anon:{unique}:{fields}"


def _constraint_key(constraint: dict[str, Any]) -> str:
    if constraint.get("name"):
        return f"name:{constraint['name']}"
    kind = constraint["kind"]
    fields = ",".join(constraint.get("fields", []))
    expression = constraint.get("expression", "")
    references = constraint.get("references", {})
    target = references.get("entity", "")
    target_fields = ",".join(references.get("fields", []))
    return f"anon:{kind}:{fields}:{target}:{target_fields}:{expression}"


def _index_map(entity: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {_index_key(index): index for index in entity.get("indexes", [])}


def _constraint_map(entity: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _constraint_key(constraint): constraint
        for constraint in entity.get("constraints", [])
    }


def _field_signature(field: dict[str, Any]) -> dict[str, Any]:
    signature: dict[str, Any] = {
        "storageName": field.get("storageName", field["name"]),
        "type": field["type"],
        "nullable": field["nullable"],
        "persisted": field["persisted"],
        "generated": field["generated"],
    }
    for key in (
        "enum",
        "default",
        "length",
        "precision",
        "scale",
        "primaryKey",
        "unique",
    ):
        if key in field:
            signature[key] = deepcopy(field[key])
    return signature


def _index_signature(index: dict[str, Any]) -> dict[str, Any]:
    signature = {
        "fields": deepcopy(index["fields"]),
        "unique": bool(index.get("unique", False)),
    }
    if "name" in index:
        signature["name"] = index["name"]
    return signature


def _constraint_signature(constraint: dict[str, Any]) -> dict[str, Any]:
    signature = {"kind": constraint["kind"]}
    for key in ("name", "fields", "references", "expression"):
        if key in constraint:
            signature[key] = deepcopy(constraint[key])
    return signature


def _column_requires_backfill(field: dict[str, Any]) -> bool:
    return (
        field.get("persisted", True)
        and field.get("generated") == "none"
        and "default" not in field
        and not field.get("nullable", False)
    )


def _warning(
    code: str,
    message: str,
    *,
    entity: str,
    field: str | None = None,
    change_kind: str,
) -> dict[str, Any]:
    warning = {
        "code": code,
        "level": "warning",
        "entity": entity,
        "changeKind": change_kind,
        "message": message,
    }
    if field is not None:
        warning["field"] = field
    return warning


def _compare_signatures(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    changes: dict[str, dict[str, Any]] = {}
    keys = sorted(set(before) | set(after))
    for key in keys:
        if before.get(key) != after.get(key):
            changes[key] = {
                "before": deepcopy(before.get(key)),
                "after": deepcopy(after.get(key)),
            }
    return changes


def plan_migration(
    before_model: dict[str, Any],
    after_model: dict[str, Any],
) -> dict[str, Any]:
    changes: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    before_entities = _entity_map(before_model)
    after_entities = _entity_map(after_model)

    for entity_name in sorted(set(before_entities) | set(after_entities)):
        before_entity = before_entities.get(entity_name)
        after_entity = after_entities.get(entity_name)

        if before_entity is None and after_entity is not None:
            changes.append(
                {
                    "kind": "createTable",
                    "entity": entity_name,
                    "after": {
                        "table": after_entity["table"],
                        "fields": [
                            _field_signature(field)
                            for field in after_entity.get("fields", [])
                        ],
                    },
                    "destructive": False,
                }
            )
            continue

        if before_entity is not None and after_entity is None:
            changes.append(
                {
                    "kind": "dropTable",
                    "entity": entity_name,
                    "before": {"table": before_entity["table"]},
                    "destructive": True,
                }
            )
            warnings.append(
                _warning(
                    "drop-table",
                    f"Table '{before_entity['table']}' would be dropped.",
                    entity=entity_name,
                    change_kind="dropTable",
                )
            )
            continue

        assert before_entity is not None and after_entity is not None

        if before_entity["table"] != after_entity["table"]:
            changes.append(
                {
                    "kind": "renameTable",
                    "entity": entity_name,
                    "changes": {
                        "table": {
                            "before": before_entity["table"],
                            "after": after_entity["table"],
                        }
                    },
                    "destructive": False,
                }
            )
            warnings.append(
                _warning(
                    "rename-table",
                    (
                        f"Entity '{entity_name}' changes table name from "
                        f"'{before_entity['table']}' to '{after_entity['table']}'."
                    ),
                    entity=entity_name,
                    change_kind="renameTable",
                )
            )

        before_fields = _field_map(before_entity)
        after_fields = _field_map(after_entity)
        for field_name in sorted(set(before_fields) | set(after_fields)):
            before_field = before_fields.get(field_name)
            after_field = after_fields.get(field_name)

            if before_field is None and after_field is not None:
                changes.append(
                    {
                        "kind": "addColumn",
                        "entity": entity_name,
                        "field": field_name,
                        "after": _field_signature(after_field),
                        "destructive": False,
                    }
                )
                if _column_requires_backfill(after_field):
                    warnings.append(
                        _warning(
                            "add-required-column-without-default",
                            (
                                f"Column '{entity_name}.{field_name}' is added as NOT NULL "
                                "without a default or generated value."
                            ),
                            entity=entity_name,
                            field=field_name,
                            change_kind="addColumn",
                        )
                    )
                continue

            if before_field is not None and after_field is None:
                changes.append(
                    {
                        "kind": "dropColumn",
                        "entity": entity_name,
                        "field": field_name,
                        "before": _field_signature(before_field),
                        "destructive": True,
                    }
                )
                warnings.append(
                    _warning(
                        "drop-column",
                        f"Column '{entity_name}.{field_name}' would be dropped.",
                        entity=entity_name,
                        field=field_name,
                        change_kind="dropColumn",
                    )
                )
                continue

            assert before_field is not None and after_field is not None
            before_signature = _field_signature(before_field)
            after_signature = _field_signature(after_field)
            attribute_changes = _compare_signatures(before_signature, after_signature)
            if not attribute_changes:
                continue

            destructive = False
            if "type" in attribute_changes or "storageName" in attribute_changes:
                destructive = True
            if "nullable" in attribute_changes:
                nullable_change = attribute_changes["nullable"]
                if nullable_change["before"] is True and nullable_change["after"] is False:
                    destructive = True
            if "length" in attribute_changes:
                length_change = attribute_changes["length"]
                before_length = length_change["before"]
                after_length = length_change["after"]
                if (
                    isinstance(before_length, int)
                    and isinstance(after_length, int)
                    and after_length < before_length
                ):
                    destructive = True

            changes.append(
                {
                    "kind": "alterColumn",
                    "entity": entity_name,
                    "field": field_name,
                    "changes": attribute_changes,
                    "destructive": destructive,
                }
            )

            if "type" in attribute_changes:
                warnings.append(
                    _warning(
                        "change-column-type",
                        f"Column '{entity_name}.{field_name}' changes type.",
                        entity=entity_name,
                        field=field_name,
                        change_kind="alterColumn",
                    )
                )
            if "storageName" in attribute_changes:
                warnings.append(
                    _warning(
                        "rename-column",
                        f"Column '{entity_name}.{field_name}' changes storage name.",
                        entity=entity_name,
                        field=field_name,
                        change_kind="alterColumn",
                    )
                )
            if "nullable" in attribute_changes:
                nullable_change = attribute_changes["nullable"]
                if nullable_change["before"] is True and nullable_change["after"] is False:
                    warnings.append(
                        _warning(
                            "tighten-nullability",
                            f"Column '{entity_name}.{field_name}' becomes NOT NULL.",
                            entity=entity_name,
                            field=field_name,
                            change_kind="alterColumn",
                        )
                    )
            if "length" in attribute_changes:
                length_change = attribute_changes["length"]
                before_length = length_change["before"]
                after_length = length_change["after"]
                if (
                    isinstance(before_length, int)
                    and isinstance(after_length, int)
                    and after_length < before_length
                ):
                    warnings.append(
                        _warning(
                            "shrink-column-length",
                            f"Column '{entity_name}.{field_name}' reduces max length.",
                            entity=entity_name,
                            field=field_name,
                            change_kind="alterColumn",
                        )
                    )

        before_indexes = _index_map(before_entity)
        after_indexes = _index_map(after_entity)
        for index_key in sorted(set(before_indexes) | set(after_indexes)):
            before_index = before_indexes.get(index_key)
            after_index = after_indexes.get(index_key)
            index_name = (after_index or before_index or {}).get("name", index_key)

            if before_index is None and after_index is not None:
                changes.append(
                    {
                        "kind": "addIndex",
                        "entity": entity_name,
                        "name": index_name,
                        "after": _index_signature(after_index),
                        "destructive": False,
                    }
                )
                continue
            if before_index is not None and after_index is None:
                changes.append(
                    {
                        "kind": "dropIndex",
                        "entity": entity_name,
                        "name": index_name,
                        "before": _index_signature(before_index),
                        "destructive": False,
                    }
                )
                continue

            assert before_index is not None and after_index is not None
            before_signature = _index_signature(before_index)
            after_signature = _index_signature(after_index)
            index_changes = _compare_signatures(before_signature, after_signature)
            if index_changes:
                changes.append(
                    {
                        "kind": "alterIndex",
                        "entity": entity_name,
                        "name": index_name,
                        "changes": index_changes,
                        "destructive": False,
                    }
                )

        before_constraints = _constraint_map(before_entity)
        after_constraints = _constraint_map(after_entity)
        for constraint_key in sorted(set(before_constraints) | set(after_constraints)):
            before_constraint = before_constraints.get(constraint_key)
            after_constraint = after_constraints.get(constraint_key)
            constraint_name = (after_constraint or before_constraint or {}).get(
                "name", constraint_key
            )

            if before_constraint is None and after_constraint is not None:
                changes.append(
                    {
                        "kind": "addConstraint",
                        "entity": entity_name,
                        "name": constraint_name,
                        "after": _constraint_signature(after_constraint),
                        "destructive": False,
                    }
                )
                continue
            if before_constraint is not None and after_constraint is None:
                changes.append(
                    {
                        "kind": "dropConstraint",
                        "entity": entity_name,
                        "name": constraint_name,
                        "before": _constraint_signature(before_constraint),
                        "destructive": False,
                    }
                )
                continue

            assert before_constraint is not None and after_constraint is not None
            before_signature = _constraint_signature(before_constraint)
            after_signature = _constraint_signature(after_constraint)
            constraint_changes = _compare_signatures(before_signature, after_signature)
            if constraint_changes:
                changes.append(
                    {
                        "kind": "alterConstraint",
                        "entity": entity_name,
                        "name": constraint_name,
                        "changes": constraint_changes,
                        "destructive": False,
                    }
                )

    destructive_changes = sum(1 for change in changes if change.get("destructive"))
    return {
        "formatVersion": "0.1",
        "fromModelVersion": before_model.get("version"),
        "toModelVersion": after_model.get("version"),
        "changes": changes,
        "warnings": warnings,
        "summary": {
            "totalChanges": len(changes),
            "destructiveChanges": destructive_changes,
            "warnings": len(warnings),
        },
    }
