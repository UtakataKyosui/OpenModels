use std::fs;
use std::path::Path;

use indexmap::IndexMap;
use serde::Deserialize;
use serde_json::Value;

use crate::error::{Result, message};
use crate::model::{AdapterMap, Computed, ConstraintReference, JsonObject, Output, SourceSchemas};

#[derive(Debug, Clone)]
pub struct LoadedDocument {
    pub raw: Value,
    pub parsed: OpenApiDocument,
}

#[derive(Debug, Clone, Deserialize)]
pub struct OpenApiDocument {
    pub openapi: String,
    #[serde(default)]
    pub components: OpenApiComponents,
    #[serde(rename = "x-openmodels")]
    pub extension: Option<OpenModelsExtension>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct OpenApiComponents {
    #[serde(default)]
    pub schemas: IndexMap<String, Value>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct OpenModelsExtension {
    pub version: String,
    #[serde(default)]
    pub adapters: Option<AdapterMap>,
    #[serde(default)]
    pub outputs: Option<Vec<Output>>,
    #[serde(default)]
    pub enums: IndexMap<String, ExtensionEnum>,
    pub entities: IndexMap<String, ExtensionEntity>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ExtensionEnum {
    #[serde(default)]
    pub description: Option<String>,
    #[serde(default)]
    pub schema: SourceSchemas,
    pub values: Vec<Value>,
    #[serde(default)]
    pub adapters: Option<AdapterMap>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ExtensionEntity {
    pub table: String,
    #[serde(rename = "sourceSchemas", default)]
    pub source_schemas: SourceSchemas,
    pub fields: IndexMap<String, ExtensionField>,
    #[serde(default)]
    pub relations: IndexMap<String, ExtensionRelation>,
    #[serde(default)]
    pub indexes: Vec<ExtensionIndex>,
    #[serde(default)]
    pub constraints: Vec<ExtensionConstraint>,
    #[serde(default)]
    pub adapters: Option<AdapterMap>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ExtensionField {
    #[serde(default)]
    pub schema: SourceSchemas,
    #[serde(default)]
    pub column: ExtensionColumn,
    #[serde(rename = "enum", default)]
    pub enum_name: Option<String>,
    #[serde(rename = "virtual", default)]
    pub virtual_field: bool,
    #[serde(default)]
    pub computed: Option<Computed>,
    #[serde(default)]
    pub adapters: Option<AdapterMap>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct ExtensionColumn {
    #[serde(rename = "type", default)]
    pub field_type: Option<String>,
    #[serde(default)]
    pub nullable: Option<bool>,
    #[serde(rename = "primaryKey", default)]
    pub primary_key: Option<bool>,
    #[serde(default)]
    pub generated: Option<String>,
    #[serde(default)]
    pub default: Option<Value>,
    #[serde(default)]
    pub length: Option<u64>,
    #[serde(default)]
    pub precision: Option<u64>,
    #[serde(default)]
    pub scale: Option<u64>,
    #[serde(default)]
    pub unique: Option<bool>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ExtensionRelation {
    pub kind: String,
    pub target: String,
    #[serde(rename = "references", default)]
    pub reference_field: Option<String>,
    #[serde(rename = "foreignKey", default)]
    pub foreign_key: Option<String>,
    #[serde(default)]
    pub through: Option<String>,
    #[serde(default)]
    pub adapters: Option<AdapterMap>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ExtensionConstraint {
    pub kind: String,
    #[serde(default)]
    pub name: Option<String>,
    #[serde(default)]
    pub fields: Option<Vec<String>>,
    #[serde(default)]
    pub references: Option<ConstraintReference>,
    #[serde(default)]
    pub expression: Option<String>,
    #[serde(default)]
    pub adapters: Option<AdapterMap>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ExtensionIndex {
    pub fields: Vec<String>,
    #[serde(default)]
    pub unique: Option<bool>,
    #[serde(default)]
    pub name: Option<String>,
    #[serde(default)]
    pub adapters: Option<AdapterMap>,
}

pub fn load_openapi_document(path: impl AsRef<Path>) -> Result<LoadedDocument> {
    let path = path.as_ref();
    let text = fs::read_to_string(path)?;
    let suffix = path
        .extension()
        .and_then(|value| value.to_str())
        .unwrap_or_default();

    let raw = match suffix {
        "yaml" | "yml" => serde_yaml::from_str::<Value>(&text)?,
        "json" => serde_json::from_str::<Value>(&text)?,
        _ => return Err(message(format!("Unsupported input file type: .{}", suffix))),
    };

    let parsed: OpenApiDocument = serde_json::from_value(raw.clone())?;
    if !(parsed.openapi.starts_with("3.0.") || parsed.openapi.starts_with("3.1.")) {
        return Err(message(format!(
            "Unsupported OpenAPI version '{}'. Only 3.0.x and 3.1.x are supported.",
            parsed.openapi
        )));
    }
    if parsed.extension.is_none() {
        return Err(message(
            "Input document is missing the top-level 'x-openmodels' field.",
        ));
    }

    Ok(LoadedDocument { raw, parsed })
}

pub fn write_json_file(path: impl AsRef<Path>, value: &Value) -> Result<()> {
    let path = path.as_ref();
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(path, serde_json::to_string_pretty(value)? + "\n")?;
    Ok(())
}

pub fn empty_object() -> JsonObject {
    JsonObject::new()
}
