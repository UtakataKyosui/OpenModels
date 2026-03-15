use std::fs;
use std::path::{Path, PathBuf};

use jsonschema::{Draft, JSONSchema};
use serde_json::Value;

use crate::error::{message, Result};

pub fn validate_x_openmodels_schema(extension: &Value) -> Result<()> {
    validate_instance("schemas/x-openmodels.schema.json", extension)
}

pub fn validate_canonical_model_schema(model: &Value) -> Result<()> {
    validate_instance("schemas/canonical-model.schema.json", model)
}

fn validate_instance(schema_relative_path: &str, instance: &Value) -> Result<()> {
    let schema_path = repo_root().join(schema_relative_path);
    let schema = serde_json::from_str::<Value>(&fs::read_to_string(&schema_path)?)?;
    let validator = JSONSchema::options()
        .with_draft(Draft::Draft202012)
        .compile(&schema)
        .map_err(|error| {
            message(format!(
                "Invalid JSON Schema at {}: {error}",
                schema_path.display()
            ))
        })?;

    if let Err(errors) = validator.validate(instance) {
        let message_body = errors
            .map(|error| error.to_string())
            .collect::<Vec<_>>()
            .join("; ");
        return Err(message(format!(
            "JSON Schema validation failed for {}: {}",
            schema_relative_path, message_body
        )));
    }

    Ok(())
}

fn repo_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .expect("repo root")
}
