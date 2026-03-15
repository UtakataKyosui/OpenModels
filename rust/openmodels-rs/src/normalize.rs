use std::collections::HashSet;

use serde_json::Value;

use crate::error::{message, Result};
use crate::model::{
    AdapterMap, CanonicalEnum, CanonicalModel, Constraint, Entity, Field, Index, Relation,
};
use crate::openapi::{
    ExtensionConstraint, ExtensionEntity, ExtensionField, ExtensionIndex, ExtensionRelation,
    LoadedDocument,
};
use crate::utils::snake_case;

pub fn normalize_openapi_document(document: &LoadedDocument) -> Result<CanonicalModel> {
    let extension =
        document.parsed.extension.as_ref().ok_or_else(|| {
            message("Input document is missing the top-level 'x-openmodels' field.")
        })?;

    let enum_names: HashSet<&str> = extension.enums.keys().map(String::as_str).collect();
    let enums = extension
        .enums
        .iter()
        .map(|(name, definition)| normalize_enum(name, definition, document))
        .collect::<Result<Vec<_>>>()?;

    let entities = extension
        .entities
        .iter()
        .map(|(name, definition)| normalize_entity(name, definition, document, &enum_names))
        .collect::<Result<Vec<_>>>()?;

    Ok(CanonicalModel {
        version: extension.version.clone(),
        adapters: extension.adapters.clone(),
        outputs: extension.outputs.clone(),
        enums,
        entities,
    })
}

fn normalize_enum(
    name: &str,
    definition: &crate::openapi::ExtensionEnum,
    document: &LoadedDocument,
) -> Result<CanonicalEnum> {
    for pointer in definition.schema.iter() {
        resolve_schema_node(&document.raw, pointer)?;
    }

    Ok(CanonicalEnum {
        name: name.to_owned(),
        description: definition.description.clone(),
        source_schemas: definition.schema.clone(),
        values: definition.values.clone(),
        adapters: definition.adapters.clone(),
    })
}

fn normalize_entity(
    entity_name: &str,
    entity_definition: &ExtensionEntity,
    document: &LoadedDocument,
    enum_names: &HashSet<&str>,
) -> Result<Entity> {
    let field_names: HashSet<&str> = entity_definition
        .fields
        .keys()
        .map(String::as_str)
        .collect();
    let fields = entity_definition
        .fields
        .iter()
        .map(|(field_name, field_definition)| {
            if let Some(enum_name) = field_definition.enum_name.as_deref() {
                if !enum_names.contains(enum_name) {
                    return Err(message(format!(
                        "Field '{}.{}' references unknown enum '{}'.",
                        entity_name, field_name, enum_name
                    )));
                }
            }
            normalize_field(field_name, field_definition, &document.raw)
        })
        .collect::<Result<Vec<_>>>()?;

    let extension =
        document.parsed.extension.as_ref().ok_or_else(|| {
            message("Input document is missing the top-level 'x-openmodels' field.")
        })?;

    let relations = entity_definition
        .relations
        .iter()
        .map(|(relation_name, relation_definition)| {
            normalize_relation(
                entity_name,
                relation_name,
                relation_definition,
                &extension.entities,
            )
        })
        .collect::<Result<Vec<_>>>()?;

    let indexes = entity_definition
        .indexes
        .iter()
        .map(|index_definition| normalize_index(index_definition, &field_names))
        .collect::<Result<Vec<_>>>()?;

    let constraints = entity_definition
        .constraints
        .iter()
        .map(|constraint_definition| {
            normalize_constraint(
                entity_name,
                constraint_definition,
                &extension.entities,
                &field_names,
            )
        })
        .collect::<Result<Vec<_>>>()?;

    Ok(Entity {
        name: entity_name.to_owned(),
        table: entity_definition.table.clone(),
        source_schemas: entity_definition.source_schemas.clone(),
        fields,
        relations,
        indexes,
        constraints,
        adapters: entity_definition.adapters.clone(),
    })
}

fn normalize_field(
    field_name: &str,
    definition: &ExtensionField,
    document: &Value,
) -> Result<Field> {
    for pointer in definition.schema.iter() {
        resolve_schema_node(document, pointer)?;
    }

    let persisted = !definition.virtual_field
        && !definition
            .computed
            .as_ref()
            .is_some_and(|computed| !computed.stored);

    Ok(Field {
        name: field_name.to_owned(),
        storage_name: snake_case(field_name),
        field_type: definition
            .column
            .field_type
            .clone()
            .unwrap_or_else(|| "unknown".to_owned()),
        nullable: infer_nullable(document, definition)?,
        persisted,
        generated: definition
            .column
            .generated
            .clone()
            .unwrap_or_else(|| "none".to_owned()),
        source_schemas: definition.schema.clone(),
        enum_name: definition.enum_name.clone(),
        default: definition.column.default.clone(),
        computed: definition.computed.clone(),
        length: definition.column.length,
        precision: definition.column.precision,
        scale: definition.column.scale,
        primary_key: definition.column.primary_key.map(|value| value),
        unique: definition.column.unique.map(|value| value),
        adapters: definition.adapters.clone(),
    })
}

fn normalize_relation(
    entity_name: &str,
    relation_name: &str,
    definition: &ExtensionRelation,
    entities: &indexmap::IndexMap<String, ExtensionEntity>,
) -> Result<Relation> {
    if !entities.contains_key(&definition.target) {
        return Err(message(format!(
            "Relation '{}.{}' references unknown entity '{}'.",
            entity_name, relation_name, definition.target
        )));
    }

    let ownership = if definition.kind == "belongsTo" {
        "owner"
    } else {
        "inverse"
    };
    let current_primary_keys = entity_primary_key_fields(
        entities
            .get(entity_name)
            .ok_or_else(|| message(format!("Entity '{}' not found.", entity_name)))?,
    );
    let target_primary_keys = entity_primary_key_fields(
        entities
            .get(&definition.target)
            .ok_or_else(|| message(format!("Entity '{}' not found.", definition.target)))?,
    );

    let references = if ownership == "owner" {
        definition
            .reference_field
            .clone()
            .or_else(|| target_primary_keys.first().cloned())
    } else {
        definition
            .reference_field
            .clone()
            .or_else(|| current_primary_keys.first().cloned())
    };

    Ok(Relation {
        name: relation_name.to_owned(),
        kind: definition.kind.clone(),
        target_entity: definition.target.clone(),
        ownership: ownership.to_owned(),
        foreign_key: definition.foreign_key.clone(),
        references,
        through_entity: definition.through.clone(),
        adapters: definition.adapters.clone(),
    })
}

fn normalize_constraint(
    entity_name: &str,
    definition: &ExtensionConstraint,
    entities: &indexmap::IndexMap<String, ExtensionEntity>,
    field_names: &HashSet<&str>,
) -> Result<Constraint> {
    if let Some(fields) = &definition.fields {
        for field_name in fields {
            if !field_names.contains(field_name.as_str()) {
                return Err(message(format!(
                    "Constraint on entity '{}' references unknown field '{}'.",
                    entity_name, field_name
                )));
            }
        }
    }

    let references = if definition.kind == "foreignKey" {
        let references = definition.references.clone().ok_or_else(|| {
            message(format!(
                "Foreign key constraint on '{}' must define references.",
                entity_name
            ))
        })?;
        let target_entity = entities.get(&references.entity).ok_or_else(|| {
            message(format!(
                "Foreign key constraint on '{}' references unknown entity '{}'.",
                entity_name, references.entity
            ))
        })?;
        let target_field_names: HashSet<&str> =
            target_entity.fields.keys().map(String::as_str).collect();
        for target_field in &references.fields {
            if !target_field_names.contains(target_field.as_str()) {
                return Err(message(format!(
                    "Foreign key constraint on '{}' references unknown field '{}.{}'.",
                    entity_name, references.entity, target_field
                )));
            }
        }
        Some(references)
    } else {
        definition.references.clone()
    };

    Ok(Constraint {
        kind: definition.kind.clone(),
        name: definition.name.clone(),
        fields: definition.fields.clone(),
        references,
        expression: definition.expression.clone(),
        adapters: definition.adapters.clone(),
    })
}

fn normalize_index(definition: &ExtensionIndex, field_names: &HashSet<&str>) -> Result<Index> {
    for field_name in &definition.fields {
        if !field_names.contains(field_name.as_str()) {
            return Err(message(format!(
                "Index references unknown field '{}'.",
                field_name
            )));
        }
    }

    Ok(Index {
        fields: definition.fields.clone(),
        unique: definition.unique.unwrap_or(false),
        name: definition.name.clone(),
        adapters: definition.adapters.clone(),
    })
}

fn entity_primary_key_fields(entity: &ExtensionEntity) -> Vec<String> {
    let mut fields = entity
        .fields
        .iter()
        .filter(|(_, field)| field.column.primary_key.unwrap_or(false))
        .map(|(name, _)| name.clone())
        .collect::<Vec<_>>();
    for constraint in &entity.constraints {
        if constraint.kind == "primaryKey" {
            if let Some(constraint_fields) = &constraint.fields {
                fields.extend(constraint_fields.iter().cloned());
            }
        }
    }
    fields
}

fn infer_nullable(document: &Value, field: &ExtensionField) -> Result<bool> {
    if let Some(nullable) = field.column.nullable {
        return Ok(nullable);
    }
    if field.column.primary_key.unwrap_or(false) {
        return Ok(false);
    }
    if matches!(
        field.column.generated.as_deref(),
        Some("database") | Some("application")
    ) {
        return Ok(false);
    }

    let mut required_values = Vec::new();
    for pointer in field.schema.iter() {
        if schema_allows_null(document, pointer)? {
            return Ok(true);
        }
        if let Some(required) = property_is_required(document, pointer)? {
            required_values.push(required);
        }
    }

    if !required_values.is_empty() && required_values.iter().all(|value| *value) {
        return Ok(false);
    }

    Ok(false)
}

fn property_is_required(document: &Value, pointer: &str) -> Result<Option<bool>> {
    let (property_name, parent_pointer) = property_context(pointer);
    let Some(property_name) = property_name else {
        return Ok(None);
    };
    let Some(parent_pointer) = parent_pointer else {
        return Ok(None);
    };
    let parent_schema = resolve_schema_node(document, &parent_pointer)?;
    let required = parent_schema
        .as_object()
        .and_then(|map| map.get("required"))
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(Value::as_str)
                .any(|item| item == property_name)
        })
        .unwrap_or(false);
    Ok(Some(required))
}

fn property_context(pointer: &str) -> (Option<String>, Option<String>) {
    let marker = "/properties/";
    let Some((parent_pointer, property_name)) = pointer.rsplit_once(marker) else {
        return (None, None);
    };
    (
        Some(property_name.to_owned()),
        Some(parent_pointer.to_owned()),
    )
}

fn schema_allows_null(document: &Value, pointer: &str) -> Result<bool> {
    let node = resolve_schema_node(document, pointer)?;
    let Some(object) = node.as_object() else {
        return Ok(false);
    };
    if object.get("nullable").and_then(Value::as_bool) == Some(true) {
        return Ok(true);
    }
    let Some(node_type) = object.get("type") else {
        return Ok(false);
    };
    match node_type {
        Value::String(value) => Ok(value == "null"),
        Value::Array(items) => Ok(items.iter().any(|item| item.as_str() == Some("null"))),
        _ => Ok(false),
    }
}

pub fn resolve_schema_node<'a>(document: &'a Value, pointer: &str) -> Result<&'a Value> {
    let mut node = resolve_json_pointer(document, pointer)?;
    let mut visited = HashSet::new();

    loop {
        ensure_supported_schema_node(node, pointer)?;
        let Some(reference) = node
            .as_object()
            .and_then(|map| map.get("$ref"))
            .and_then(Value::as_str)
        else {
            return Ok(node);
        };
        if !visited.insert(reference.to_owned()) {
            return Err(message(format!("Cyclic $ref detected at {}", reference)));
        }
        node = resolve_json_pointer(document, reference)?;
    }
}

pub fn resolve_json_pointer<'a>(document: &'a Value, pointer: &str) -> Result<&'a Value> {
    if pointer == "#" {
        return Ok(document);
    }
    if !pointer.starts_with("#/") {
        return Err(message(format!("Unsupported JSON pointer: {}", pointer)));
    }

    let mut current = document;
    for raw_token in pointer[2..].split('/') {
        let token = raw_token.replace("~1", "/").replace("~0", "~");
        match current {
            Value::Array(items) => {
                let index = token.parse::<usize>().map_err(|_| {
                    message(format!(
                        "Invalid list pointer segment '{}' in {}",
                        token, pointer
                    ))
                })?;
                current = items.get(index).ok_or_else(|| {
                    message(format!(
                        "Invalid list pointer segment '{}' in {}",
                        token, pointer
                    ))
                })?;
            }
            Value::Object(map) => {
                current = map
                    .get(&token)
                    .ok_or_else(|| message(format!("Pointer not found: {}", pointer)))?;
            }
            _ => return Err(message(format!("Pointer not found: {}", pointer))),
        }
    }

    Ok(current)
}

fn ensure_supported_schema_node(node: &Value, pointer: &str) -> Result<()> {
    let Some(object) = node.as_object() else {
        return Ok(());
    };
    for keyword in ["oneOf", "anyOf", "allOf", "discriminator"] {
        if object.contains_key(keyword) {
            return Err(message(format!(
                "Unsupported OpenAPI construct '{}' at {}.",
                keyword, pointer
            )));
        }
    }
    Ok(())
}

pub fn canonical_model_to_value(model: &CanonicalModel) -> Result<Value> {
    Ok(serde_json::to_value(model)?)
}

pub fn canonical_model_to_pretty_json(model: &CanonicalModel) -> Result<String> {
    Ok(serde_json::to_string_pretty(model)? + "\n")
}

#[allow(dead_code)]
fn copy_adapters(adapters: &Option<AdapterMap>) -> Option<AdapterMap> {
    adapters.clone()
}
