use std::collections::{BTreeMap, HashMap};

use serde_json::Value;

use crate::adapter::{BackendAdapter, GeneratedFile};
use crate::error::{message, Result};
use crate::model::{
    AdapterMap, CanonicalEnum, CanonicalModel, Constraint, Entity, Field, JsonObject, Relation,
};
use crate::utils::{snake_case, to_json_literal, upper_camel_case};

pub const SEAORM_RUST_TARGET: &str = "seaorm-rust";
pub static SEAORM_RUST_ADAPTER: SeaOrmRustAdapter = SeaOrmRustAdapter;

pub struct SeaOrmRustAdapter;

fn seaorm_definition_config<'a>(adapters: Option<&'a AdapterMap>) -> Option<&'a JsonObject> {
    adapters.and_then(|adapters| adapters.get(SEAORM_RUST_TARGET))
}

fn string_value<'a>(config: Option<&'a JsonObject>, key: &str) -> Option<&'a str> {
    config?.get(key).and_then(Value::as_str)
}

fn bool_value(config: Option<&JsonObject>, key: &str) -> Option<bool> {
    config?.get(key).and_then(Value::as_bool)
}

fn string_array(config: Option<&JsonObject>, key: &str) -> Result<Vec<String>> {
    let Some(value) = config.and_then(|config| config.get(key)) else {
        return Ok(Vec::new());
    };
    let Some(items) = value.as_array() else {
        return Err(message(format!(
            "{} must contain only non-empty strings.",
            key
        )));
    };
    let mut lines = Vec::new();
    for item in items {
        let Some(text) = item.as_str() else {
            return Err(message(format!(
                "{} must contain only non-empty strings.",
                key
            )));
        };
        if text.trim().is_empty() {
            return Err(message(format!(
                "{} must contain only non-empty strings.",
                key
            )));
        }
        lines.push(text.to_owned());
    }
    Ok(lines)
}

fn module_name(entity: &Entity) -> String {
    string_value(
        seaorm_definition_config(entity.adapters.as_ref()),
        "moduleName",
    )
    .map(ToOwned::to_owned)
    .unwrap_or_else(|| snake_case(&entity.name))
}

fn persisted_fields(entity: &Entity) -> Vec<&Field> {
    entity
        .fields
        .iter()
        .filter(|field| field.persisted)
        .collect()
}

fn raw_rust_type(field: &Field) -> Result<String> {
    let adapter_config = seaorm_definition_config(field.adapters.as_ref());
    if let Some(rust_type) = string_value(adapter_config, "rustType") {
        return Ok(rust_type.to_owned());
    }
    if let Some(enum_name) = &field.enum_name {
        return Ok(upper_camel_case(enum_name));
    }
    match field.field_type.as_str() {
        "uuid" => Ok(String::from("Uuid")),
        "varchar" | "text" => Ok(String::from("String")),
        "integer" => Ok(String::from("i32")),
        "boolean" => Ok(String::from("bool")),
        "timestamp" => Ok(String::from("DateTime")),
        "timestamptz" => Ok(String::from("DateTimeWithTimeZone")),
        other => Err(message(format!(
            "Unsupported SeaORM Rust type mapping for canonical field type '{}'.",
            other
        ))),
    }
}

fn seaorm_rust_type(field: &Field) -> Result<String> {
    let rust_type = raw_rust_type(field)?;
    if field.nullable {
        Ok(format!("Option<{}>", rust_type))
    } else {
        Ok(rust_type)
    }
}

fn seaorm_column_type(field: &Field) -> Result<String> {
    let adapter_config = seaorm_definition_config(field.adapters.as_ref());
    if let Some(column_type) = string_value(adapter_config, "columnType") {
        return Ok(column_type.to_owned());
    }

    match field.field_type.as_str() {
        "uuid" => Ok(String::from("Uuid")),
        "varchar" => Ok(match field.length {
            Some(length) => format!("String(StringLen::N({}))", length),
            None => String::from("String(StringLen::None)"),
        }),
        "text" => Ok(String::from("Text")),
        "integer" => Ok(String::from("Integer")),
        "boolean" => Ok(String::from("Boolean")),
        "timestamp" => Ok(String::from("Timestamp")),
        "timestamptz" => Ok(String::from("TimestampWithTimeZone")),
        other => Err(message(format!(
            "Unsupported SeaORM column type mapping for canonical field type '{}'.",
            other
        ))),
    }
}

fn render_attribute_lines(values: &[String], context: &str) -> Result<Vec<String>> {
    let mut lines = Vec::new();
    for value in values {
        if value.trim().is_empty() {
            return Err(message(format!(
                "{} must contain only non-empty strings.",
                context
            )));
        }
        lines.push(value.clone());
    }
    Ok(lines)
}

fn field_rust_name(field: &Field) -> String {
    field.storage_name.clone()
}

fn primary_key_fields(entity: &Entity) -> Vec<String> {
    let mut names = entity
        .fields
        .iter()
        .filter(|field| field.primary_key.unwrap_or(false))
        .map(|field| field.name.clone())
        .collect::<Vec<_>>();
    for constraint in &entity.constraints {
        if constraint.kind == "primaryKey" {
            if let Some(fields) = &constraint.fields {
                for field_name in fields {
                    if !names.contains(field_name) {
                        names.push(field_name.clone());
                    }
                }
            }
        }
    }
    names
}

fn column_variant_name(field_name: &str) -> String {
    upper_camel_case(&snake_case(field_name))
}

fn enum_variant_name(value: &str) -> String {
    let mut parts = Vec::new();
    let mut current = String::new();
    for ch in value.chars() {
        if ch.is_ascii_alphanumeric() {
            current.push(ch);
        } else if !current.is_empty() {
            parts.push(current.clone());
            current.clear();
        }
    }
    if !current.is_empty() {
        parts.push(current);
    }
    if parts.is_empty() {
        return String::from("Value");
    }
    let name = upper_camel_case(&parts.join(" "));
    if name.chars().next().is_some_and(|ch| ch.is_ascii_digit()) {
        format!("Value{}", name)
    } else {
        name
    }
}

fn active_enums_for_entity<'a>(
    entity: &'a Entity,
    enums_by_name: &'a HashMap<&'a str, &'a CanonicalEnum>,
) -> Result<Vec<(&'a CanonicalEnum, String)>> {
    let mut db_type_by_enum: BTreeMap<String, String> = BTreeMap::new();
    for field in persisted_fields(entity) {
        let Some(enum_name) = field.enum_name.as_deref() else {
            continue;
        };
        if string_value(
            seaorm_definition_config(field.adapters.as_ref()),
            "rustType",
        )
        .is_some()
        {
            continue;
        }
        if !enums_by_name.contains_key(enum_name) {
            return Err(message(format!(
                "Entity '{}' references unknown enum '{}'.",
                entity.name, enum_name
            )));
        }
        let db_type = seaorm_column_type(field)?;
        if let Some(previous) = db_type_by_enum.get(enum_name) {
            if previous != &db_type {
                return Err(message(format!(
                    "Entity '{}' uses enum '{}' with incompatible SeaORM db types: '{}' and '{}'.",
                    entity.name, enum_name, previous, db_type
                )));
            }
        }
        db_type_by_enum.insert(enum_name.to_owned(), db_type);
    }

    db_type_by_enum
        .into_iter()
        .map(|(enum_name, db_type)| {
            let enum_definition = enums_by_name.get(enum_name.as_str()).ok_or_else(|| {
                message(format!(
                    "Entity '{}' references unknown enum '{}'.",
                    entity.name, enum_name
                ))
            })?;
            Ok((*enum_definition, db_type))
        })
        .collect()
}

fn render_active_enum(enum_definition: &CanonicalEnum, db_type: &str) -> Result<String> {
    let values = seaorm_string_enum_values(enum_definition)?;
    let mut lines = vec![
        String::from("#[derive(Copy, Clone, Debug, PartialEq, Eq, EnumIter, DeriveActiveEnum)]"),
        format!(
            "#[sea_orm(rs_type = \"String\", db_type = \"{}\", enum_name = \"{}\")]",
            db_type,
            snake_case(&enum_definition.name)
        ),
        format!("pub enum {} {{", upper_camel_case(&enum_definition.name)),
    ];
    for value in values {
        let string_literal = serde_json::to_string(value).expect("json string literal");
        lines.push(format!("    #[sea_orm(string_value = {})]", string_literal));
        lines.push(format!("    {},", enum_variant_name(value)));
    }
    lines.push(String::from("}"));
    Ok(lines.join("\n"))
}

fn seaorm_string_enum_values<'a>(enum_definition: &'a CanonicalEnum) -> Result<Vec<&'a str>> {
    let mut values = Vec::new();
    for value in &enum_definition.values {
        let Some(text) = value.as_str() else {
            return Err(message(format!(
                "SeaORM enum '{}' requires string values, but found {}.",
                enum_definition.name, value
            )));
        };
        values.push(text);
    }
    Ok(values)
}

fn field_comment_lines(field: &Field) -> Vec<String> {
    let mut lines = Vec::new();
    if let Some(default) = &field.default {
        lines.push(format!(
            "// OpenModels: default = {}",
            to_json_literal(default)
        ));
    }
    if field.generated != "none" {
        lines.push(format!("// OpenModels: generated = {}", field.generated));
    }
    if let Some(computed) = &field.computed {
        lines.push(format!("// OpenModels: computed = {}", computed.expression));
    }
    lines
}

fn field_attribute_lines(field: &Field) -> Result<Vec<String>> {
    let adapter_config = seaorm_definition_config(field.adapters.as_ref());
    let context = format!(
        "Field '{}' adapters.seaorm-rust.extraAttributes",
        field.name
    );
    let mut attributes =
        render_attribute_lines(&string_array(adapter_config, "extraAttributes")?, &context)?;

    let mut tokens = Vec::new();
    if field.primary_key.unwrap_or(false) {
        tokens.push(String::from("primary_key"));
        let auto_increment = field.field_type == "integer" && field.generated == "database";
        tokens.push(format!(
            "auto_increment = {}",
            if auto_increment { "true" } else { "false" }
        ));
    }
    tokens.push(format!("column_type = \"{}\"", seaorm_column_type(field)?));
    attributes.push(format!("#[sea_orm({})]", tokens.join(", ")));
    Ok(attributes)
}

fn render_model(entity: &Entity) -> Result<String> {
    let primary_key_fields = primary_key_fields(entity);
    if primary_key_fields.len() != 1 {
        return Err(message(format!(
            "SeaORM Phase 2 requires exactly one primary key field for entity '{}'.",
            entity.name
        )));
    }

    let persisted_fields = persisted_fields(entity);
    if persisted_fields.is_empty() {
        return Err(message(format!(
            "SeaORM entity '{}' has no persisted fields to generate.",
            entity.name
        )));
    }

    let entity_config = seaorm_definition_config(entity.adapters.as_ref());
    let mut derive_items = vec![
        String::from("Clone"),
        String::from("Debug"),
        String::from("PartialEq"),
        String::from("Eq"),
        String::from("DeriveEntityModel"),
    ];
    for derive_item in string_array(entity_config, "extraDerives")? {
        if !derive_items.contains(&derive_item) {
            derive_items.push(derive_item);
        }
    }

    let entity_context = format!(
        "Entity '{}' adapters.seaorm-rust.extraAttributes",
        entity.name
    );
    let mut lines = vec![format!("#[derive({})]", derive_items.join(", "))];
    lines.extend(render_attribute_lines(
        &string_array(entity_config, "extraAttributes")?,
        &entity_context,
    )?);
    lines.push(format!("#[sea_orm(table_name = \"{}\")]", entity.table));
    lines.push(String::from("pub struct Model {"));
    for field in persisted_fields {
        for comment in field_comment_lines(field) {
            lines.push(format!("    {}", comment));
        }
        for attribute in field_attribute_lines(field)? {
            lines.push(format!("    {}", attribute));
        }
        lines.push(format!(
            "    pub {}: {},",
            field_rust_name(field),
            seaorm_rust_type(field)?
        ));
    }
    lines.push(String::from("}"));
    Ok(lines.join("\n"))
}

fn relation_variant_name(relation: &Relation) -> Result<String> {
    let relation_config = seaorm_definition_config(relation.adapters.as_ref());
    if let Some(variant_name) = string_value(relation_config, "variantName") {
        if variant_name.trim().is_empty() {
            return Err(message(format!(
                "Relation '{}' adapters.seaorm-rust.variantName must be a non-empty string.",
                relation.name
            )));
        }
        return Ok(variant_name.to_owned());
    }
    Ok(upper_camel_case(&snake_case(&relation.name)))
}

fn related_entity_path(entity_by_name: &HashMap<&str, &Entity>, entity_name: &str) -> String {
    format!(
        "super::{}::Entity",
        module_name(entity_by_name[entity_name])
    )
}

fn related_column_path(
    entity_by_name: &HashMap<&str, &Entity>,
    entity_name: &str,
    field_name: &str,
) -> String {
    format!(
        "super::{}::Column::{}",
        module_name(entity_by_name[entity_name]),
        column_variant_name(field_name)
    )
}

fn seaorm_reference_action(value: &str) -> Result<&'static str> {
    match value {
        "noAction" => Ok("NoAction"),
        "restrict" => Ok("Restrict"),
        "cascade" => Ok("Cascade"),
        "setNull" => Ok("SetNull"),
        "setDefault" => Ok("SetDefault"),
        other => Err(message(format!(
            "Unsupported SeaORM foreign key action '{}'.",
            other
        ))),
    }
}

fn matching_foreign_key_constraint<'a>(
    entity: &'a Entity,
    relation: &Relation,
) -> Option<&'a Constraint> {
    if relation.kind != "belongsTo" {
        return None;
    }
    let foreign_key = relation.foreign_key.as_ref()?;
    let reference_field = relation.references.as_ref()?;

    entity.constraints.iter().find(|constraint| {
        constraint.kind == "foreignKey"
            && constraint.fields.as_ref() == Some(&vec![foreign_key.clone()])
            && constraint.references.as_ref().is_some_and(|references| {
                references.entity == relation.target_entity
                    && references.fields == vec![reference_field.clone()]
            })
    })
}

fn relation_attribute_lines(
    relation: &Relation,
    entity: &Entity,
    entity_by_name: &HashMap<&str, &Entity>,
) -> Result<Vec<String>> {
    let relation_config = seaorm_definition_config(relation.adapters.as_ref());
    let context = format!(
        "Relation '{}.{}' adapters.seaorm-rust.extraAttributes",
        entity.name, relation.name
    );
    let mut attributes =
        render_attribute_lines(&string_array(relation_config, "extraAttributes")?, &context)?;

    let target_path = related_entity_path(entity_by_name, &relation.target_entity);
    let mut tokens = Vec::new();
    match relation.kind.as_str() {
        "belongsTo" => {
            let foreign_key = relation.foreign_key.as_ref().ok_or_else(|| {
                message(format!(
                    "SeaORM belongsTo relation '{}.{}' requires foreignKey and references.",
                    entity.name, relation.name
                ))
            })?;
            let reference_field = relation.references.as_ref().ok_or_else(|| {
                message(format!(
                    "SeaORM belongsTo relation '{}.{}' requires foreignKey and references.",
                    entity.name, relation.name
                ))
            })?;
            tokens.push(format!("belongs_to = \"{}\"", target_path));
            tokens.push(format!(
                "from = \"Column::{}\"",
                column_variant_name(foreign_key)
            ));
            tokens.push(format!(
                "to = \"{}\"",
                related_column_path(entity_by_name, &relation.target_entity, reference_field)
            ));
            if let Some(constraint) = matching_foreign_key_constraint(entity, relation) {
                if let Some(references) = &constraint.references {
                    if let Some(on_update) = &references.on_update {
                        tokens.push(format!(
                            "on_update = \"{}\"",
                            seaorm_reference_action(on_update)?
                        ));
                    }
                    if let Some(on_delete) = &references.on_delete {
                        tokens.push(format!(
                            "on_delete = \"{}\"",
                            seaorm_reference_action(on_delete)?
                        ));
                    }
                }
            }
        }
        "hasMany" => {
            tokens.push(format!("has_many = \"{}\"", target_path));
        }
        "hasOne" => {
            tokens.push(format!("has_one = \"{}\"", target_path));
        }
        other => {
            return Err(message(format!(
                "SeaORM Phase 3 does not support relation kind '{}' on '{}.{}'.",
                other, entity.name, relation.name
            )));
        }
    }

    attributes.push(format!("#[sea_orm({})]", tokens.join(", ")));
    Ok(attributes)
}

fn render_relation_enum(
    entity: &Entity,
    entity_by_name: &HashMap<&str, &Entity>,
) -> Result<String> {
    let mut lines = vec![
        String::from("#[derive(Copy, Clone, Debug, EnumIter, DeriveRelation)]"),
        String::from("pub enum Relation {"),
    ];
    for relation in &entity.relations {
        for attribute in relation_attribute_lines(relation, entity, entity_by_name)? {
            lines.push(format!("    {}", attribute));
        }
        lines.push(format!("    {},", relation_variant_name(relation)?));
    }
    lines.push(String::from("}"));
    Ok(lines.join("\n"))
}

fn related_impl_lines(
    entity: &Entity,
    entity_by_name: &HashMap<&str, &Entity>,
) -> Result<Vec<String>> {
    let mut grouped: BTreeMap<String, Vec<&Relation>> = BTreeMap::new();
    for relation in &entity.relations {
        let relation_config = seaorm_definition_config(relation.adapters.as_ref());
        let skip_related_impl = bool_value(relation_config, "skipRelatedImpl").unwrap_or(false);
        if relation_config
            .and_then(|config| config.get("skipRelatedImpl"))
            .is_some()
            && !relation_config
                .and_then(|config| config.get("skipRelatedImpl"))
                .is_some_and(Value::is_boolean)
        {
            return Err(message(format!(
                "Relation '{}.{}' adapters.seaorm-rust.skipRelatedImpl must be boolean.",
                entity.name, relation.name
            )));
        }
        if skip_related_impl {
            continue;
        }
        grouped
            .entry(relation.target_entity.clone())
            .or_default()
            .push(relation);
    }

    for (target_entity, relations) in &grouped {
        if relations.len() > 1 {
            let relation_names = relations
                .iter()
                .map(|relation| relation.name.as_str())
                .collect::<Vec<_>>()
                .join(", ");
            return Err(message(format!(
                "Entity '{}' has multiple SeaORM relations to '{}' ({}). Set adapters.seaorm-rust.skipRelatedImpl on all but one relation.",
                entity.name, target_entity, relation_names
            )));
        }
    }

    let mut lines = Vec::new();
    for (target_entity, relations) in grouped {
        let relation = relations[0];
        lines.extend([
            format!(
                "impl Related<{}> for Entity {{",
                related_entity_path(entity_by_name, &target_entity)
            ),
            String::from("    fn to() -> RelationDef {"),
            format!(
                "        Relation::{}.def()",
                relation_variant_name(relation)?
            ),
            String::from("    }"),
            String::from("}"),
        ]);
    }
    Ok(lines)
}

fn constraint_comment_lines(entity: &Entity) -> Vec<String> {
    let constraints = entity
        .constraints
        .iter()
        .filter(|constraint| constraint.kind != "primaryKey" && constraint.kind != "foreignKey")
        .collect::<Vec<_>>();
    if entity.indexes.is_empty() && constraints.is_empty() {
        return Vec::new();
    }

    let mut lines = vec![String::from(
        "// OpenModels Phase 3 does not emit indexes or non-foreign-key constraints yet.",
    )];
    if !entity.indexes.is_empty() {
        lines.push(String::from("// Planned indexes:"));
        for index in &entity.indexes {
            let uniqueness = if index.unique { " unique" } else { "" };
            lines.push(format!(
                "// - {}:{} [{}]",
                index.name.as_deref().unwrap_or("<anonymous>"),
                uniqueness,
                index.fields.join(", ")
            ));
        }
    }
    if !constraints.is_empty() {
        lines.push(String::from("// Planned constraints:"));
        for constraint in constraints {
            let mut detail = format!(
                "{}: {}",
                constraint.name.as_deref().unwrap_or("<anonymous>"),
                constraint.kind
            );
            if let Some(fields) = &constraint.fields {
                detail.push_str(&format!(" [{}]", fields.join(", ")));
            }
            if constraint.kind == "check" {
                if let Some(expression) = &constraint.expression {
                    detail.push_str(&format!(" ({})", expression));
                }
            }
            lines.push(format!("// - {}", detail));
        }
    }
    lines
}

fn render_entity_file(
    entity: &Entity,
    module_root: &str,
    enums_by_name: &HashMap<&str, &CanonicalEnum>,
    entity_by_name: &HashMap<&str, &Entity>,
) -> Result<GeneratedFile> {
    let mut lines = vec![String::from("use sea_orm::entity::prelude::*;")];

    let active_enums = active_enums_for_entity(entity, enums_by_name)?;
    if !active_enums.is_empty() {
        lines.push(String::new());
        for (index, (enum_definition, db_type)) in active_enums.iter().enumerate() {
            if index > 0 {
                lines.push(String::new());
            }
            lines.push(render_active_enum(enum_definition, db_type)?);
        }
    }

    lines.push(String::new());
    lines.push(render_model(entity)?);
    lines.push(String::new());
    lines.push(render_relation_enum(entity, entity_by_name)?);
    let related_impls = related_impl_lines(entity, entity_by_name)?;
    if !related_impls.is_empty() {
        lines.push(String::new());
        lines.extend(related_impls);
    }
    let constraint_comments = constraint_comment_lines(entity);
    if !constraint_comments.is_empty() {
        lines.push(String::new());
        lines.extend(constraint_comments);
    }

    lines.push(String::new());
    lines.push(String::from("impl ActiveModelBehavior for ActiveModel {}"));

    Ok(GeneratedFile {
        path: format!("{}/{}.rs", module_root, module_name(entity)),
        content: lines.join("\n") + "\n",
    })
}

fn mod_file(entities: &[Entity], module_root: &str) -> GeneratedFile {
    let mut lines = vec![
        String::from("//! Generated by OpenModels for seaorm-rust."),
        String::new(),
        String::from("pub mod prelude;"),
    ];
    let mut module_names = entities.iter().map(module_name).collect::<Vec<_>>();
    module_names.sort();
    for module in module_names {
        lines.push(format!("pub mod {};", module));
    }
    GeneratedFile {
        path: format!("{}/mod.rs", module_root),
        content: lines.join("\n") + "\n",
    }
}

fn prelude_file(entities: &[Entity], module_root: &str) -> GeneratedFile {
    let mut ordered = entities.iter().collect::<Vec<_>>();
    ordered.sort_by(|left, right| left.name.cmp(&right.name));
    let mut lines = vec![
        String::from("//! Public SeaORM entity exports generated by OpenModels."),
        String::new(),
    ];
    for entity in ordered {
        lines.push(format!(
            "pub use super::{}::Entity as {};",
            module_name(entity),
            upper_camel_case(&entity.name)
        ));
    }
    GeneratedFile {
        path: format!("{}/prelude.rs", module_root),
        content: lines.join("\n") + "\n",
    }
}

impl BackendAdapter for SeaOrmRustAdapter {
    fn key(&self) -> &'static str {
        SEAORM_RUST_TARGET
    }

    fn description(&self) -> &'static str {
        "SeaORM Rust entity generator"
    }

    fn default_filename(&self) -> &'static str {
        "entity/mod.rs"
    }

    fn generate_files(
        &self,
        canonical_model: &CanonicalModel,
        filename: Option<&str>,
        options: Option<&JsonObject>,
    ) -> Result<Vec<GeneratedFile>> {
        if filename.is_some() {
            return Err(message(
                "The seaorm-rust adapter uses a fixed multi-file layout and does not accept filename overrides.",
            ));
        }

        let module_root = options
            .and_then(|options| options.get("moduleRoot"))
            .and_then(Value::as_str)
            .unwrap_or("entity");
        if module_root.is_empty() {
            return Err(message(
                "The seaorm-rust adapter requires a non-empty string for options.moduleRoot.",
            ));
        }

        let entity_by_name = canonical_model
            .entities
            .iter()
            .map(|entity| (entity.name.as_str(), entity))
            .collect::<HashMap<_, _>>();
        let enums_by_name = canonical_model
            .enums
            .iter()
            .map(|enum_definition| (enum_definition.name.as_str(), enum_definition))
            .collect::<HashMap<_, _>>();

        let mut files = vec![
            mod_file(&canonical_model.entities, module_root),
            prelude_file(&canonical_model.entities, module_root),
        ];
        let mut ordered_entities = canonical_model.entities.iter().collect::<Vec<_>>();
        ordered_entities.sort_by_key(|entity| module_name(entity));
        for entity in ordered_entities {
            files.push(render_entity_file(
                entity,
                module_root,
                &enums_by_name,
                &entity_by_name,
            )?);
        }
        Ok(files)
    }
}
