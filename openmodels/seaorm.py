from __future__ import annotations

import re
from typing import Any

from .adapter import AdapterError, BackendAdapter, GeneratedFile
from .common import snake_case, to_json_literal, upper_camel_case


SEAORM_RUST_TARGET = "seaorm-rust"


def _seaorm_definition_config(definition: dict[str, Any]) -> dict[str, Any]:
    return definition.get("adapters", {}).get(SEAORM_RUST_TARGET, {})


def _seaorm_entity_config(entity: dict[str, Any]) -> dict[str, Any]:
    return _seaorm_definition_config(entity)


def _seaorm_field_config(field: dict[str, Any]) -> dict[str, Any]:
    return _seaorm_definition_config(field)


def _seaorm_relation_config(relation: dict[str, Any]) -> dict[str, Any]:
    return _seaorm_definition_config(relation)


def _module_name(entity: dict[str, Any]) -> str:
    adapter_config = _seaorm_entity_config(entity)
    return adapter_config.get("moduleName", snake_case(entity["name"]))


def _persisted_fields(entity: dict[str, Any]) -> list[dict[str, Any]]:
    return [field for field in entity.get("fields", []) if field.get("persisted", True)]


def _raw_rust_type(field: dict[str, Any]) -> str:
    adapter_config = _seaorm_field_config(field)
    if "rustType" in adapter_config:
        return adapter_config["rustType"]

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

    raise AdapterError(f"Unsupported SeaORM Rust type mapping for canonical field type '{field_type}'.")


def _seaorm_rust_type(field: dict[str, Any]) -> str:
    rust_type = _raw_rust_type(field)
    if field.get("nullable", False):
        return f"Option<{rust_type}>"
    return rust_type


def _seaorm_column_type(field: dict[str, Any]) -> str:
    adapter_config = _seaorm_field_config(field)
    if "columnType" in adapter_config:
        return adapter_config["columnType"]

    field_type = field["type"]
    if field_type == "uuid":
        return "Uuid"
    if field_type == "varchar":
        length = field.get("length")
        if length is None:
            return "String(StringLen::None)"
        return f"String(StringLen::N({length}))"
    if field_type == "text":
        return "Text"
    if field_type == "integer":
        return "Integer"
    if field_type == "boolean":
        return "Boolean"
    if field_type == "timestamp":
        return "Timestamp"
    if field_type == "timestamptz":
        return "TimestampWithTimeZone"

    raise AdapterError(f"Unsupported SeaORM column type mapping for canonical field type '{field_type}'.")


def _render_attribute_lines(values: list[Any], context: str) -> list[str]:
    lines: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise AdapterError(f"{context} must contain only non-empty strings.")
        lines.append(value)
    return lines


def _field_rust_name(field: dict[str, Any]) -> str:
    return field.get("storageName", snake_case(field["name"]))


def _primary_key_fields(entity: dict[str, Any]) -> list[str]:
    names = [field["name"] for field in entity.get("fields", []) if field.get("primaryKey")]
    for constraint in entity.get("constraints", []):
        if constraint.get("kind") == "primaryKey":
            for field_name in constraint.get("fields", []):
                if field_name not in names:
                    names.append(field_name)
    return names


def _column_variant_name(field_name: str) -> str:
    return upper_camel_case(snake_case(field_name))


def _enum_variant_name(value: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", value)
    if not parts:
        return "Value"
    name = upper_camel_case(" ".join(parts))
    if name[:1].isdigit():
        return f"Value{name}"
    return name


def _active_enums_for_entity(
    entity: dict[str, Any],
    enums_by_name: dict[str, dict[str, Any]],
) -> list[tuple[dict[str, Any], str]]:
    db_type_by_enum: dict[str, str] = {}
    for field in _persisted_fields(entity):
        enum_name = field.get("enum")
        if enum_name is None:
            continue
        if "rustType" in _seaorm_field_config(field):
            continue
        if enum_name not in enums_by_name:
            raise AdapterError(f"Entity '{entity['name']}' references unknown enum '{enum_name}'.")

        db_type = _seaorm_column_type(field)
        previous = db_type_by_enum.get(enum_name)
        if previous is not None and previous != db_type:
            raise AdapterError(
                f"Entity '{entity['name']}' uses enum '{enum_name}' with incompatible SeaORM db types: "
                f"'{previous}' and '{db_type}'."
            )
        db_type_by_enum[enum_name] = db_type

    active_enums: list[tuple[dict[str, Any], str]] = []
    for enum_name in sorted(db_type_by_enum):
        active_enums.append((enums_by_name[enum_name], db_type_by_enum[enum_name]))
    return active_enums


def _render_active_enum(enum_definition: dict[str, Any], db_type: str) -> str:
    lines = [
        "#[derive(Copy, Clone, Debug, PartialEq, Eq, EnumIter, DeriveActiveEnum)]",
        (
            f'#[sea_orm(rs_type = "String", db_type = "{db_type}", '
            f'enum_name = "{snake_case(enum_definition["name"])}")]'
        ),
        f'pub enum {upper_camel_case(enum_definition["name"])} {{',
    ]
    for value in enum_definition.get("values", []):
        lines.append(f'    #[sea_orm(string_value = {to_json_literal(value)})]')
        lines.append(f"    {_enum_variant_name(value)},")
    lines.append("}")
    return "\n".join(lines)


def _field_comment_lines(field: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if "default" in field:
        lines.append(f"// OpenModels: default = {to_json_literal(field['default'])}")
    generated = field.get("generated", "none")
    if generated != "none":
        lines.append(f"// OpenModels: generated = {generated}")
    computed = field.get("computed")
    if computed:
        lines.append(f"// OpenModels: computed = {computed['expression']}")
    return lines


def _field_attribute_lines(field: dict[str, Any]) -> list[str]:
    adapter_config = _seaorm_field_config(field)
    attributes = _render_attribute_lines(
        adapter_config.get("extraAttributes", []),
        f"Field '{field['name']}' adapters.seaorm-rust.extraAttributes",
    )

    tokens: list[str] = []
    if field.get("primaryKey"):
        tokens.append("primary_key")
        auto_increment = field["type"] == "integer" and field.get("generated") == "database"
        tokens.append(f"auto_increment = {'true' if auto_increment else 'false'}")
    tokens.append(f'column_type = "{_seaorm_column_type(field)}"')

    attributes.append(f"#[sea_orm({', '.join(tokens)})]")
    return attributes


def _render_model(entity: dict[str, Any]) -> str:
    primary_key_fields = _primary_key_fields(entity)
    if len(primary_key_fields) != 1:
        raise AdapterError(
            f"SeaORM Phase 2 requires exactly one primary key field for entity '{entity['name']}'."
        )

    persisted_fields = _persisted_fields(entity)
    if not persisted_fields:
        raise AdapterError(
            f"SeaORM entity '{entity['name']}' has no persisted fields to generate."
        )

    entity_config = _seaorm_entity_config(entity)
    derive_items = ["Clone", "Debug", "PartialEq", "Eq", "DeriveEntityModel"]
    for derive_item in entity_config.get("extraDerives", []):
        if not isinstance(derive_item, str) or not derive_item.strip():
            raise AdapterError(
                f"Entity '{entity['name']}' adapters.seaorm-rust.extraDerives must contain only non-empty strings."
            )
        if derive_item not in derive_items:
            derive_items.append(derive_item)

    lines = [f"#[derive({', '.join(derive_items)})]"]
    lines.extend(
        _render_attribute_lines(
            entity_config.get("extraAttributes", []),
            f"Entity '{entity['name']}' adapters.seaorm-rust.extraAttributes",
        )
    )
    lines.append(f'#[sea_orm(table_name = "{entity["table"]}")]')
    lines.append("pub struct Model {")
    for field in persisted_fields:
        for comment in _field_comment_lines(field):
            lines.append(f"    {comment}")
        for attribute in _field_attribute_lines(field):
            lines.append(f"    {attribute}")
        lines.append(f"    pub {_field_rust_name(field)}: {_seaorm_rust_type(field)},")
    lines.append("}")
    return "\n".join(lines)


def _relation_variant_name(relation: dict[str, Any]) -> str:
    relation_config = _seaorm_relation_config(relation)
    variant_name = relation_config.get("variantName")
    if variant_name is None:
        variant_name = upper_camel_case(snake_case(relation["name"]))
    if not isinstance(variant_name, str) or not variant_name.strip():
        raise AdapterError(
            f"Relation '{relation['name']}' adapters.seaorm-rust.variantName must be a non-empty string."
        )
    return variant_name


def _related_entity_path(entity_by_name: dict[str, dict[str, Any]], entity_name: str) -> str:
    return f"super::{_module_name(entity_by_name[entity_name])}::Entity"


def _related_column_path(entity_by_name: dict[str, dict[str, Any]], entity_name: str, field_name: str) -> str:
    return f"super::{_module_name(entity_by_name[entity_name])}::Column::{_column_variant_name(field_name)}"


def _seaorm_reference_action(value: str) -> str:
    mapping = {
        "noAction": "NoAction",
        "restrict": "Restrict",
        "cascade": "Cascade",
        "setNull": "SetNull",
        "setDefault": "SetDefault",
    }
    try:
        return mapping[value]
    except KeyError as exc:
        raise AdapterError(f"Unsupported SeaORM foreign key action '{value}'.") from exc


def _matching_foreign_key_constraint(entity: dict[str, Any], relation: dict[str, Any]) -> dict[str, Any] | None:
    if relation["kind"] != "belongsTo":
        return None

    foreign_key = relation.get("foreignKey")
    reference_field = relation.get("references")
    if not foreign_key or not reference_field:
        return None

    for constraint in entity.get("constraints", []):
        if constraint.get("kind") != "foreignKey":
            continue
        if constraint.get("fields") != [foreign_key]:
            continue
        references = constraint.get("references", {})
        if references.get("entity") != relation["targetEntity"]:
            continue
        if references.get("fields") != [reference_field]:
            continue
        return constraint
    return None


def _relation_attribute_lines(
    relation: dict[str, Any],
    entity: dict[str, Any],
    entity_by_name: dict[str, dict[str, Any]],
) -> list[str]:
    relation_config = _seaorm_relation_config(relation)
    attributes = _render_attribute_lines(
        relation_config.get("extraAttributes", []),
        f"Relation '{entity['name']}.{relation['name']}' adapters.seaorm-rust.extraAttributes",
    )

    target_entity = relation["targetEntity"]
    target_path = _related_entity_path(entity_by_name, target_entity)
    kind = relation["kind"]
    tokens: list[str]

    if kind == "belongsTo":
        foreign_key = relation.get("foreignKey")
        reference_field = relation.get("references")
        if not foreign_key or not reference_field:
            raise AdapterError(
                f"SeaORM belongsTo relation '{entity['name']}.{relation['name']}' requires foreignKey and references."
            )
        tokens = [
            f'belongs_to = "{target_path}"',
            f'from = "Column::{_column_variant_name(foreign_key)}"',
            f'to = "{_related_column_path(entity_by_name, target_entity, reference_field)}"',
        ]
        constraint = _matching_foreign_key_constraint(entity, relation)
        if constraint is not None:
            references = constraint["references"]
            if "onUpdate" in references:
                tokens.append(f'on_update = "{_seaorm_reference_action(references["onUpdate"])}"')
            if "onDelete" in references:
                tokens.append(f'on_delete = "{_seaorm_reference_action(references["onDelete"])}"')
    elif kind == "hasMany":
        tokens = [f'has_many = "{target_path}"']
    elif kind == "hasOne":
        tokens = [f'has_one = "{target_path}"']
    else:
        raise AdapterError(
            f"SeaORM Phase 3 does not support relation kind '{kind}' on '{entity['name']}.{relation['name']}'."
        )

    attributes.append(f"#[sea_orm({', '.join(tokens)})]")
    return attributes


def _render_relation_enum(
    entity: dict[str, Any],
    entity_by_name: dict[str, dict[str, Any]],
) -> str:
    lines = ["#[derive(Copy, Clone, Debug, EnumIter, DeriveRelation)]", "pub enum Relation {"]
    for relation in entity.get("relations", []):
        for attribute in _relation_attribute_lines(relation, entity, entity_by_name):
            lines.append(f"    {attribute}")
        lines.append(f"    {_relation_variant_name(relation)},")
    lines.append("}")
    return "\n".join(lines)


def _related_impl_lines(
    entity: dict[str, Any],
    entity_by_name: dict[str, dict[str, Any]],
) -> list[str]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for relation in entity.get("relations", []):
        relation_config = _seaorm_relation_config(relation)
        skip_related_impl = relation_config.get("skipRelatedImpl", False)
        if not isinstance(skip_related_impl, bool):
            raise AdapterError(
                f"Relation '{entity['name']}.{relation['name']}' adapters.seaorm-rust.skipRelatedImpl must be boolean."
            )
        if skip_related_impl:
            continue
        grouped.setdefault(relation["targetEntity"], []).append(relation)

    for target_entity, relations in grouped.items():
        if len(relations) > 1:
            relation_names = ", ".join(relation["name"] for relation in relations)
            raise AdapterError(
                f"Entity '{entity['name']}' has multiple SeaORM relations to '{target_entity}' "
                f"({relation_names}). Set adapters.seaorm-rust.skipRelatedImpl on all but one relation."
            )

    lines: list[str] = []
    for target_entity in sorted(grouped):
        relation = grouped[target_entity][0]
        lines.extend(
            [
                f"impl Related<{_related_entity_path(entity_by_name, target_entity)}> for Entity {{",
                "    fn to() -> RelationDef {",
                f"        Relation::{_relation_variant_name(relation)}.def()",
                "    }",
                "}",
            ]
        )
    return lines


def _constraint_comment_lines(entity: dict[str, Any]) -> list[str]:
    indexes = entity.get("indexes", [])
    constraints = [
        constraint
        for constraint in entity.get("constraints", [])
        if constraint.get("kind") not in {"primaryKey", "foreignKey"}
    ]
    if not indexes and not constraints:
        return []

    lines = [
        "// OpenModels Phase 3 does not emit indexes or non-foreign-key constraints yet.",
    ]
    if indexes:
        lines.append("// Planned indexes:")
        for index in indexes:
            uniqueness = " unique" if index.get("unique") else ""
            lines.append(
                f"// - {index['name']}:{uniqueness} [{', '.join(index.get('fields', []))}]"
            )
    if constraints:
        lines.append("// Planned constraints:")
        for constraint in constraints:
            name = constraint.get("name", "<anonymous>")
            detail = f"{name}: {constraint['kind']}"
            fields = constraint.get("fields")
            if fields:
                detail += f" [{', '.join(fields)}]"
            if constraint.get("kind") == "foreignKey":
                references = constraint["references"]
                detail += (
                    f" -> {references['entity']}[{', '.join(references.get('fields', []))}]"
                )
            if constraint.get("kind") == "check":
                detail += f" ({constraint['expression']})"
            lines.append(f"// - {detail}")
    return lines


def _render_entity_file(
    entity: dict[str, Any],
    module_root: str,
    enums_by_name: dict[str, dict[str, Any]],
    entity_by_name: dict[str, dict[str, Any]],
) -> GeneratedFile:
    lines = [
        "use sea_orm::entity::prelude::*;",
    ]

    active_enums = _active_enums_for_entity(entity, enums_by_name)
    if active_enums:
        lines.append("")
        for index, (enum_definition, db_type) in enumerate(active_enums):
            if index > 0:
                lines.append("")
            lines.append(_render_active_enum(enum_definition, db_type))

    lines.append("")
    lines.append(_render_model(entity))
    lines.append("")

    lines.append(_render_relation_enum(entity, entity_by_name))
    related_impls = _related_impl_lines(entity, entity_by_name)
    if related_impls:
        lines.append("")
        lines.extend(related_impls)

    constraint_comments = _constraint_comment_lines(entity)
    if constraint_comments:
        lines.append("")
        lines.extend(constraint_comments)

    lines.extend(["", "impl ActiveModelBehavior for ActiveModel {}"])
    return GeneratedFile(path=f"{module_root}/{_module_name(entity)}.rs", content="\n".join(lines) + "\n")


def _mod_file(entities: list[dict[str, Any]], module_root: str) -> GeneratedFile:
    lines = [
        "//! Generated by OpenModels for seaorm-rust.",
        "",
        "pub mod prelude;",
    ]
    for entity in sorted(entities, key=lambda item: _module_name(item)):
        lines.append(f"pub mod {_module_name(entity)};")
    return GeneratedFile(path=f"{module_root}/mod.rs", content="\n".join(lines) + "\n")


def _prelude_file(entities: list[dict[str, Any]], module_root: str) -> GeneratedFile:
    lines = [
        "//! Public SeaORM entity exports generated by OpenModels.",
        "",
    ]
    for entity in sorted(entities, key=lambda item: item["name"]):
        lines.append(
            f"pub use super::{_module_name(entity)}::Entity as {upper_camel_case(entity['name'])};"
        )
    return GeneratedFile(path=f"{module_root}/prelude.rs", content="\n".join(lines) + "\n")


class SeaOrmRustAdapter(BackendAdapter):
    key = SEAORM_RUST_TARGET
    description = "SeaORM Rust entity generator"
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
        entity_by_name = {entity["name"]: entity for entity in entities}
        enums_by_name = {
            enum_definition["name"]: enum_definition
            for enum_definition in canonical_model.get("enums", [])
        }
        files = [
            _mod_file(entities, module_root),
            _prelude_file(entities, module_root),
        ]
        files.extend(
            _render_entity_file(entity, module_root, enums_by_name, entity_by_name)
            for entity in sorted(entities, key=lambda item: _module_name(item))
        )
        return files


SEAORM_RUST_ADAPTER = SeaOrmRustAdapter()
