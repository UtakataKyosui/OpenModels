use std::fs;
use std::path::PathBuf;

use openmodels_rs::{
    canonical_model_to_value, generate_drizzle_schema, load_openapi_document,
    normalize_openapi_document,
};
use serde_json::Value;
use tempfile::tempdir;

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .expect("repo root")
}

#[test]
fn normalizes_blog_fixture_to_existing_canonical_snapshot() {
    let root = repo_root();
    let loaded = load_openapi_document(root.join("examples/openapi/blog-api.yaml")).unwrap();
    let canonical = normalize_openapi_document(&loaded).unwrap();
    let actual = canonical_model_to_value(&canonical).unwrap();
    let expected: Value = serde_json::from_str(
        &fs::read_to_string(root.join("examples/canonical/blog-model.json")).unwrap(),
    )
    .unwrap();

    assert_eq!(expected, actual);
}

#[test]
fn generates_blog_drizzle_snapshot() {
    let root = repo_root();
    let loaded = load_openapi_document(root.join("examples/openapi/blog-api.yaml")).unwrap();
    let canonical = normalize_openapi_document(&loaded).unwrap();
    let actual = generate_drizzle_schema(&canonical).unwrap();
    let expected = fs::read_to_string(root.join("examples/generated/blog-schema.ts")).unwrap();

    assert_eq!(expected, actual);
}

#[test]
fn loader_rejects_missing_openmodels_extension() {
    let temp = tempdir().unwrap();
    let path = temp.path().join("missing.yaml");
    fs::write(
        &path,
        "openapi: 3.1.0\ninfo:\n  title: Test\n  version: 0.1.0\npaths: {}\n",
    )
    .unwrap();

    let error = load_openapi_document(&path).unwrap_err().to_string();
    assert!(error.contains("x-openmodels"));
}

#[test]
fn loader_rejects_unsupported_openapi_version() {
    let temp = tempdir().unwrap();
    let path = temp.path().join("unsupported.yaml");
    fs::write(
        &path,
        "openapi: 2.0.0\ninfo:\n  title: Test\n  version: 0.1.0\npaths: {}\nx-openmodels:\n  version: \"0.1\"\n  entities: {}\n",
    )
    .unwrap();

    let error = load_openapi_document(&path).unwrap_err().to_string();
    assert!(error.contains("Unsupported OpenAPI version"));
}
