use std::fs;
use std::path::PathBuf;

use openmodels_rs::{
    canonical_model_to_value, generate_artifacts, generate_artifacts_to_directory,
    generate_drizzle_schema, get_adapter, load_openapi_document, normalize_openapi_document,
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
fn registry_exposes_drizzle_target() {
    let adapter = get_adapter("drizzle-pg").unwrap();

    assert_eq!("drizzle-pg", adapter.key());
    assert_eq!("schema.ts", adapter.default_filename());
}

#[test]
fn registry_exposes_seaorm_target() {
    let adapter = get_adapter("seaorm-rust").unwrap();

    assert_eq!("seaorm-rust", adapter.key());
    assert_eq!("entity/mod.rs", adapter.default_filename());
}

#[test]
fn generic_generation_supports_target_override_and_writes_output() {
    let root = repo_root();
    let loaded = load_openapi_document(root.join("examples/openapi/blog-api.yaml")).unwrap();
    let canonical = normalize_openapi_document(&loaded).unwrap();

    let generated_files =
        generate_artifacts(&canonical, Some("drizzle-pg"), Some("blog-schema.ts")).unwrap();
    assert_eq!(1, generated_files.len());
    assert_eq!("blog-schema.ts", generated_files[0].path);
    assert_eq!(
        fs::read_to_string(root.join("examples/generated/blog-schema.ts")).unwrap(),
        generated_files[0].content
    );

    let out_dir = tempdir().unwrap();
    let written = generate_artifacts_to_directory(
        root.join("examples/openapi/blog-api.yaml"),
        out_dir.path(),
        Some("drizzle-pg"),
        Some("schema.ts"),
    )
    .unwrap();
    assert_eq!(vec![out_dir.path().join("schema.ts")], written);
}

#[test]
fn generates_blog_seaorm_snapshots() {
    let root = repo_root();
    let loaded = load_openapi_document(root.join("examples/openapi/blog-api.yaml")).unwrap();
    let canonical = normalize_openapi_document(&loaded).unwrap();
    let generated_files = generate_artifacts(&canonical, Some("seaorm-rust"), None).unwrap();
    let generated = generated_files
        .iter()
        .map(|file| (file.path.as_str(), file.content.as_str()))
        .collect::<std::collections::HashMap<_, _>>();

    assert_eq!(4, generated.len());
    assert_eq!(
        fs::read_to_string(root.join("examples/generated/seaorm-entity/entity/mod.rs")).unwrap(),
        generated["entity/mod.rs"]
    );
    assert_eq!(
        fs::read_to_string(root.join("examples/generated/seaorm-entity/entity/prelude.rs"))
            .unwrap(),
        generated["entity/prelude.rs"]
    );
    assert_eq!(
        fs::read_to_string(root.join("examples/generated/seaorm-entity/entity/post.rs")).unwrap(),
        generated["entity/post.rs"]
    );
    assert_eq!(
        fs::read_to_string(root.join("examples/generated/seaorm-entity/entity/user.rs")).unwrap(),
        generated["entity/user.rs"]
    );
}

#[test]
fn declared_outputs_generate_drizzle_and_seaorm_artifacts() {
    let root = repo_root();
    let loaded = load_openapi_document(root.join("examples/openapi/blog-api.yaml")).unwrap();
    let canonical = normalize_openapi_document(&loaded).unwrap();

    let generated = generate_artifacts(&canonical, None, None).unwrap();
    let paths = generated
        .iter()
        .map(|file| file.path.as_str())
        .collect::<Vec<_>>();

    assert_eq!(
        vec![
            "blog-schema.ts",
            "seaorm-entity/mod.rs",
            "seaorm-entity/prelude.rs",
            "seaorm-entity/post.rs",
            "seaorm-entity/user.rs",
        ],
        paths
    );
}

#[test]
fn generic_generation_rejects_multi_output_filename_override() {
    let root = repo_root();
    let loaded = load_openapi_document(root.join("examples/openapi/blog-api.yaml")).unwrap();
    let mut canonical = normalize_openapi_document(&loaded).unwrap();
    canonical.outputs = Some(vec![
        openmodels_rs::model::Output {
            target: String::from("drizzle-pg"),
            filename: Some(String::from("schema-a.ts")),
            options: None,
        },
        openmodels_rs::model::Output {
            target: String::from("drizzle-pg"),
            filename: Some(String::from("schema-b.ts")),
            options: None,
        },
    ]);

    let error = generate_artifacts(&canonical, None, Some("override.ts"))
        .unwrap_err()
        .to_string();
    assert!(error.contains("filename override"));
}

#[test]
fn seaorm_rejects_filename_override() {
    let root = repo_root();
    let loaded = load_openapi_document(root.join("examples/openapi/blog-api.yaml")).unwrap();
    let canonical = normalize_openapi_document(&loaded).unwrap();

    let error = generate_artifacts(&canonical, Some("seaorm-rust"), Some("entity.rs"))
        .unwrap_err()
        .to_string();
    assert!(error.contains("fixed multi-file layout"));
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
