use indexmap::IndexMap;
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};

pub type JsonObject = Map<String, Value>;
pub type AdapterMap = IndexMap<String, JsonObject>;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Default)]
pub struct SourceSchemas {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub create: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub read: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub update: Option<String>,
}

impl SourceSchemas {
    pub fn iter(&self) -> impl Iterator<Item = &str> {
        self.create
            .iter()
            .chain(self.read.iter())
            .chain(self.update.iter())
            .map(String::as_str)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Output {
    pub target: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub filename: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub options: Option<JsonObject>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct CanonicalEnum {
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    #[serde(rename = "sourceSchemas")]
    pub source_schemas: SourceSchemas,
    pub values: Vec<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub adapters: Option<AdapterMap>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Computed {
    pub expression: String,
    pub stored: bool,
    #[serde(rename = "dependsOn", default, skip_serializing_if = "Option::is_none")]
    pub depends_on: Option<Vec<String>>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Field {
    pub name: String,
    #[serde(rename = "storageName")]
    pub storage_name: String,
    #[serde(rename = "type")]
    pub field_type: String,
    pub nullable: bool,
    pub persisted: bool,
    pub generated: String,
    #[serde(rename = "sourceSchemas")]
    pub source_schemas: SourceSchemas,
    #[serde(rename = "enum", skip_serializing_if = "Option::is_none")]
    pub enum_name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub default: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub computed: Option<Computed>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub length: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub precision: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub scale: Option<u64>,
    #[serde(rename = "primaryKey", skip_serializing_if = "Option::is_none")]
    pub primary_key: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub unique: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub adapters: Option<AdapterMap>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Relation {
    pub name: String,
    pub kind: String,
    #[serde(rename = "targetEntity")]
    pub target_entity: String,
    pub ownership: String,
    #[serde(rename = "foreignKey", skip_serializing_if = "Option::is_none")]
    pub foreign_key: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub references: Option<String>,
    #[serde(rename = "throughEntity", skip_serializing_if = "Option::is_none")]
    pub through_entity: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub adapters: Option<AdapterMap>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ConstraintReference {
    pub entity: String,
    pub fields: Vec<String>,
    #[serde(rename = "onDelete", skip_serializing_if = "Option::is_none")]
    pub on_delete: Option<String>,
    #[serde(rename = "onUpdate", skip_serializing_if = "Option::is_none")]
    pub on_update: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Constraint {
    pub kind: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub fields: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub references: Option<ConstraintReference>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub expression: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub adapters: Option<AdapterMap>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Index {
    pub fields: Vec<String>,
    pub unique: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub adapters: Option<AdapterMap>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Entity {
    pub name: String,
    pub table: String,
    #[serde(rename = "sourceSchemas")]
    pub source_schemas: SourceSchemas,
    pub fields: Vec<Field>,
    pub relations: Vec<Relation>,
    pub indexes: Vec<Index>,
    pub constraints: Vec<Constraint>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub adapters: Option<AdapterMap>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct CanonicalModel {
    pub version: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub adapters: Option<AdapterMap>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub outputs: Option<Vec<Output>>,
    #[serde(default)]
    pub enums: Vec<CanonicalEnum>,
    pub entities: Vec<Entity>,
}
