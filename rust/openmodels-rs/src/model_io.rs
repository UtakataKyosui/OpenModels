use std::fs;
use std::path::Path;

use serde_json::Value;

use crate::error::{Result, message};
use crate::model::CanonicalModel;
use crate::normalize::normalize_openapi_document;
use crate::openapi::load_openapi_document;
use crate::schema::validate_canonical_model_schema;

pub fn load_canonical_model(path: impl AsRef<Path>) -> Result<CanonicalModel> {
    let path = path.as_ref();
    let raw = load_raw_document(path)?;
    let object = raw
        .as_object()
        .ok_or_else(|| message("Model input must be a JSON or YAML object."))?;

    if object.contains_key("openapi") {
        let document = load_openapi_document(path)?;
        return normalize_openapi_document(&document);
    }

    if object.contains_key("version") && object.contains_key("entities") {
        validate_canonical_model_schema(&raw)?;
        return Ok(serde_json::from_value(raw)?);
    }

    Err(message(
        "Input must be either an OpenAPI document with x-openmodels or a canonical model JSON document.",
    ))
}

fn load_raw_document(path: &Path) -> Result<Value> {
    let text = fs::read_to_string(path)?;
    let suffix = path
        .extension()
        .and_then(|value| value.to_str())
        .unwrap_or_default();

    match suffix {
        "yaml" | "yml" => Ok(serde_yaml::from_str::<Value>(&text)?),
        "json" => Ok(serde_json::from_str::<Value>(&text)?),
        _ => Err(message(format!("Unsupported input file type: .{}", suffix))),
    }
}
