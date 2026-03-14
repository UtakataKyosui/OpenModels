from __future__ import annotations

from typing import Any

from .adapter import BackendAdapter, GeneratedFile
from .common import camel_case, escape_template_literal, snake_case, to_json_literal


DRIZZLE_PG_TARGET = "drizzle-pg"


def _enum_export_name(enum_name: str) -> str:
    return camel_case(snake_case(enum_name)) + "Enum"


def _table_export_name(table_name: str) -> str:
    return camel_case(table_name)


def _relation_export_name(table_name: str) -> str:
    return _table_export_name(table_name) + "Relations"


def _render_literal(value: Any) -> str:
    return to_json_literal(value)


def _drizzle_adapter_config(definition: dict[str, Any]) -> dict[str, Any]:
    return definition.get("adapters", {}).get(DRIZZLE_PG_TARGET, {})


def _collect_adapter_imports(
    definition: dict[str, Any],
    pg_core_imports: set[str],
    orm_imports: set[str],
) -> None:
    adapter_config = _drizzle_adapter_config(definition)
    imports = adapter_config.get("imports", {})
    for symbol in imports.get("pgCore", []):
        pg_core_imports.add(symbol)
    for symbol in imports.get("orm", []):
        orm_imports.add(symbol)


def _render_column_type(field: dict[str, Any]) -> str:
    storage_name = field.get("storageName", snake_case(field["name"]))
    field_type = field["type"]
    adapter_config = _drizzle_adapter_config(field)
    column_factory = adapter_config.get("columnFactory")
    if column_factory:
        return f'{column_factory}("{storage_name}")'

    if "enum" in field:
        return f'{_enum_export_name(field["enum"])}("{storage_name}")'
    if field_type == "uuid":
        return f'uuid("{storage_name}")'
    if field_type == "varchar":
        length = field.get("length")
        if length:
            return f'varchar("{storage_name}", {{ length: {length} }})'
        return f'varchar("{storage_name}")'
    if field_type == "text":
        return f'text("{storage_name}")'
    if field_type == "timestamptz":
        precision = field.get("precision")
        config = ['withTimezone: true', 'mode: "date"']
        if precision is not None:
            config.insert(0, f"precision: {precision}")
        return f'timestamp("{storage_name}", {{ {", ".join(config)} }})'
    if field_type == "timestamp":
        precision = field.get("precision")
        config = ['mode: "date"']
        if precision is not None:
            config.insert(0, f"precision: {precision}")
        return f'timestamp("{storage_name}", {{ {", ".join(config)} }})'
    if field_type == "integer":
        return f'integer("{storage_name}")'
    if field_type == "boolean":
        return f'boolean("{storage_name}")'

    raise ValueError(f"Unsupported Drizzle PostgreSQL type: {field_type}")


def _collect_inline_foreign_keys(entity: dict[str, Any]) -> dict[str, dict[str, Any]]:
    inline_foreign_keys: dict[str, dict[str, Any]] = {}
    for constraint in entity.get("constraints", []):
        if constraint.get("kind") != "foreignKey":
            continue
        fields = constraint.get("fields", [])
        references = constraint.get("references", {})
        target_fields = references.get("fields", [])
        if len(fields) == 1 and len(target_fields) == 1:
            inline_foreign_keys[fields[0]] = constraint
    return inline_foreign_keys


def _has_explicit_unique_constraint(entity: dict[str, Any], field_name: str) -> bool:
    for index in entity.get("indexes", []):
        if index.get("unique") and index.get("fields") == [field_name]:
            return True
    for constraint in entity.get("constraints", []):
        if constraint.get("kind") == "unique" and constraint.get("fields") == [field_name]:
            return True
    return False


def _render_column(field: dict[str, Any], entity: dict[str, Any], tables_by_entity: dict[str, str]) -> list[str]:
    lines: list[str] = []
    column_expression = _render_column_type(field)
    generated = field.get("generated", "none")
    adapter_config = _drizzle_adapter_config(field)

    for suffix in adapter_config.get("chain", []):
        column_expression += suffix

    if generated == "database" and field["type"] == "uuid" and field.get("primaryKey"):
        column_expression += ".defaultRandom()"
    elif generated == "database" and field["type"] in {"timestamp", "timestamptz"}:
        column_expression += ".defaultNow()"
    elif "default" in field:
        column_expression += f'.default({_render_literal(field["default"])})'

    inline_foreign_key = _collect_inline_foreign_keys(entity).get(field["name"])
    if inline_foreign_key:
        references = inline_foreign_key["references"]
        target_entity = references["entity"]
        target_field = references["fields"][0]
        target_table = tables_by_entity[target_entity]
        actions: list[str] = []
        if "onDelete" in references:
            actions.append(f'onDelete: "{references["onDelete"]}"')
        if "onUpdate" in references:
            actions.append(f'onUpdate: "{references["onUpdate"]}"')
        action_text = f", {{ {', '.join(actions)} }}" if actions else ""
        column_expression += (
            f".references(() => {target_table}.{target_field}{action_text})"
        )

    if field.get("unique") and not _has_explicit_unique_constraint(entity, field["name"]):
        column_expression += ".unique()"
    if not field.get("nullable", False) and not field.get("primaryKey", False):
        column_expression += ".notNull()"
    if field.get("primaryKey"):
        column_expression += ".primaryKey()"

    if "computed" in field and field["computed"].get("stored") and generated == "database":
        expression = escape_template_literal(field["computed"]["expression"])
        column_expression += f".generatedAlwaysAs(sql`{expression}`)"

    if "computed" in field and generated == "application":
        lines.append(
            f'    // computed by application: {field["computed"]["expression"]}'
        )

    lines.append(f'    {field["name"]}: {column_expression},')
    return lines


def _render_index(index_definition: dict[str, Any]) -> str:
    builder = "uniqueIndex" if index_definition.get("unique") else "index"
    fields = ", ".join(f"table.{field}" for field in index_definition["fields"])
    return f'{builder}("{index_definition["name"]}").on({fields})'


def _render_constraint(
    constraint: dict[str, Any],
    tables_by_entity: dict[str, str],
) -> str | None:
    kind = constraint["kind"]
    name = constraint.get("name")
    if kind == "unique":
        fields = ", ".join(f"table.{field}" for field in constraint["fields"])
        return f'uniqueIndex("{name}").on({fields})'
    if kind == "check":
        expression = escape_template_literal(constraint["expression"])
        return f'check("{name}", sql`{expression}`)'
    if kind == "foreignKey":
        fields = constraint.get("fields", [])
        target_fields = constraint["references"]["fields"]
        if len(fields) == 1 and len(target_fields) == 1:
            return None
        target_table = tables_by_entity[constraint["references"]["entity"]]
        columns = ", ".join(f"table.{field}" for field in fields)
        foreign_columns = ", ".join(f"{target_table}.{field}" for field in target_fields)
        expression = (
            "foreignKey({ "
            f'name: "{name}", columns: [{columns}], foreignColumns: [{foreign_columns}]'
            " })"
        )
        if "onDelete" in constraint["references"]:
            expression += f'.onDelete("{constraint["references"]["onDelete"]}")'
        if "onUpdate" in constraint["references"]:
            expression += f'.onUpdate("{constraint["references"]["onUpdate"]}")'
        return expression
    if kind == "primaryKey":
        fields = ", ".join(f"table.{field}" for field in constraint["fields"])
        if name:
            return f'primaryKey({{ name: "{name}", columns: [{fields}] }})'
        return f"primaryKey({{ columns: [{fields}] }})"
    return None


def _render_table(
    entity: dict[str, Any],
    tables_by_entity: dict[str, str],
) -> str:
    table_name = entity["table"]
    export_name = _table_export_name(table_name)
    table_factory = _drizzle_adapter_config(entity).get("tableFactory", "pgTable")
    lines = [
        f"export const {export_name} = {table_factory}(",
        f'  "{table_name}",',
        "  {",
    ]
    for field in entity["fields"]:
        lines.extend(_render_column(field, entity, tables_by_entity))
    lines.append("  },")

    callback_items: list[str] = []
    unique_signatures: set[tuple[str, tuple[str, ...]]] = set()
    for index_definition in entity.get("indexes", []):
        callback_items.append(_render_index(index_definition))
        if index_definition.get("unique"):
            unique_signatures.add(("unique", tuple(index_definition["fields"])))

    for constraint in entity.get("constraints", []):
        if constraint.get("kind") == "unique":
            signature = ("unique", tuple(constraint.get("fields", [])))
            if signature in unique_signatures:
                continue
            unique_signatures.add(signature)

        rendered_constraint = _render_constraint(constraint, tables_by_entity)
        if rendered_constraint:
            callback_items.append(rendered_constraint)

    if callback_items:
        lines.append("  (table) => [")
        for item in callback_items:
            lines.append(f"    {item},")
        lines.append("  ],")

    lines.append(");")
    return "\n".join(lines)


def _render_relation(entity: dict[str, Any], tables_by_entity: dict[str, str]) -> str | None:
    relations_definitions = entity.get("relations", [])
    if not relations_definitions:
        return None

    table_export = _table_export_name(entity["table"])
    relation_export = _relation_export_name(entity["table"])
    relation_kinds = set()
    for relation in relations_definitions:
        if relation["kind"] in {"belongsTo", "hasOne"}:
            relation_kinds.add("one")
        if relation["kind"] in {"hasMany", "manyToMany"}:
            relation_kinds.add("many")
    signature = ", ".join(sorted(relation_kinds))
    lines = [
        f"export const {relation_export} = relations({table_export}, ({{ {signature} }}) => ({{"
    ]

    for relation in relations_definitions:
        relation_name = relation["name"]
        target_table = _table_export_name(
            next(
                table_name
                for entity_name, table_name in tables_by_entity.items()
                if entity_name == relation["targetEntity"]
            )
        )
        kind = relation["kind"]
        ownership = relation["ownership"]

        if kind == "belongsTo" and ownership == "owner":
            lines.append(f"  {relation_name}: one({target_table}, {{")
            lines.append(
                f"    fields: [{table_export}.{relation['foreignKey']}],"
            )
            lines.append(
                f"    references: [{target_table}.{relation['references']}],"
            )
            lines.append("  }),")
            continue

        if kind == "hasOne" and ownership == "owner":
            lines.append(f"  {relation_name}: one({target_table}, {{")
            lines.append(
                f"    fields: [{table_export}.{relation['foreignKey']}],"
            )
            lines.append(
                f"    references: [{target_table}.{relation['references']}],"
            )
            lines.append("  }),")
            continue

        if kind == "hasOne" and ownership == "inverse":
            lines.append(f"  {relation_name}: one({target_table}),")
            continue

        if kind == "hasMany":
            lines.append(f"  {relation_name}: many({target_table}),")
            continue

        if kind == "manyToMany":
            lines.append(
                f"  // TODO: wire many-to-many relation '{relation_name}' through "
                f"{relation.get('throughEntity', 'a junction table')}"
            )
            continue

    lines.append("}));")
    return "\n".join(lines)


def generate_drizzle_schema(canonical_model: dict[str, Any]) -> str:
    tables_by_entity = {
        entity["name"]: entity["table"] for entity in canonical_model.get("entities", [])
    }

    pg_core_imports = {"pgTable"}
    orm_imports: set[str] = set()
    _collect_adapter_imports(canonical_model, pg_core_imports, orm_imports)

    for enum in canonical_model.get("enums", []):
        pg_core_imports.add("pgEnum")
        _collect_adapter_imports(enum, pg_core_imports, orm_imports)

    for entity in canonical_model.get("entities", []):
        _collect_adapter_imports(entity, pg_core_imports, orm_imports)
        if entity.get("relations"):
            orm_imports.add("relations")
        if entity.get("indexes"):
            for index_definition in entity["indexes"]:
                _collect_adapter_imports(index_definition, pg_core_imports, orm_imports)
                pg_core_imports.add(
                    "uniqueIndex" if index_definition.get("unique") else "index"
                )

        for field in entity["fields"]:
            _collect_adapter_imports(field, pg_core_imports, orm_imports)
            if "enum" in field:
                continue
            field_type = field["type"]
            column_factory = _drizzle_adapter_config(field).get("columnFactory")
            if column_factory:
                pg_core_imports.add(column_factory)
                if "computed" in field and field["computed"].get("stored") and field.get("generated") == "database":
                    orm_imports.add("sql")
                continue
            if field_type == "uuid":
                pg_core_imports.add("uuid")
            elif field_type == "varchar":
                pg_core_imports.add("varchar")
            elif field_type == "text":
                pg_core_imports.add("text")
            elif field_type in {"timestamp", "timestamptz"}:
                pg_core_imports.add("timestamp")
            elif field_type == "integer":
                pg_core_imports.add("integer")
            elif field_type == "boolean":
                pg_core_imports.add("boolean")
            else:
                raise ValueError(f"Unsupported Drizzle PostgreSQL type: {field_type}")

            if "computed" in field and field["computed"].get("stored") and field.get("generated") == "database":
                orm_imports.add("sql")

        for constraint in entity.get("constraints", []):
            _collect_adapter_imports(constraint, pg_core_imports, orm_imports)
            kind = constraint["kind"]
            if kind == "unique":
                pg_core_imports.add("uniqueIndex")
            elif kind == "check":
                pg_core_imports.add("check")
                orm_imports.add("sql")
            elif kind == "foreignKey":
                if len(constraint.get("fields", [])) != 1 or len(
                    constraint["references"].get("fields", [])
                ) != 1:
                    pg_core_imports.add("foreignKey")
            elif kind == "primaryKey":
                pg_core_imports.add("primaryKey")

    sections: list[str] = []
    if orm_imports:
        imports = ", ".join(sorted(orm_imports))
        sections.append(f'import {{ {imports} }} from "drizzle-orm";')
    pg_imports = ", ".join(sorted(pg_core_imports))
    sections.append(f'import {{ {pg_imports} }} from "drizzle-orm/pg-core";')

    enum_blocks = []
    for enum in canonical_model.get("enums", []):
        enum_export = _enum_export_name(enum["name"])
        enum_name = snake_case(enum["name"])
        values = ", ".join(_render_literal(value) for value in enum["values"])
        enum_blocks.append(
            f'export const {enum_export} = pgEnum("{enum_name}", [{values}]);'
        )
    if enum_blocks:
        sections.append("\n".join(enum_blocks))

    table_blocks = [
        _render_table(entity, tables_by_entity)
        for entity in canonical_model.get("entities", [])
    ]
    sections.append("\n\n".join(table_blocks))

    relation_blocks = list(
        filter(
            None,
            (
                _render_relation(entity, tables_by_entity)
                for entity in canonical_model.get("entities", [])
            ),
        )
    )
    if relation_blocks:
        sections.append("\n\n".join(relation_blocks))

    return "\n\n".join(sections) + "\n"


class DrizzlePgAdapter(BackendAdapter):
    key = DRIZZLE_PG_TARGET
    description = "Drizzle ORM schema for PostgreSQL"
    default_filename = "schema.ts"

    def generate_files(
        self,
        canonical_model: dict[str, Any],
        filename: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> list[GeneratedFile]:
        return [
            GeneratedFile(
                path=filename or self.default_filename,
                content=generate_drizzle_schema(canonical_model),
            )
        ]


DRIZZLE_PG_ADAPTER = DrizzlePgAdapter()
