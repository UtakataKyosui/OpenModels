use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};

use serde::Serialize;
use serde_json::Value;

use crate::error::{message, Result};
use crate::model::{CanonicalModel, Entity, Relation};
use crate::model_io::load_canonical_model;
use crate::openapi::load_openapi_document;
use crate::registry::list_adapters;

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub struct Diagnostic {
    pub code: String,
    pub path: String,
    pub message: String,
}

pub fn validate_examples() -> Result<Vec<Diagnostic>> {
    let root = repo_root();
    let openapi_document = load_openapi_document(root.join("examples/openapi/blog-api.yaml"))?;
    let openapi_document_v1 =
        load_openapi_document(root.join("examples/openapi/blog-api-v1.yaml"))?;
    let canonical_model = load_canonical_model(root.join("examples/canonical/blog-model.json"))?;

    let extension = openapi_document
        .raw
        .get("x-openmodels")
        .ok_or_else(|| message("Input document is missing the top-level 'x-openmodels' field."))?;
    let extension_v1 = openapi_document_v1
        .raw
        .get("x-openmodels")
        .ok_or_else(|| message("Input document is missing the top-level 'x-openmodels' field."))?;

    let mut diagnostics = Vec::new();
    diagnostics.extend(validate_x_openmodels_semantics(extension));
    diagnostics.extend(validate_x_openmodels_semantics(extension_v1));
    diagnostics.extend(validate_canonical_model_semantics(&canonical_model));
    Ok(diagnostics)
}

pub fn validate_x_openmodels_semantics(extension: &Value) -> Vec<Diagnostic> {
    let known_targets = known_adapter_targets();
    let entities = extension
        .get("entities")
        .and_then(Value::as_object)
        .cloned()
        .unwrap_or_default();
    let enum_names = extension
        .get("enums")
        .and_then(Value::as_object)
        .map(|values| values.keys().cloned().collect::<BTreeSet<_>>())
        .unwrap_or_default();
    let entity_names = entities.keys().cloned().collect::<BTreeSet<_>>();
    let field_names = field_names_by_entity(&entities);

    let mut diagnostics = Vec::new();

    if let Some(outputs) = extension.get("outputs").and_then(Value::as_array) {
        for (output_index, output) in outputs.iter().enumerate() {
            let target = output
                .get("target")
                .and_then(Value::as_str)
                .unwrap_or_default();
            if !known_targets.contains(target) {
                diagnostics.push(Diagnostic {
                    code: String::from("unknown-output-target"),
                    path: format!("outputs[{output_index}].target"),
                    message: format!("Unknown output target '{target}'."),
                });
            }
        }
    }

    for (entity_name, entity) in &entities {
        if let Some(fields) = entity.get("fields").and_then(Value::as_object) {
            for (field_name, field) in fields {
                if let Some(enum_name) = field.get("enum").and_then(Value::as_str) {
                    if !enum_names.contains(enum_name) {
                        diagnostics.push(Diagnostic {
                            code: String::from("unknown-enum"),
                            path: format!("entities.{entity_name}.fields.{field_name}.enum"),
                            message: format!("Unknown enum '{enum_name}'."),
                        });
                    }
                }
            }
        }

        if let Some(relations) = entity.get("relations").and_then(Value::as_object) {
            for (relation_name, relation) in relations {
                let target = relation
                    .get("target")
                    .and_then(Value::as_str)
                    .unwrap_or_default();
                if !entity_names.contains(target) {
                    diagnostics.push(Diagnostic {
                        code: String::from("unknown-relation-target"),
                        path: format!("entities.{entity_name}.relations.{relation_name}.target"),
                        message: format!("Unknown relation target '{target}'."),
                    });
                    continue;
                }

                let foreign_key = relation.get("foreignKey").and_then(Value::as_str);
                let references = relation.get("references").and_then(Value::as_str);
                let (owner_entity, referenced_entity) =
                    x_openmodels_foreign_key_owner(entity_name, relation);

                if let (Some(foreign_key), Some(owner_entity)) = (foreign_key, owner_entity) {
                    if !field_names
                        .get(owner_entity)
                        .is_some_and(|fields| fields.contains(foreign_key))
                    {
                        diagnostics.push(Diagnostic {
                            code: String::from("unknown-foreign-key-field"),
                            path: format!(
                                "entities.{entity_name}.relations.{relation_name}.foreignKey"
                            ),
                            message: format!(
                                "Unknown foreign key field '{foreign_key}' on entity '{owner_entity}'."
                            ),
                        });
                    }
                }

                if let (Some(references), Some(referenced_entity)) = (references, referenced_entity)
                {
                    if !field_names
                        .get(referenced_entity)
                        .is_some_and(|fields| fields.contains(references))
                    {
                        diagnostics.push(Diagnostic {
                            code: String::from("unknown-reference-field"),
                            path: format!(
                                "entities.{entity_name}.relations.{relation_name}.references"
                            ),
                            message: format!(
                                "Unknown referenced field '{references}' on entity '{referenced_entity}'."
                            ),
                        });
                    }
                }
            }
        }

        if let Some(indexes) = entity.get("indexes").and_then(Value::as_array) {
            for (index_index, index) in indexes.iter().enumerate() {
                for field_name in string_array(index.get("fields")) {
                    if !field_names
                        .get(entity_name)
                        .is_some_and(|fields| fields.contains(field_name.as_str()))
                    {
                        diagnostics.push(Diagnostic {
                            code: String::from("unknown-index-field"),
                            path: format!("entities.{entity_name}.indexes[{index_index}]"),
                            message: format!("Unknown index field '{field_name}'."),
                        });
                    }
                }
            }
        }

        if let Some(constraints) = entity.get("constraints").and_then(Value::as_array) {
            for (constraint_index, constraint) in constraints.iter().enumerate() {
                for field_name in string_array(constraint.get("fields")) {
                    if !field_names
                        .get(entity_name)
                        .is_some_and(|fields| fields.contains(field_name.as_str()))
                    {
                        diagnostics.push(Diagnostic {
                            code: String::from("unknown-constraint-field"),
                            path: format!("entities.{entity_name}.constraints[{constraint_index}]"),
                            message: format!("Unknown constraint field '{field_name}'."),
                        });
                    }
                }

                if constraint.get("kind").and_then(Value::as_str) == Some("foreignKey") {
                    let Some(references) = constraint.get("references").and_then(Value::as_object)
                    else {
                        diagnostics.push(Diagnostic {
                            code: String::from("missing-foreign-key-reference"),
                            path: format!("entities.{entity_name}.constraints[{constraint_index}]"),
                            message: String::from("Foreign key constraint must define references."),
                        });
                        continue;
                    };

                    let target = references
                        .get("entity")
                        .and_then(Value::as_str)
                        .unwrap_or_default();
                    if !entity_names.contains(target) {
                        diagnostics.push(Diagnostic {
                            code: String::from("unknown-constraint-target"),
                            path: format!(
                                "entities.{entity_name}.constraints[{constraint_index}].references.entity"
                            ),
                            message: format!("Unknown foreign key target '{target}'."),
                        });
                        continue;
                    }

                    for target_field in string_array(references.get("fields")) {
                        if !field_names
                            .get(target)
                            .is_some_and(|fields| fields.contains(target_field.as_str()))
                        {
                            diagnostics.push(Diagnostic {
                                code: String::from("unknown-constraint-reference-field"),
                                path: format!(
                                    "entities.{entity_name}.constraints[{constraint_index}].references.fields"
                                ),
                                message: format!(
                                    "Unknown referenced field '{target_field}' on entity '{target}'."
                                ),
                            });
                        }
                    }
                }
            }
        }
    }

    diagnostics
}

pub fn validate_canonical_model_semantics(model: &CanonicalModel) -> Vec<Diagnostic> {
    let known_targets = known_adapter_targets();
    let entity_names = model
        .entities
        .iter()
        .map(|entity| entity.name.clone())
        .collect::<BTreeSet<_>>();
    let field_names = field_names_by_canonical_entity(&model.entities);
    let enum_names = model
        .enums
        .iter()
        .map(|canonical_enum| canonical_enum.name.clone())
        .collect::<BTreeSet<_>>();

    let mut diagnostics = Vec::new();

    if let Some(outputs) = &model.outputs {
        for (output_index, output) in outputs.iter().enumerate() {
            if !known_targets.contains(output.target.as_str()) {
                diagnostics.push(Diagnostic {
                    code: String::from("unknown-output-target"),
                    path: format!("outputs[{output_index}].target"),
                    message: format!("Unknown output target '{}'.", output.target),
                });
            }
        }
    }

    for entity in &model.entities {
        let entity_name = &entity.name;
        for field in &entity.fields {
            if let Some(enum_name) = &field.enum_name {
                if !enum_names.contains(enum_name) {
                    diagnostics.push(Diagnostic {
                        code: String::from("unknown-enum"),
                        path: format!("entities.{entity_name}.fields.{}.enum", field.name),
                        message: format!("Unknown enum '{enum_name}'."),
                    });
                }
            }
        }

        for relation in &entity.relations {
            let relation_name = &relation.name;
            let target = &relation.target_entity;
            if !entity_names.contains(target) {
                diagnostics.push(Diagnostic {
                    code: String::from("unknown-relation-target"),
                    path: format!("entities.{entity_name}.relations.{relation_name}.targetEntity"),
                    message: format!("Unknown relation target '{target}'."),
                });
                continue;
            }

            let (owner_entity, referenced_entity) = canonical_relation_owner(entity_name, relation);
            if let (Some(foreign_key), Some(owner_entity)) =
                (relation.foreign_key.as_deref(), owner_entity)
            {
                if !field_names
                    .get(owner_entity)
                    .is_some_and(|fields| fields.contains(foreign_key))
                {
                    diagnostics.push(Diagnostic {
                        code: String::from("unknown-foreign-key-field"),
                        path: format!(
                            "entities.{entity_name}.relations.{relation_name}.foreignKey"
                        ),
                        message: format!(
                            "Unknown foreign key field '{foreign_key}' on entity '{owner_entity}'."
                        ),
                    });
                }
            }

            if let (Some(references), Some(referenced_entity)) =
                (relation.references.as_deref(), referenced_entity)
            {
                if !field_names
                    .get(referenced_entity)
                    .is_some_and(|fields| fields.contains(references))
                {
                    diagnostics.push(Diagnostic {
                        code: String::from("unknown-reference-field"),
                        path: format!(
                            "entities.{entity_name}.relations.{relation_name}.references"
                        ),
                        message: format!(
                            "Unknown referenced field '{references}' on entity '{referenced_entity}'."
                        ),
                    });
                }
            }
        }

        for index in &entity.indexes {
            for field_name in &index.fields {
                if !field_names
                    .get(entity_name)
                    .is_some_and(|fields| fields.contains(field_name))
                {
                    diagnostics.push(Diagnostic {
                        code: String::from("unknown-index-field"),
                        path: format!(
                            "entities.{entity_name}.indexes.{}",
                            index.name.as_deref().unwrap_or("<unnamed>")
                        ),
                        message: format!("Unknown index field '{field_name}'."),
                    });
                }
            }
        }

        for constraint in &entity.constraints {
            let constraint_name = constraint.name.as_deref().unwrap_or("<unnamed>");
            if let Some(fields) = &constraint.fields {
                for field_name in fields {
                    if !field_names
                        .get(entity_name)
                        .is_some_and(|entity_fields| entity_fields.contains(field_name))
                    {
                        diagnostics.push(Diagnostic {
                            code: String::from("unknown-constraint-field"),
                            path: format!("entities.{entity_name}.constraints.{constraint_name}"),
                            message: format!("Unknown constraint field '{field_name}'."),
                        });
                    }
                }
            }

            if constraint.kind == "foreignKey" {
                let Some(references) = constraint.references.as_ref() else {
                    diagnostics.push(Diagnostic {
                        code: String::from("missing-foreign-key-reference"),
                        path: format!("entities.{entity_name}.constraints.{constraint_name}"),
                        message: String::from("Foreign key constraint must define references."),
                    });
                    continue;
                };

                if !entity_names.contains(&references.entity) {
                    diagnostics.push(Diagnostic {
                        code: String::from("unknown-constraint-target"),
                        path: format!(
                            "entities.{entity_name}.constraints.{constraint_name}.references.entity"
                        ),
                        message: format!("Unknown foreign key target '{}'.", references.entity),
                    });
                    continue;
                }

                for target_field in &references.fields {
                    if !field_names
                        .get(&references.entity)
                        .is_some_and(|fields| fields.contains(target_field))
                    {
                        diagnostics.push(Diagnostic {
                            code: String::from("unknown-constraint-reference-field"),
                            path: format!(
                                "entities.{entity_name}.constraints.{constraint_name}.references.fields"
                            ),
                            message: format!(
                                "Unknown referenced field '{}' on entity '{}'.",
                                target_field, references.entity
                            ),
                        });
                    }
                }
            }
        }
    }

    diagnostics
}

fn known_adapter_targets() -> BTreeSet<&'static str> {
    list_adapters()
        .iter()
        .map(|adapter| adapter.key())
        .collect()
}

fn field_names_by_entity(
    entities: &serde_json::Map<String, Value>,
) -> BTreeMap<String, BTreeSet<String>> {
    let mut names = BTreeMap::new();
    for (entity_name, entity) in entities {
        let field_names = entity
            .get("fields")
            .and_then(Value::as_object)
            .map(|fields| fields.keys().cloned().collect::<BTreeSet<_>>())
            .unwrap_or_default();
        names.insert(entity_name.clone(), field_names);
    }
    names
}

fn field_names_by_canonical_entity(entities: &[Entity]) -> BTreeMap<String, BTreeSet<String>> {
    entities
        .iter()
        .map(|entity| {
            (
                entity.name.clone(),
                entity
                    .fields
                    .iter()
                    .map(|field| field.name.clone())
                    .collect::<BTreeSet<_>>(),
            )
        })
        .collect()
}

fn x_openmodels_foreign_key_owner<'a>(
    entity_name: &'a str,
    relation: &'a Value,
) -> (Option<&'a str>, Option<&'a str>) {
    let kind = relation.get("kind").and_then(Value::as_str);
    let target = relation.get("target").and_then(Value::as_str);
    match kind {
        Some("belongsTo") => (Some(entity_name), target),
        Some("hasOne") | Some("hasMany") => (target, Some(entity_name)),
        _ => (None, target),
    }
}

fn canonical_relation_owner<'a>(
    entity_name: &'a str,
    relation: &'a Relation,
) -> (Option<&'a str>, Option<&'a str>) {
    match relation.ownership.as_str() {
        "owner" => (Some(entity_name), Some(relation.target_entity.as_str())),
        "inverse" => (Some(relation.target_entity.as_str()), Some(entity_name)),
        _ => (None, Some(relation.target_entity.as_str())),
    }
}

fn string_array(value: Option<&Value>) -> Vec<String> {
    value
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(Value::as_str)
                .map(String::from)
                .collect::<Vec<_>>()
        })
        .unwrap_or_default()
}

fn repo_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .expect("repo root")
}
