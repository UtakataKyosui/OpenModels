use std::collections::{BTreeSet, HashMap, HashSet};

use serde_json::Value;

use crate::adapter::{BackendAdapter, GeneratedFile};
use crate::error::{message, Result};
use crate::model::{AdapterMap, CanonicalModel, Constraint, Entity, Field, Index, JsonObject};
use crate::utils::{camel_case, escape_template_literal, snake_case, to_json_literal};

pub const DRIZZLE_PG_TARGET: &str = "drizzle-pg";
pub static DRIZZLE_PG_ADAPTER: DrizzlePgAdapter = DrizzlePgAdapter;

pub struct DrizzlePgAdapter;

pub fn generate_drizzle_schema(model: &CanonicalModel) -> Result<String> {
    let tables_by_entity = model
        .entities
        .iter()
        .map(|entity| (entity.name.as_str(), entity.table.as_str()))
        .collect::<HashMap<_, _>>();

    let mut pg_core_imports = BTreeSet::from([String::from("pgTable")]);
    let mut orm_imports = BTreeSet::new();
    collect_adapter_imports(
        model.adapters.as_ref(),
        &mut pg_core_imports,
        &mut orm_imports,
    );

    for canonical_enum in &model.enums {
        pg_core_imports.insert(String::from("pgEnum"));
        collect_adapter_imports(
            canonical_enum.adapters.as_ref(),
            &mut pg_core_imports,
            &mut orm_imports,
        );
    }

    for entity in &model.entities {
        collect_adapter_imports(
            entity.adapters.as_ref(),
            &mut pg_core_imports,
            &mut orm_imports,
        );
        if !entity.relations.is_empty() {
            orm_imports.insert(String::from("relations"));
        }
        for index in &entity.indexes {
            collect_adapter_imports(
                index.adapters.as_ref(),
                &mut pg_core_imports,
                &mut orm_imports,
            );
            pg_core_imports.insert(if index.unique {
                String::from("uniqueIndex")
            } else {
                String::from("index")
            });
        }
        for field in &entity.fields {
            collect_adapter_imports(
                field.adapters.as_ref(),
                &mut pg_core_imports,
                &mut orm_imports,
            );
            if field.enum_name.is_some() {
                continue;
            }
            if let Some(column_factory) = adapter_string(field.adapters.as_ref(), "columnFactory") {
                pg_core_imports.insert(column_factory.to_owned());
                if field
                    .computed
                    .as_ref()
                    .is_some_and(|computed| computed.stored)
                    && field.generated == "database"
                {
                    orm_imports.insert(String::from("sql"));
                }
                continue;
            }
            let import = match field.field_type.as_str() {
                "uuid" => "uuid",
                "varchar" => "varchar",
                "text" => "text",
                "timestamp" | "timestamptz" => "timestamp",
                "integer" => "integer",
                "boolean" => "boolean",
                other => {
                    return Err(message(format!(
                        "Unsupported Drizzle PostgreSQL type: {}",
                        other
                    )));
                }
            };
            pg_core_imports.insert(import.to_owned());

            if field
                .computed
                .as_ref()
                .is_some_and(|computed| computed.stored)
                && field.generated == "database"
            {
                orm_imports.insert(String::from("sql"));
            }
        }
        for constraint in &entity.constraints {
            collect_adapter_imports(
                constraint.adapters.as_ref(),
                &mut pg_core_imports,
                &mut orm_imports,
            );
            match constraint.kind.as_str() {
                "unique" => {
                    pg_core_imports.insert(String::from("uniqueIndex"));
                }
                "check" => {
                    pg_core_imports.insert(String::from("check"));
                    orm_imports.insert(String::from("sql"));
                }
                "foreignKey" => {
                    if !is_inline_foreign_key(constraint) {
                        pg_core_imports.insert(String::from("foreignKey"));
                    }
                }
                "primaryKey" => {
                    pg_core_imports.insert(String::from("primaryKey"));
                }
                _ => {}
            }
        }
    }

    let mut sections = Vec::new();
    if !orm_imports.is_empty() {
        sections.push(format!(
            "import {{ {} }} from \"drizzle-orm\";",
            orm_imports.into_iter().collect::<Vec<_>>().join(", ")
        ));
    }
    sections.push(format!(
        "import {{ {} }} from \"drizzle-orm/pg-core\";",
        pg_core_imports.into_iter().collect::<Vec<_>>().join(", ")
    ));

    let enum_blocks = model
        .enums
        .iter()
        .map(|canonical_enum| -> Result<String> {
            let values = drizzle_enum_values(canonical_enum)?;
            Ok(format!(
                "export const {} = pgEnum(\"{}\", [{}]);",
                enum_export_name(&canonical_enum.name),
                snake_case(&canonical_enum.name),
                values
                    .iter()
                    .map(|value| to_json_literal(value))
                    .collect::<Vec<_>>()
                    .join(", ")
            ))
        })
        .collect::<Result<Vec<_>>>()?;
    if !enum_blocks.is_empty() {
        sections.push(enum_blocks.join("\n"));
    }

    sections.push(
        model
            .entities
            .iter()
            .map(|entity| render_table(entity, &tables_by_entity))
            .collect::<Result<Vec<_>>>()?
            .join("\n\n"),
    );

    let relation_blocks = model
        .entities
        .iter()
        .filter_map(|entity| render_relation(entity, &tables_by_entity).transpose())
        .collect::<Result<Vec<_>>>()?;
    if !relation_blocks.is_empty() {
        sections.push(relation_blocks.join("\n\n"));
    }

    Ok(sections.join("\n\n") + "\n")
}

impl BackendAdapter for DrizzlePgAdapter {
    fn key(&self) -> &'static str {
        DRIZZLE_PG_TARGET
    }

    fn description(&self) -> &'static str {
        "Drizzle ORM schema for PostgreSQL"
    }

    fn default_filename(&self) -> &'static str {
        "schema.ts"
    }

    fn generate_files(
        &self,
        canonical_model: &CanonicalModel,
        filename: Option<&str>,
        _options: Option<&JsonObject>,
    ) -> Result<Vec<GeneratedFile>> {
        Ok(vec![GeneratedFile {
            path: filename.unwrap_or(self.default_filename()).to_owned(),
            content: generate_drizzle_schema(canonical_model)?,
        }])
    }
}

fn enum_export_name(enum_name: &str) -> String {
    format!("{}Enum", camel_case(&snake_case(enum_name)))
}

fn table_export_name(table_name: &str) -> String {
    camel_case(table_name)
}

fn drizzle_enum_values<'a>(
    canonical_enum: &'a crate::model::CanonicalEnum,
) -> Result<Vec<&'a Value>> {
    let mut values = Vec::new();
    for value in &canonical_enum.values {
        if !value.is_string() {
            return Err(message(format!(
                "Drizzle PostgreSQL enum '{}' requires string values, but found {}.",
                canonical_enum.name, value
            )));
        }
        values.push(value);
    }
    Ok(values)
}

fn relation_export_name(table_name: &str) -> String {
    format!("{}Relations", table_export_name(table_name))
}

fn drizzle_adapter_config<'a>(adapters: Option<&'a AdapterMap>) -> Option<&'a JsonObject> {
    adapters.and_then(|adapters| adapters.get(DRIZZLE_PG_TARGET))
}

fn adapter_string<'a>(adapters: Option<&'a AdapterMap>, key: &str) -> Option<&'a str> {
    drizzle_adapter_config(adapters)?
        .get(key)
        .and_then(Value::as_str)
}

fn adapter_string_array(adapters: Option<&AdapterMap>, key: &str) -> Vec<String> {
    drizzle_adapter_config(adapters)
        .and_then(|config| config.get(key))
        .and_then(Value::as_array)
        .map(|values| {
            values
                .iter()
                .filter_map(Value::as_str)
                .map(ToOwned::to_owned)
                .collect::<Vec<_>>()
        })
        .unwrap_or_default()
}

fn collect_adapter_imports(
    adapters: Option<&AdapterMap>,
    pg_core_imports: &mut BTreeSet<String>,
    orm_imports: &mut BTreeSet<String>,
) {
    let Some(config) = drizzle_adapter_config(adapters) else {
        return;
    };
    let Some(imports) = config.get("imports").and_then(Value::as_object) else {
        return;
    };
    for symbol in imports
        .get("pgCore")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(Value::as_str)
    {
        pg_core_imports.insert(symbol.to_owned());
    }
    for symbol in imports
        .get("orm")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(Value::as_str)
    {
        orm_imports.insert(symbol.to_owned());
    }
}

fn render_column_type(field: &Field) -> Result<String> {
    if let Some(column_factory) = adapter_string(field.adapters.as_ref(), "columnFactory") {
        return Ok(format!("{}(\"{}\")", column_factory, field.storage_name));
    }
    if let Some(enum_name) = &field.enum_name {
        return Ok(format!(
            "{}(\"{}\")",
            enum_export_name(enum_name),
            field.storage_name
        ));
    }
    match field.field_type.as_str() {
        "uuid" => Ok(format!("uuid(\"{}\")", field.storage_name)),
        "varchar" => {
            if let Some(length) = field.length {
                Ok(format!(
                    "varchar(\"{}\", {{ length: {} }})",
                    field.storage_name, length
                ))
            } else {
                Ok(format!("varchar(\"{}\")", field.storage_name))
            }
        }
        "text" => Ok(format!("text(\"{}\")", field.storage_name)),
        "timestamptz" => {
            let mut config = vec![
                String::from("withTimezone: true"),
                String::from("mode: \"date\""),
            ];
            if let Some(precision) = field.precision {
                config.insert(0, format!("precision: {}", precision));
            }
            Ok(format!(
                "timestamp(\"{}\", {{ {} }})",
                field.storage_name,
                config.join(", ")
            ))
        }
        "timestamp" => {
            let mut config = vec![String::from("mode: \"date\"")];
            if let Some(precision) = field.precision {
                config.insert(0, format!("precision: {}", precision));
            }
            Ok(format!(
                "timestamp(\"{}\", {{ {} }})",
                field.storage_name,
                config.join(", ")
            ))
        }
        "integer" => Ok(format!("integer(\"{}\")", field.storage_name)),
        "boolean" => Ok(format!("boolean(\"{}\")", field.storage_name)),
        other => Err(message(format!(
            "Unsupported Drizzle PostgreSQL type: {}",
            other
        ))),
    }
}

fn collect_inline_foreign_keys<'a>(entity: &'a Entity) -> HashMap<&'a str, &'a Constraint> {
    let mut inline_foreign_keys = HashMap::new();
    for constraint in &entity.constraints {
        if constraint.kind != "foreignKey" {
            continue;
        }
        let Some(fields) = constraint.fields.as_ref() else {
            continue;
        };
        let Some(references) = constraint.references.as_ref() else {
            continue;
        };
        if fields.len() == 1 && references.fields.len() == 1 {
            inline_foreign_keys.insert(fields[0].as_str(), constraint);
        }
    }
    inline_foreign_keys
}

fn has_explicit_unique_constraint(entity: &Entity, field_name: &str) -> bool {
    entity
        .indexes
        .iter()
        .any(|index| index.unique && index.fields.len() == 1 && index.fields[0] == field_name)
        || entity.constraints.iter().any(|constraint| {
            constraint.kind == "unique"
                && constraint
                    .fields
                    .as_ref()
                    .is_some_and(|fields| fields.len() == 1 && fields[0] == field_name)
        })
}

fn render_column(
    field: &Field,
    entity: &Entity,
    inline_foreign_keys: &HashMap<&str, &Constraint>,
    tables_by_entity: &HashMap<&str, &str>,
) -> Result<Vec<String>> {
    let mut lines = Vec::new();
    let mut column_expression = render_column_type(field)?;

    for suffix in adapter_string_array(field.adapters.as_ref(), "chain") {
        column_expression.push_str(&suffix);
    }

    if field.generated == "database"
        && field.field_type == "uuid"
        && field.primary_key.unwrap_or(false)
    {
        column_expression.push_str(".defaultRandom()");
    } else if field.generated == "database"
        && (field.field_type == "timestamp" || field.field_type == "timestamptz")
    {
        column_expression.push_str(".defaultNow()");
    } else if let Some(default) = &field.default {
        column_expression.push_str(&format!(".default({})", to_json_literal(default)));
    }

    if let Some(inline_foreign_key) = inline_foreign_keys.get(field.name.as_str()) {
        let references = inline_foreign_key
            .references
            .as_ref()
            .expect("inline foreign key references");
        let target_table = tables_by_entity
            .get(references.entity.as_str())
            .ok_or_else(|| message(format!("Unknown target entity '{}'.", references.entity)))?;
        let target_field = references
            .fields
            .first()
            .ok_or_else(|| message("Foreign key reference must contain at least one field."))?;
        let mut actions = Vec::new();
        if let Some(on_delete) = &references.on_delete {
            actions.push(format!("onDelete: \"{}\"", on_delete));
        }
        if let Some(on_update) = &references.on_update {
            actions.push(format!("onUpdate: \"{}\"", on_update));
        }
        let action_text = if actions.is_empty() {
            String::new()
        } else {
            format!(", {{ {} }}", actions.join(", "))
        };
        column_expression.push_str(&format!(
            ".references(() => {}.{}{})",
            table_export_name(target_table),
            target_field,
            action_text
        ));
    }

    if field.unique.unwrap_or(false) && !has_explicit_unique_constraint(entity, &field.name) {
        column_expression.push_str(".unique()");
    }
    if !field.nullable && !field.primary_key.unwrap_or(false) {
        column_expression.push_str(".notNull()");
    }
    if field.primary_key.unwrap_or(false) {
        column_expression.push_str(".primaryKey()");
    }

    if let Some(computed) = &field.computed {
        if computed.stored && field.generated == "database" {
            column_expression.push_str(&format!(
                ".generatedAlwaysAs(sql`{}`)",
                escape_template_literal(&computed.expression)
            ));
        }
        if field.generated == "application" {
            lines.push(format!(
                "    // computed by application: {}",
                computed.expression
            ));
        }
    }

    lines.push(format!("    {}: {},", field.name, column_expression));
    Ok(lines)
}

fn render_index(index: &Index) -> Result<String> {
    let builder = if index.unique { "uniqueIndex" } else { "index" };
    let name = index
        .name
        .as_ref()
        .ok_or_else(|| message("Index name is required for Drizzle generation."))?;
    Ok(format!(
        "{}(\"{}\").on({})",
        builder,
        name,
        index
            .fields
            .iter()
            .map(|field| format!("table.{}", field))
            .collect::<Vec<_>>()
            .join(", ")
    ))
}

fn is_inline_foreign_key(constraint: &Constraint) -> bool {
    constraint.kind == "foreignKey"
        && constraint
            .fields
            .as_ref()
            .is_some_and(|fields| fields.len() == 1)
        && constraint
            .references
            .as_ref()
            .is_some_and(|references| references.fields.len() == 1)
}

fn render_constraint(
    constraint: &Constraint,
    tables_by_entity: &HashMap<&str, &str>,
) -> Result<Option<String>> {
    match constraint.kind.as_str() {
        "unique" => {
            let name = constraint
                .name
                .as_ref()
                .ok_or_else(|| message("Unique constraint name is required."))?;
            let fields = constraint
                .fields
                .as_ref()
                .ok_or_else(|| message("Unique constraint fields are required."))?;
            Ok(Some(format!(
                "uniqueIndex(\"{}\").on({})",
                name,
                fields
                    .iter()
                    .map(|field| format!("table.{}", field))
                    .collect::<Vec<_>>()
                    .join(", ")
            )))
        }
        "check" => {
            let name = constraint
                .name
                .as_ref()
                .ok_or_else(|| message("Check constraint name is required."))?;
            let expression = constraint
                .expression
                .as_ref()
                .ok_or_else(|| message("Check constraint expression is required."))?;
            Ok(Some(format!(
                "check(\"{}\", sql`{}`)",
                name,
                escape_template_literal(expression)
            )))
        }
        "foreignKey" => {
            if is_inline_foreign_key(constraint) {
                return Ok(None);
            }
            let name = constraint
                .name
                .as_ref()
                .ok_or_else(|| message("Foreign key constraint name is required."))?;
            let fields = constraint
                .fields
                .as_ref()
                .ok_or_else(|| message("Foreign key fields are required."))?;
            let references = constraint
                .references
                .as_ref()
                .ok_or_else(|| message("Foreign key references are required."))?;
            let target_table = tables_by_entity
                .get(references.entity.as_str())
                .ok_or_else(|| {
                    message(format!("Unknown target entity '{}'.", references.entity))
                })?;
            let mut expression = format!(
                "foreignKey({{ name: \"{}\", columns: [{}], foreignColumns: [{}] }})",
                name,
                fields
                    .iter()
                    .map(|field| format!("table.{}", field))
                    .collect::<Vec<_>>()
                    .join(", "),
                references
                    .fields
                    .iter()
                    .map(|field| format!("{}.{}", table_export_name(target_table), field))
                    .collect::<Vec<_>>()
                    .join(", ")
            );
            if let Some(on_delete) = &references.on_delete {
                expression.push_str(&format!(".onDelete(\"{}\")", on_delete));
            }
            if let Some(on_update) = &references.on_update {
                expression.push_str(&format!(".onUpdate(\"{}\")", on_update));
            }
            Ok(Some(expression))
        }
        "primaryKey" => {
            let fields = constraint
                .fields
                .as_ref()
                .ok_or_else(|| message("Primary key fields are required."))?;
            let columns = fields
                .iter()
                .map(|field| format!("table.{}", field))
                .collect::<Vec<_>>()
                .join(", ");
            if let Some(name) = &constraint.name {
                Ok(Some(format!(
                    "primaryKey({{ name: \"{}\", columns: [{}] }})",
                    name, columns
                )))
            } else {
                Ok(Some(format!("primaryKey({{ columns: [{}] }})", columns)))
            }
        }
        _ => Ok(None),
    }
}

fn render_table(entity: &Entity, tables_by_entity: &HashMap<&str, &str>) -> Result<String> {
    let table_factory =
        adapter_string(entity.adapters.as_ref(), "tableFactory").unwrap_or("pgTable");
    let export_name = table_export_name(&entity.table);
    let inline_foreign_keys = collect_inline_foreign_keys(entity);
    let mut lines = vec![
        format!("export const {} = {}(", export_name, table_factory),
        format!("  \"{}\",", entity.table),
        String::from("  {"),
    ];
    for field in &entity.fields {
        lines.extend(render_column(
            field,
            entity,
            &inline_foreign_keys,
            tables_by_entity,
        )?);
    }
    lines.push(String::from("  },"));

    let mut callback_items = Vec::new();
    let mut unique_signatures = HashSet::new();
    for index in &entity.indexes {
        callback_items.push(render_index(index)?);
        if index.unique {
            unique_signatures.insert(("unique".to_owned(), index.fields.clone()));
        }
    }

    for constraint in &entity.constraints {
        if constraint.kind == "unique" {
            let fields = constraint.fields.clone().unwrap_or_default();
            let signature = ("unique".to_owned(), fields);
            if unique_signatures.contains(&signature) {
                continue;
            }
            unique_signatures.insert(signature);
        }

        if let Some(rendered) = render_constraint(constraint, tables_by_entity)? {
            callback_items.push(rendered);
        }
    }

    if !callback_items.is_empty() {
        lines.push(String::from("  (table) => ["));
        for item in callback_items {
            lines.push(format!("    {},", item));
        }
        lines.push(String::from("  ],"));
    }

    lines.push(String::from(");"));
    Ok(lines.join("\n"))
}

fn render_relation(
    entity: &Entity,
    tables_by_entity: &HashMap<&str, &str>,
) -> Result<Option<String>> {
    if entity.relations.is_empty() {
        return Ok(None);
    }

    let table_export = table_export_name(&entity.table);
    let relation_export = relation_export_name(&entity.table);
    let mut relation_kinds = BTreeSet::new();
    for relation in &entity.relations {
        if matches!(relation.kind.as_str(), "belongsTo" | "hasOne") {
            relation_kinds.insert(String::from("one"));
        }
        if matches!(relation.kind.as_str(), "hasMany" | "manyToMany") {
            relation_kinds.insert(String::from("many"));
        }
    }

    let mut lines = vec![format!(
        "export const {} = relations({}, ({{ {} }}) => ({{",
        relation_export,
        table_export,
        relation_kinds.into_iter().collect::<Vec<_>>().join(", ")
    )];

    for relation in &entity.relations {
        let target_table_name = tables_by_entity
            .get(relation.target_entity.as_str())
            .ok_or_else(|| {
                message(format!(
                    "Unknown target entity '{}'.",
                    relation.target_entity
                ))
            })?;
        let target_table = table_export_name(target_table_name);

        match (relation.kind.as_str(), relation.ownership.as_str()) {
            ("belongsTo", "owner") | ("hasOne", "owner") => {
                let foreign_key = relation.foreign_key.as_ref().ok_or_else(|| {
                    message(format!(
                        "Relation '{}.{}' requires foreignKey.",
                        entity.name, relation.name
                    ))
                })?;
                let references = relation.references.as_ref().ok_or_else(|| {
                    message(format!(
                        "Relation '{}.{}' requires references.",
                        entity.name, relation.name
                    ))
                })?;
                lines.push(format!("  {}: one({}, {{", relation.name, target_table));
                lines.push(format!("    fields: [{}.{foreign_key}],", table_export));
                lines.push(format!("    references: [{}.{references}],", target_table));
                lines.push(String::from("  }),"));
            }
            ("hasOne", "inverse") => {
                lines.push(format!("  {}: one({}),", relation.name, target_table));
            }
            ("hasMany", _) => {
                lines.push(format!("  {}: many({}),", relation.name, target_table));
            }
            ("manyToMany", _) => {
                lines.push(format!(
                    "  // TODO: wire many-to-many relation '{}' through {}",
                    relation.name,
                    relation
                        .through_entity
                        .as_deref()
                        .unwrap_or("a junction table")
                ));
            }
            _ => {}
        }
    }

    lines.push(String::from("}));"));
    Ok(Some(lines.join("\n")))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::Map;

    use crate::model::{Computed, ConstraintReference, Relation, SourceSchemas};

    fn field(name: &str, field_type: &str) -> Field {
        Field {
            name: name.to_owned(),
            storage_name: snake_case(name),
            field_type: field_type.to_owned(),
            nullable: false,
            persisted: true,
            generated: String::from("none"),
            source_schemas: SourceSchemas::default(),
            enum_name: None,
            default: None,
            computed: None,
            length: None,
            precision: None,
            scale: None,
            primary_key: None,
            unique: None,
            adapters: None,
        }
    }

    #[test]
    fn render_column_type_variants() {
        let mut custom = field("metadata", "json");
        let mut adapter = Map::new();
        adapter.insert(
            String::from("columnFactory"),
            Value::String(String::from("jsonb")),
        );
        custom.adapters = Some(AdapterMap::from([(
            String::from(DRIZZLE_PG_TARGET),
            adapter,
        )]));
        assert_eq!("jsonb(\"metadata\")", render_column_type(&custom).unwrap());

        let varchar = field("title", "varchar");
        assert_eq!("varchar(\"title\")", render_column_type(&varchar).unwrap());

        let mut timestamp = field("createdAt", "timestamp");
        timestamp.storage_name = String::from("created_at");
        timestamp.precision = Some(3);
        assert_eq!(
            "timestamp(\"created_at\", { precision: 3, mode: \"date\" })",
            render_column_type(&timestamp).unwrap()
        );
    }

    #[test]
    fn render_constraint_variants() {
        let tables_by_entity = HashMap::from([("Thing", "things"), ("Other", "others")]);
        let unique = Constraint {
            kind: String::from("unique"),
            name: Some(String::from("things_name_key")),
            fields: Some(vec![String::from("name")]),
            references: None,
            expression: None,
            adapters: None,
        };
        assert_eq!(
            Some(String::from(
                "uniqueIndex(\"things_name_key\").on(table.name)"
            )),
            render_constraint(&unique, &tables_by_entity).unwrap()
        );

        let foreign_key = Constraint {
            kind: String::from("foreignKey"),
            name: Some(String::from("compound_fk")),
            fields: Some(vec![String::from("id"), String::from("slug")]),
            references: Some(ConstraintReference {
                entity: String::from("Other"),
                fields: vec![String::from("id"), String::from("slug")],
                on_delete: Some(String::from("cascade")),
                on_update: Some(String::from("restrict")),
            }),
            expression: None,
            adapters: None,
        };
        assert_eq!(
            Some(String::from(
                "foreignKey({ name: \"compound_fk\", columns: [table.id, table.slug], foreignColumns: [others.id, others.slug] }).onDelete(\"cascade\").onUpdate(\"restrict\")"
            )),
            render_constraint(&foreign_key, &tables_by_entity).unwrap()
        );
    }

    #[test]
    fn generate_drizzle_schema_supports_custom_factories() {
        let model = CanonicalModel {
            version: String::from("0.1"),
            adapters: None,
            outputs: None,
            enums: Vec::new(),
            entities: vec![Entity {
                name: String::from("Metric"),
                table: String::from("metrics"),
                source_schemas: SourceSchemas::default(),
                fields: vec![
                    Field {
                        primary_key: Some(true),
                        generated: String::from("database"),
                        field_type: String::from("uuid"),
                        ..field("id", "uuid")
                    },
                    Field {
                        generated: String::from("database"),
                        computed: Some(Computed {
                            expression: String::from("build_payload()"),
                            stored: true,
                            depends_on: None,
                        }),
                        adapters: Some(AdapterMap::from([(
                            String::from(DRIZZLE_PG_TARGET),
                            Map::from_iter([
                                (
                                    String::from("columnFactory"),
                                    Value::String(String::from("jsonb")),
                                ),
                                (
                                    String::from("imports"),
                                    Value::Object(Map::from_iter([
                                        (
                                            String::from("pgCore"),
                                            Value::Array(vec![Value::String(String::from(
                                                "jsonb",
                                            ))]),
                                        ),
                                        (
                                            String::from("orm"),
                                            Value::Array(vec![Value::String(String::from("sql"))]),
                                        ),
                                    ])),
                                ),
                            ]),
                        )])),
                        ..field("payload", "json")
                    },
                ],
                relations: vec![Relation {
                    name: String::from("things"),
                    kind: String::from("manyToMany"),
                    target_entity: String::from("Metric"),
                    ownership: String::from("inverse"),
                    foreign_key: None,
                    references: None,
                    through_entity: Some(String::from("MetricThing")),
                    adapters: None,
                }],
                indexes: Vec::new(),
                constraints: Vec::new(),
                adapters: Some(AdapterMap::from([(
                    String::from(DRIZZLE_PG_TARGET),
                    Map::from_iter([
                        (
                            String::from("tableFactory"),
                            Value::String(String::from("customTable")),
                        ),
                        (
                            String::from("imports"),
                            Value::Object(Map::from_iter([
                                (
                                    String::from("pgCore"),
                                    Value::Array(vec![Value::String(String::from("customTable"))]),
                                ),
                                (
                                    String::from("orm"),
                                    Value::Array(vec![Value::String(String::from(
                                        "customOrmHelper",
                                    ))]),
                                ),
                            ])),
                        ),
                    ]),
                )])),
            }],
        };

        let generated = generate_drizzle_schema(&model).unwrap();
        assert!(
            generated.contains("import { customOrmHelper, relations, sql } from \"drizzle-orm\";")
        );
        assert!(generated.contains(
            "import { customTable, jsonb, pgTable, uuid } from \"drizzle-orm/pg-core\";"
        ));
        assert!(generated.contains("export const metrics = customTable("));
        assert!(generated.contains(
            "payload: jsonb(\"payload\").notNull().generatedAlwaysAs(sql`build_payload()`),"
        ));
        assert!(generated.contains("TODO: wire many-to-many relation 'things' through MetricThing"));
    }
}
