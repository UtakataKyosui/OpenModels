use std::collections::{BTreeMap, BTreeSet};

use serde::Serialize;
use serde_json::{Map, Value};

use crate::model::{CanonicalModel, Constraint, Entity, Field, Index};

#[derive(Debug, Clone, Serialize, PartialEq)]
pub struct MigrationPlan {
    #[serde(rename = "formatVersion")]
    pub format_version: String,
    #[serde(rename = "fromModelVersion")]
    pub from_model_version: String,
    #[serde(rename = "toModelVersion")]
    pub to_model_version: String,
    pub changes: Vec<Value>,
    pub warnings: Vec<MigrationWarning>,
    pub summary: MigrationSummary,
}

#[derive(Debug, Clone, Serialize, PartialEq)]
pub struct MigrationWarning {
    pub code: String,
    pub level: String,
    pub entity: String,
    #[serde(rename = "changeKind")]
    pub change_kind: String,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub field: Option<String>,
}

#[derive(Debug, Clone, Serialize, PartialEq)]
pub struct MigrationSummary {
    #[serde(rename = "totalChanges")]
    pub total_changes: usize,
    #[serde(rename = "destructiveChanges")]
    pub destructive_changes: usize,
    pub warnings: usize,
}

pub fn plan_migration(
    before_model: &CanonicalModel,
    after_model: &CanonicalModel,
) -> MigrationPlan {
    let mut changes = Vec::new();
    let mut warnings = Vec::new();

    let before_entities = entity_map(before_model);
    let after_entities = entity_map(after_model);

    for entity_name in sorted_union(before_entities.keys(), after_entities.keys()) {
        let before_entity = before_entities.get(entity_name.as_str()).copied();
        let after_entity = after_entities.get(entity_name.as_str()).copied();

        if before_entity.is_none() && after_entity.is_some() {
            let after_entity = after_entity.expect("after entity");
            changes.push(create_table_change(after_entity));
            continue;
        }

        if before_entity.is_some() && after_entity.is_none() {
            let before_entity = before_entity.expect("before entity");
            changes.push(drop_table_change(&entity_name, before_entity));
            warnings.push(warning(
                "drop-table",
                &format!("Table '{}' would be dropped.", before_entity.table),
                &entity_name,
                None,
                "dropTable",
            ));
            continue;
        }

        let before_entity = before_entity.expect("before entity");
        let after_entity = after_entity.expect("after entity");

        if before_entity.table != after_entity.table {
            changes.push(rename_table_change(
                &entity_name,
                &before_entity.table,
                &after_entity.table,
            ));
            warnings.push(warning(
                "rename-table",
                &format!(
                    "Entity '{}' changes table name from '{}' to '{}'.",
                    entity_name, before_entity.table, after_entity.table
                ),
                &entity_name,
                None,
                "renameTable",
            ));
        }

        let before_fields = field_map(before_entity);
        let after_fields = field_map(after_entity);
        for field_name in sorted_union(before_fields.keys(), after_fields.keys()) {
            let before_field = before_fields.get(field_name.as_str()).copied();
            let after_field = after_fields.get(field_name.as_str()).copied();

            if before_field.is_none() && after_field.is_some() {
                let after_field = after_field.expect("after field");
                changes.push(add_column_change(&entity_name, &field_name, after_field));
                if column_requires_backfill(after_field) {
                    warnings.push(warning(
                        "add-required-column-without-default",
                        &format!(
                            "Column '{}.{}' is added as NOT NULL without a default or generated value.",
                            entity_name, field_name
                        ),
                        &entity_name,
                        Some(field_name.clone()),
                        "addColumn",
                    ));
                }
                continue;
            }

            if before_field.is_some() && after_field.is_none() {
                let before_field = before_field.expect("before field");
                changes.push(drop_column_change(&entity_name, &field_name, before_field));
                warnings.push(warning(
                    "drop-column",
                    &format!("Column '{}.{}' would be dropped.", entity_name, field_name),
                    &entity_name,
                    Some(field_name.clone()),
                    "dropColumn",
                ));
                continue;
            }

            let before_field = before_field.expect("before field");
            let after_field = after_field.expect("after field");
            let before_signature = field_signature(before_field);
            let after_signature = field_signature(after_field);
            let attribute_changes = compare_signatures(&before_signature, &after_signature);
            if attribute_changes.is_empty() {
                continue;
            }

            let destructive = is_destructive_column_change(&attribute_changes);
            changes.push(alter_column_change(
                &entity_name,
                &field_name,
                attribute_changes.clone(),
                destructive,
            ));

            if attribute_changes.contains_key("type") {
                warnings.push(warning(
                    "change-column-type",
                    &format!("Column '{}.{}' changes type.", entity_name, field_name),
                    &entity_name,
                    Some(field_name.clone()),
                    "alterColumn",
                ));
            }
            if attribute_changes.contains_key("storageName") {
                warnings.push(warning(
                    "rename-column",
                    &format!(
                        "Column '{}.{}' changes storage name.",
                        entity_name, field_name
                    ),
                    &entity_name,
                    Some(field_name.clone()),
                    "alterColumn",
                ));
            }
            if tightened_nullability(&attribute_changes) {
                warnings.push(warning(
                    "tighten-nullability",
                    &format!("Column '{}.{}' becomes NOT NULL.", entity_name, field_name),
                    &entity_name,
                    Some(field_name.clone()),
                    "alterColumn",
                ));
            }
            if shrinks_length(&attribute_changes) {
                warnings.push(warning(
                    "shrink-column-length",
                    &format!(
                        "Column '{}.{}' reduces max length.",
                        entity_name, field_name
                    ),
                    &entity_name,
                    Some(field_name.clone()),
                    "alterColumn",
                ));
            }
        }

        let before_indexes = index_map(before_entity);
        let after_indexes = index_map(after_entity);
        for index_key in sorted_union(before_indexes.keys(), after_indexes.keys()) {
            let before_index = before_indexes.get(index_key.as_str()).copied();
            let after_index = after_indexes.get(index_key.as_str()).copied();
            let index_name = (after_index.or(before_index))
                .and_then(|index| index.name.clone())
                .unwrap_or_else(|| index_key.clone());

            if before_index.is_none() && after_index.is_some() {
                let after_index = after_index.expect("after index");
                changes.push(add_index_change(&entity_name, &index_name, after_index));
                continue;
            }
            if before_index.is_some() && after_index.is_none() {
                let before_index = before_index.expect("before index");
                changes.push(drop_index_change(&entity_name, &index_name, before_index));
                continue;
            }

            let before_index = before_index.expect("before index");
            let after_index = after_index.expect("after index");
            let before_signature = index_signature(before_index);
            let after_signature = index_signature(after_index);
            let index_changes = compare_signatures(&before_signature, &after_signature);
            if !index_changes.is_empty() {
                changes.push(alter_index_change(&entity_name, &index_name, index_changes));
            }
        }

        let before_constraints = constraint_map(before_entity);
        let after_constraints = constraint_map(after_entity);
        for constraint_key in sorted_union(before_constraints.keys(), after_constraints.keys()) {
            let before_constraint = before_constraints.get(constraint_key.as_str()).copied();
            let after_constraint = after_constraints.get(constraint_key.as_str()).copied();
            let constraint_name = (after_constraint.or(before_constraint))
                .and_then(|constraint| constraint.name.clone())
                .unwrap_or_else(|| constraint_key.clone());

            if before_constraint.is_none() && after_constraint.is_some() {
                let after_constraint = after_constraint.expect("after constraint");
                changes.push(add_constraint_change(
                    &entity_name,
                    &constraint_name,
                    after_constraint,
                ));
                continue;
            }
            if before_constraint.is_some() && after_constraint.is_none() {
                let before_constraint = before_constraint.expect("before constraint");
                changes.push(drop_constraint_change(
                    &entity_name,
                    &constraint_name,
                    before_constraint,
                ));
                continue;
            }

            let before_constraint = before_constraint.expect("before constraint");
            let after_constraint = after_constraint.expect("after constraint");
            let before_signature = constraint_signature(before_constraint);
            let after_signature = constraint_signature(after_constraint);
            let constraint_changes = compare_signatures(&before_signature, &after_signature);
            if !constraint_changes.is_empty() {
                changes.push(alter_constraint_change(
                    &entity_name,
                    &constraint_name,
                    constraint_changes,
                ));
            }
        }
    }

    let destructive_changes = changes
        .iter()
        .filter(|change| {
            change
                .get("destructive")
                .and_then(Value::as_bool)
                .unwrap_or(false)
        })
        .count();

    let total_changes = changes.len();
    let warning_count = warnings.len();

    MigrationPlan {
        format_version: String::from("0.1"),
        from_model_version: before_model.version.clone(),
        to_model_version: after_model.version.clone(),
        changes,
        warnings,
        summary: MigrationSummary {
            total_changes,
            destructive_changes,
            warnings: warning_count,
        },
    }
}

fn entity_map(model: &CanonicalModel) -> BTreeMap<String, &Entity> {
    model
        .entities
        .iter()
        .map(|entity| (entity.name.clone(), entity))
        .collect()
}

fn field_map(entity: &Entity) -> BTreeMap<String, &Field> {
    entity
        .fields
        .iter()
        .map(|field| (field.name.clone(), field))
        .collect()
}

fn index_map(entity: &Entity) -> BTreeMap<String, &Index> {
    entity
        .indexes
        .iter()
        .map(|index| (index_key(index), index))
        .collect()
}

fn constraint_map(entity: &Entity) -> BTreeMap<String, &Constraint> {
    entity
        .constraints
        .iter()
        .map(|constraint| (constraint_key(constraint), constraint))
        .collect()
}

fn index_key(index: &Index) -> String {
    if let Some(name) = &index.name {
        return format!("name:{name}");
    }
    let unique = if index.unique { "unique" } else { "plain" };
    let fields = index.fields.join(",");
    format!("anon:{unique}:{fields}")
}

fn constraint_key(constraint: &Constraint) -> String {
    if let Some(name) = &constraint.name {
        return format!("name:{name}");
    }
    let kind = &constraint.kind;
    let fields = constraint.fields.clone().unwrap_or_default().join(",");
    let expression = constraint.expression.clone().unwrap_or_default();
    let references = constraint.references.as_ref();
    let target = references
        .map(|value| value.entity.clone())
        .unwrap_or_default();
    let target_fields = references
        .map(|value| value.fields.join(","))
        .unwrap_or_default();
    format!("anon:{kind}:{fields}:{target}:{target_fields}:{expression}")
}

fn field_signature(field: &Field) -> Map<String, Value> {
    let mut signature = Map::new();
    signature.insert(
        String::from("storageName"),
        Value::String(field.storage_name.clone()),
    );
    signature.insert(
        String::from("type"),
        Value::String(field.field_type.clone()),
    );
    signature.insert(String::from("nullable"), Value::Bool(field.nullable));
    signature.insert(String::from("persisted"), Value::Bool(field.persisted));
    signature.insert(
        String::from("generated"),
        Value::String(field.generated.clone()),
    );
    if let Some(enum_name) = &field.enum_name {
        signature.insert(String::from("enum"), Value::String(enum_name.clone()));
    }
    if let Some(default) = &field.default {
        signature.insert(String::from("default"), default.clone());
    }
    if let Some(length) = field.length {
        signature.insert(String::from("length"), Value::from(length));
    }
    if let Some(precision) = field.precision {
        signature.insert(String::from("precision"), Value::from(precision));
    }
    if let Some(scale) = field.scale {
        signature.insert(String::from("scale"), Value::from(scale));
    }
    if let Some(primary_key) = field.primary_key {
        signature.insert(String::from("primaryKey"), Value::Bool(primary_key));
    }
    if let Some(unique) = field.unique {
        signature.insert(String::from("unique"), Value::Bool(unique));
    }
    signature
}

fn index_signature(index: &Index) -> Map<String, Value> {
    let mut signature = Map::new();
    signature.insert(
        String::from("fields"),
        Value::Array(index.fields.iter().cloned().map(Value::String).collect()),
    );
    signature.insert(String::from("unique"), Value::Bool(index.unique));
    if let Some(name) = &index.name {
        signature.insert(String::from("name"), Value::String(name.clone()));
    }
    signature
}

fn constraint_signature(constraint: &Constraint) -> Map<String, Value> {
    let mut signature = Map::new();
    signature.insert(String::from("kind"), Value::String(constraint.kind.clone()));
    if let Some(name) = &constraint.name {
        signature.insert(String::from("name"), Value::String(name.clone()));
    }
    if let Some(fields) = &constraint.fields {
        signature.insert(
            String::from("fields"),
            Value::Array(fields.iter().cloned().map(Value::String).collect()),
        );
    }
    if let Some(references) = &constraint.references {
        signature.insert(
            String::from("references"),
            serde_json::to_value(references).expect("constraint reference serializes"),
        );
    }
    if let Some(expression) = &constraint.expression {
        signature.insert(
            String::from("expression"),
            Value::String(expression.clone()),
        );
    }
    signature
}

fn column_requires_backfill(field: &Field) -> bool {
    field.persisted && field.generated == "none" && field.default.is_none() && !field.nullable
}

fn compare_signatures(
    before: &Map<String, Value>,
    after: &Map<String, Value>,
) -> Map<String, Value> {
    let mut changes = Map::new();
    for key in sorted_union(before.keys(), after.keys()) {
        let before_value = before.get(key.as_str());
        let after_value = after.get(key.as_str());
        if before_value != after_value {
            let mut change = Map::new();
            change.insert(
                String::from("before"),
                before_value.cloned().unwrap_or(Value::Null),
            );
            change.insert(
                String::from("after"),
                after_value.cloned().unwrap_or(Value::Null),
            );
            changes.insert(key, Value::Object(change));
        }
    }
    changes
}

fn warning(
    code: &str,
    message: &str,
    entity: &str,
    field: Option<String>,
    change_kind: &str,
) -> MigrationWarning {
    MigrationWarning {
        code: String::from(code),
        level: String::from("warning"),
        entity: String::from(entity),
        change_kind: String::from(change_kind),
        message: String::from(message),
        field,
    }
}

fn create_table_change(entity: &Entity) -> Value {
    let mut after = Map::new();
    after.insert(String::from("table"), Value::String(entity.table.clone()));
    after.insert(
        String::from("fields"),
        Value::Array(
            entity
                .fields
                .iter()
                .map(|field| Value::Object(field_signature(field)))
                .collect(),
        ),
    );

    let mut change = Map::new();
    change.insert(
        String::from("kind"),
        Value::String(String::from("createTable")),
    );
    change.insert(String::from("entity"), Value::String(entity.name.clone()));
    change.insert(String::from("after"), Value::Object(after));
    change.insert(String::from("destructive"), Value::Bool(false));
    Value::Object(change)
}

fn drop_table_change(entity_name: &str, entity: &Entity) -> Value {
    let mut before = Map::new();
    before.insert(String::from("table"), Value::String(entity.table.clone()));

    let mut change = Map::new();
    change.insert(
        String::from("kind"),
        Value::String(String::from("dropTable")),
    );
    change.insert(
        String::from("entity"),
        Value::String(String::from(entity_name)),
    );
    change.insert(String::from("before"), Value::Object(before));
    change.insert(String::from("destructive"), Value::Bool(true));
    Value::Object(change)
}

fn rename_table_change(entity_name: &str, before_table: &str, after_table: &str) -> Value {
    let mut table_change = Map::new();
    table_change.insert(
        String::from("before"),
        Value::String(String::from(before_table)),
    );
    table_change.insert(
        String::from("after"),
        Value::String(String::from(after_table)),
    );

    let mut changes = Map::new();
    changes.insert(String::from("table"), Value::Object(table_change));

    let mut change = Map::new();
    change.insert(
        String::from("kind"),
        Value::String(String::from("renameTable")),
    );
    change.insert(
        String::from("entity"),
        Value::String(String::from(entity_name)),
    );
    change.insert(String::from("changes"), Value::Object(changes));
    change.insert(String::from("destructive"), Value::Bool(false));
    Value::Object(change)
}

fn add_column_change(entity_name: &str, field_name: &str, field: &Field) -> Value {
    let mut change = Map::new();
    change.insert(
        String::from("kind"),
        Value::String(String::from("addColumn")),
    );
    change.insert(
        String::from("entity"),
        Value::String(String::from(entity_name)),
    );
    change.insert(
        String::from("field"),
        Value::String(String::from(field_name)),
    );
    change.insert(String::from("after"), Value::Object(field_signature(field)));
    change.insert(String::from("destructive"), Value::Bool(false));
    Value::Object(change)
}

fn drop_column_change(entity_name: &str, field_name: &str, field: &Field) -> Value {
    let mut change = Map::new();
    change.insert(
        String::from("kind"),
        Value::String(String::from("dropColumn")),
    );
    change.insert(
        String::from("entity"),
        Value::String(String::from(entity_name)),
    );
    change.insert(
        String::from("field"),
        Value::String(String::from(field_name)),
    );
    change.insert(
        String::from("before"),
        Value::Object(field_signature(field)),
    );
    change.insert(String::from("destructive"), Value::Bool(true));
    Value::Object(change)
}

fn alter_column_change(
    entity_name: &str,
    field_name: &str,
    attribute_changes: Map<String, Value>,
    destructive: bool,
) -> Value {
    let mut change = Map::new();
    change.insert(
        String::from("kind"),
        Value::String(String::from("alterColumn")),
    );
    change.insert(
        String::from("entity"),
        Value::String(String::from(entity_name)),
    );
    change.insert(
        String::from("field"),
        Value::String(String::from(field_name)),
    );
    change.insert(String::from("changes"), Value::Object(attribute_changes));
    change.insert(String::from("destructive"), Value::Bool(destructive));
    Value::Object(change)
}

fn add_index_change(entity_name: &str, index_name: &str, index: &Index) -> Value {
    let mut change = Map::new();
    change.insert(
        String::from("kind"),
        Value::String(String::from("addIndex")),
    );
    change.insert(
        String::from("entity"),
        Value::String(String::from(entity_name)),
    );
    change.insert(
        String::from("name"),
        Value::String(String::from(index_name)),
    );
    change.insert(String::from("after"), Value::Object(index_signature(index)));
    change.insert(String::from("destructive"), Value::Bool(false));
    Value::Object(change)
}

fn drop_index_change(entity_name: &str, index_name: &str, index: &Index) -> Value {
    let mut change = Map::new();
    change.insert(
        String::from("kind"),
        Value::String(String::from("dropIndex")),
    );
    change.insert(
        String::from("entity"),
        Value::String(String::from(entity_name)),
    );
    change.insert(
        String::from("name"),
        Value::String(String::from(index_name)),
    );
    change.insert(
        String::from("before"),
        Value::Object(index_signature(index)),
    );
    change.insert(String::from("destructive"), Value::Bool(false));
    Value::Object(change)
}

fn alter_index_change(
    entity_name: &str,
    index_name: &str,
    index_changes: Map<String, Value>,
) -> Value {
    let mut change = Map::new();
    change.insert(
        String::from("kind"),
        Value::String(String::from("alterIndex")),
    );
    change.insert(
        String::from("entity"),
        Value::String(String::from(entity_name)),
    );
    change.insert(
        String::from("name"),
        Value::String(String::from(index_name)),
    );
    change.insert(String::from("changes"), Value::Object(index_changes));
    change.insert(String::from("destructive"), Value::Bool(false));
    Value::Object(change)
}

fn add_constraint_change(entity_name: &str, name: &str, constraint: &Constraint) -> Value {
    let mut change = Map::new();
    change.insert(
        String::from("kind"),
        Value::String(String::from("addConstraint")),
    );
    change.insert(
        String::from("entity"),
        Value::String(String::from(entity_name)),
    );
    change.insert(String::from("name"), Value::String(String::from(name)));
    change.insert(
        String::from("after"),
        Value::Object(constraint_signature(constraint)),
    );
    change.insert(String::from("destructive"), Value::Bool(false));
    Value::Object(change)
}

fn drop_constraint_change(entity_name: &str, name: &str, constraint: &Constraint) -> Value {
    let mut change = Map::new();
    change.insert(
        String::from("kind"),
        Value::String(String::from("dropConstraint")),
    );
    change.insert(
        String::from("entity"),
        Value::String(String::from(entity_name)),
    );
    change.insert(String::from("name"), Value::String(String::from(name)));
    change.insert(
        String::from("before"),
        Value::Object(constraint_signature(constraint)),
    );
    change.insert(String::from("destructive"), Value::Bool(false));
    Value::Object(change)
}

fn alter_constraint_change(
    entity_name: &str,
    name: &str,
    constraint_changes: Map<String, Value>,
) -> Value {
    let mut change = Map::new();
    change.insert(
        String::from("kind"),
        Value::String(String::from("alterConstraint")),
    );
    change.insert(
        String::from("entity"),
        Value::String(String::from(entity_name)),
    );
    change.insert(String::from("name"), Value::String(String::from(name)));
    change.insert(String::from("changes"), Value::Object(constraint_changes));
    change.insert(String::from("destructive"), Value::Bool(false));
    Value::Object(change)
}

fn is_destructive_column_change(attribute_changes: &Map<String, Value>) -> bool {
    attribute_changes.contains_key("type")
        || attribute_changes.contains_key("storageName")
        || tightened_nullability(attribute_changes)
        || shrinks_length(attribute_changes)
}

fn tightened_nullability(attribute_changes: &Map<String, Value>) -> bool {
    attribute_changes
        .get("nullable")
        .and_then(Value::as_object)
        .is_some_and(|change| {
            change.get("before").and_then(Value::as_bool) == Some(true)
                && change.get("after").and_then(Value::as_bool) == Some(false)
        })
}

fn shrinks_length(attribute_changes: &Map<String, Value>) -> bool {
    attribute_changes
        .get("length")
        .and_then(Value::as_object)
        .is_some_and(|change| {
            match (
                change.get("before").and_then(Value::as_u64),
                change.get("after").and_then(Value::as_u64),
            ) {
                (Some(before), Some(after)) => after < before,
                _ => false,
            }
        })
}

fn sorted_union<'a, I>(before: I, after: I) -> Vec<String>
where
    I: IntoIterator<Item = &'a String>,
{
    before
        .into_iter()
        .chain(after)
        .cloned()
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect()
}
