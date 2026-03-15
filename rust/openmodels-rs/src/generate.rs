use std::fs;
use std::path::{Path, PathBuf};

use crate::adapter::GeneratedFile;
use crate::error::{Result, message};
use crate::model::{CanonicalModel, Output};
use crate::normalize::normalize_openapi_document;
use crate::openapi::load_openapi_document;
use crate::registry::get_adapter;

pub const DEFAULT_TARGET: &str = "drizzle-pg";
pub const DEFAULT_FILENAME: &str = "schema.ts";

pub fn generate_artifacts(
    canonical_model: &CanonicalModel,
    target: Option<&str>,
    filename: Option<&str>,
) -> Result<Vec<GeneratedFile>> {
    if let Some(target) = target {
        let adapter = get_adapter(target)?;
        return adapter.generate_files(canonical_model, filename, None);
    }

    let outputs = if let Some(outputs) = &canonical_model.outputs {
        if outputs.is_empty() {
            vec![default_output()]
        } else {
            outputs.clone()
        }
    } else {
        vec![default_output()]
    };

    if filename.is_some() && outputs.len() != 1 {
        return Err(message(
            "A filename override can only be used when a single output target is selected.",
        ));
    }

    let mut generated_files = Vec::new();
    for output in &outputs {
        let adapter = get_adapter(&output.target)?;
        generated_files.extend(adapter.generate_files(
            canonical_model,
            filename.or(output.filename.as_deref()),
            output.options.as_ref(),
        )?);
    }

    Ok(generated_files)
}

pub fn write_generated_files(
    generated_files: &[GeneratedFile],
    out_dir: impl AsRef<Path>,
) -> Result<Vec<PathBuf>> {
    let out_dir = out_dir.as_ref();
    fs::create_dir_all(out_dir)?;
    let mut written_paths = Vec::new();

    for generated_file in generated_files {
        let target_path = out_dir.join(&generated_file.path);
        if let Some(parent) = target_path.parent() {
            fs::create_dir_all(parent)?;
        }
        fs::write(&target_path, &generated_file.content)?;
        written_paths.push(target_path);
    }

    Ok(written_paths)
}

pub fn generate_artifacts_to_directory(
    input_path: impl AsRef<Path>,
    out_dir: impl AsRef<Path>,
    target: Option<&str>,
    filename: Option<&str>,
) -> Result<Vec<PathBuf>> {
    let document = load_openapi_document(input_path)?;
    let canonical_model = normalize_openapi_document(&document)?;
    let generated_files = generate_artifacts(&canonical_model, target, filename)?;
    write_generated_files(&generated_files, out_dir)
}

fn default_output() -> Output {
    Output {
        target: String::from(DEFAULT_TARGET),
        filename: Some(String::from(DEFAULT_FILENAME)),
        options: None,
    }
}
