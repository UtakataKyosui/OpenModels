use std::fs;
use std::path::PathBuf;

use openmodels_rs::{
    canonical_model_to_value, generate_artifacts, generate_artifacts_to_directory,
    generate_drizzle_schema, generate_mapper_files, get_adapter, load_canonical_model,
    load_openapi_document, normalize_openapi_document, plan_migration,
    validate_canonical_model_semantics, validate_examples, validate_x_openmodels_semantics,
    write_generated_files,
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

#[test]
fn loader_rejects_extension_that_violates_json_schema() {
    let temp = tempdir().unwrap();
    let path = temp.path().join("invalid-extension.yaml");
    fs::write(
        &path,
        "openapi: 3.1.0\ninfo:\n  title: Test\n  version: 0.1.0\npaths: {}\nx-openmodels:\n  version: bad\n  entities: {}\n",
    )
    .unwrap();

    let error = load_openapi_document(&path).unwrap_err().to_string();
    assert!(error.contains("JSON Schema validation failed"));
    assert!(error.contains("schemas/x-openmodels.schema.json"));
}

#[test]
fn canonical_loader_rejects_model_that_violates_json_schema() {
    let temp = tempdir().unwrap();
    let path = temp.path().join("invalid-canonical.json");
    fs::write(&path, r#"{"version":"bad","entities":[]}"#).unwrap();

    let error = load_canonical_model(&path).unwrap_err().to_string();
    assert!(error.contains("JSON Schema validation failed"));
    assert!(error.contains("schemas/canonical-model.schema.json"));
}

#[test]
fn migration_planner_matches_existing_snapshot() {
    let root = repo_root();
    let before_model =
        load_canonical_model(root.join("examples/openapi/blog-api-v1.yaml")).unwrap();
    let after_model = load_canonical_model(root.join("examples/openapi/blog-api.yaml")).unwrap();
    let actual = serde_json::to_value(plan_migration(&before_model, &after_model)).unwrap();
    let expected: Value = serde_json::from_str(
        &fs::read_to_string(root.join("examples/migrations/blog-v1-to-v2.json")).unwrap(),
    )
    .unwrap();

    assert_eq!(expected, actual);
}

#[test]
fn migration_planner_covers_branchy_changes_and_warnings() {
    let before_model: openmodels_rs::CanonicalModel = serde_json::from_value(serde_json::json!({
        "version": "0.1",
        "entities": [
            {
                "name": "Alpha",
                "table": "alpha",
                "sourceSchemas": {},
                "fields": [
                    {"name": "id", "storageName": "id", "type": "uuid", "nullable": false, "persisted": true, "generated": "database", "sourceSchemas": {}, "primaryKey": true},
                    {"name": "name", "storageName": "name", "type": "varchar", "nullable": true, "persisted": true, "generated": "none", "sourceSchemas": {}, "length": 20},
                    {"name": "legacy", "storageName": "legacy", "type": "varchar", "nullable": false, "persisted": true, "generated": "none", "sourceSchemas": {}, "length": 50, "default": "legacy"}
                ],
                "relations": [],
                "indexes": [
                    {"name": "alpha_name_idx", "fields": ["name"], "unique": false},
                    {"name": "alpha_unique_idx", "fields": ["name"], "unique": true}
                ],
                "constraints": [
                    {"kind": "check", "name": "alpha_name_check", "expression": "name <> ''"},
                    {"kind": "unique", "name": "alpha_name_unique", "fields": ["name"]},
                    {"kind": "foreignKey", "name": "alpha_fk_multi", "fields": ["name", "legacy"], "references": {"entity": "Gamma", "fields": ["name", "legacy"]}}
                ]
            },
            {
                "name": "Gamma",
                "table": "gamma",
                "sourceSchemas": {},
                "fields": [
                    {"name": "id", "storageName": "id", "type": "uuid", "nullable": false, "persisted": true, "generated": "database", "sourceSchemas": {}, "primaryKey": true},
                    {"name": "name", "storageName": "name", "type": "varchar", "nullable": false, "persisted": true, "generated": "none", "sourceSchemas": {}, "length": 20},
                    {"name": "legacy", "storageName": "legacy", "type": "varchar", "nullable": false, "persisted": true, "generated": "none", "sourceSchemas": {}, "length": 20}
                ],
                "relations": [],
                "indexes": [],
                "constraints": []
            },
            {
                "name": "DropMe",
                "table": "drop_me",
                "sourceSchemas": {},
                "fields": [
                    {"name": "id", "storageName": "id", "type": "uuid", "nullable": false, "persisted": true, "generated": "database", "sourceSchemas": {}, "primaryKey": true}
                ],
                "relations": [],
                "indexes": [],
                "constraints": []
            }
        ]
    }))
    .unwrap();
    let after_model: openmodels_rs::CanonicalModel = serde_json::from_value(serde_json::json!({
        "version": "0.2",
        "entities": [
            {
                "name": "Alpha",
                "table": "alpha_new",
                "sourceSchemas": {},
                "fields": [
                    {"name": "id", "storageName": "id", "type": "uuid", "nullable": false, "persisted": true, "generated": "database", "sourceSchemas": {}, "primaryKey": true},
                    {"name": "name", "storageName": "name_v2", "type": "text", "nullable": false, "persisted": true, "generated": "none", "sourceSchemas": {}, "length": 10},
                    {"name": "requiredField", "storageName": "required_field", "type": "integer", "nullable": false, "persisted": true, "generated": "none", "sourceSchemas": {}}
                ],
                "relations": [],
                "indexes": [
                    {"name": "alpha_name_idx", "fields": ["name", "requiredField"], "unique": false},
                    {"name": "alpha_new_idx", "fields": ["requiredField"], "unique": false}
                ],
                "constraints": [
                    {"kind": "check", "name": "alpha_name_check", "expression": "char_length(name_v2) > 0"},
                    {"kind": "foreignKey", "name": "alpha_fk_multi", "fields": ["name", "requiredField"], "references": {"entity": "Gamma", "fields": ["name", "legacy"]}},
                    {"kind": "primaryKey", "name": "alpha_pk", "fields": ["id"]}
                ]
            },
            {
                "name": "Gamma",
                "table": "gamma",
                "sourceSchemas": {},
                "fields": [
                    {"name": "id", "storageName": "id", "type": "uuid", "nullable": false, "persisted": true, "generated": "database", "sourceSchemas": {}, "primaryKey": true},
                    {"name": "name", "storageName": "name", "type": "varchar", "nullable": false, "persisted": true, "generated": "none", "sourceSchemas": {}, "length": 20},
                    {"name": "legacy", "storageName": "legacy", "type": "varchar", "nullable": false, "persisted": true, "generated": "none", "sourceSchemas": {}, "length": 20}
                ],
                "relations": [],
                "indexes": [],
                "constraints": []
            },
            {
                "name": "Beta",
                "table": "beta",
                "sourceSchemas": {},
                "fields": [
                    {"name": "id", "storageName": "id", "type": "uuid", "nullable": false, "persisted": true, "generated": "database", "sourceSchemas": {}, "primaryKey": true},
                    {"name": "value", "storageName": "value", "type": "varchar", "nullable": false, "persisted": true, "generated": "none", "sourceSchemas": {}, "length": 20, "default": "x"}
                ],
                "relations": [],
                "indexes": [],
                "constraints": []
            }
        ]
    }))
    .unwrap();

    let plan = plan_migration(&before_model, &after_model);
    let change_kinds = plan
        .changes
        .iter()
        .filter_map(|change| change.get("kind").and_then(Value::as_str))
        .collect::<std::collections::HashSet<_>>();
    let warning_codes = plan
        .warnings
        .iter()
        .map(|warning| warning.code.as_str())
        .collect::<std::collections::HashSet<_>>();

    assert!(change_kinds.is_superset(&std::collections::HashSet::from([
        "createTable",
        "dropTable",
        "renameTable",
        "addColumn",
        "dropColumn",
        "alterColumn",
        "addIndex",
        "dropIndex",
        "alterIndex",
        "addConstraint",
        "dropConstraint",
        "alterConstraint",
    ])));
    assert!(warning_codes.is_superset(&std::collections::HashSet::from([
        "drop-table",
        "rename-table",
        "add-required-column-without-default",
        "drop-column",
        "change-column-type",
        "rename-column",
        "tighten-nullability",
        "shrink-column-length",
    ])));
    assert_eq!("0.1", plan.from_model_version);
    assert_eq!("0.2", plan.to_model_version);
    assert!(plan.summary.destructive_changes >= 3);
    assert!(plan.summary.warnings >= 8);
}

#[test]
fn mapper_generator_matches_existing_snapshots() {
    let root = repo_root();
    let document = load_openapi_document(root.join("examples/openapi/blog-api.yaml")).unwrap();
    let canonical = normalize_openapi_document(&document).unwrap();
    let generated = generate_mapper_files(&document.raw, &canonical, None, None).unwrap();
    let generated = generated
        .iter()
        .map(|file| (file.path.as_str(), file.content.as_str()))
        .collect::<std::collections::HashMap<_, _>>();

    assert_eq!(
        fs::read_to_string(root.join("examples/generated/blog-dto-mappers.ts")).unwrap(),
        generated["dto-mappers.ts"]
    );
    assert_eq!(
        fs::read_to_string(root.join("examples/generated/blog-dto-mappers.diagnostics.json"))
            .unwrap(),
        generated["dto-mappers.diagnostics.json"]
    );
}

#[test]
fn mapper_generator_writes_custom_filenames() {
    let root = repo_root();
    let document = load_openapi_document(root.join("examples/openapi/blog-api.yaml")).unwrap();
    let canonical = normalize_openapi_document(&document).unwrap();
    let generated = generate_mapper_files(
        &document.raw,
        &canonical,
        Some("mappers.ts"),
        Some("mappers.json"),
    )
    .unwrap();
    let out_dir = tempdir().unwrap();
    let written = write_generated_files(&generated, out_dir.path()).unwrap();

    assert_eq!(
        vec![
            out_dir.path().join("mappers.ts"),
            out_dir.path().join("mappers.json")
        ],
        written
    );
}

#[test]
fn validate_examples_passes_for_current_fixtures() {
    let diagnostics = validate_examples().unwrap();
    assert!(diagnostics.is_empty());
}

#[test]
fn x_openmodels_semantics_reports_unknown_enum() {
    let root = repo_root();
    let mut document = load_openapi_document(root.join("examples/openapi/blog-api.yaml")).unwrap();
    document.raw["x-openmodels"]["entities"]["Post"]["fields"]["status"]["enum"] =
        Value::String(String::from("MissingStatus"));

    let diagnostics = validate_x_openmodels_semantics(&document.raw["x-openmodels"]);
    assert_eq!(
        vec!["unknown-enum"],
        diagnostics
            .iter()
            .map(|item| item.code.as_str())
            .collect::<Vec<_>>()
    );
}

#[test]
fn canonical_semantics_report_reference_problems() {
    let root = repo_root();
    let mut model = load_canonical_model(root.join("examples/canonical/blog-model.json")).unwrap();
    model.entities[1].relations[0].foreign_key = Some(String::from("missingField"));
    model.entities[1].relations[0].references = Some(String::from("missingField"));
    model.entities[1].constraints[0]
        .references
        .as_mut()
        .unwrap()
        .entity = String::from("MissingUser");

    let diagnostics = validate_canonical_model_semantics(&model);
    let codes = diagnostics
        .iter()
        .map(|item| item.code.as_str())
        .collect::<std::collections::HashSet<_>>();

    assert!(codes.contains("unknown-foreign-key-field"));
    assert!(codes.contains("unknown-reference-field"));
    assert!(codes.contains("unknown-constraint-target"));
}

#[test]
fn drizzle_rejects_non_string_enum_values() {
    let model: openmodels_rs::CanonicalModel = serde_json::from_value(serde_json::json!({
        "version": "0.1",
        "enums": [
            {
                "name": "StatusCode",
                "sourceSchemas": {},
                "values": [1, 2]
            }
        ],
        "entities": [
            {
                "name": "Thing",
                "table": "things",
                "sourceSchemas": {},
                "fields": [
                    {
                        "name": "status",
                        "storageName": "status",
                        "type": "varchar",
                        "nullable": false,
                        "persisted": true,
                        "generated": "none",
                        "enum": "StatusCode",
                        "sourceSchemas": {}
                    }
                ],
                "relations": [],
                "indexes": [],
                "constraints": []
            }
        ]
    }))
    .unwrap();

    let error = generate_drizzle_schema(&model).unwrap_err().to_string();
    assert!(error.contains("requires string values"));
}

#[test]
fn seaorm_rejects_non_string_enum_values() {
    let model: openmodels_rs::CanonicalModel = serde_json::from_value(serde_json::json!({
        "version": "0.1",
        "enums": [
            {
                "name": "StatusCode",
                "sourceSchemas": {},
                "values": [1, 2]
            }
        ],
        "entities": [
            {
                "name": "Thing",
                "table": "things",
                "sourceSchemas": {},
                "fields": [
                    {
                        "name": "id",
                        "storageName": "id",
                        "type": "uuid",
                        "nullable": false,
                        "persisted": true,
                        "generated": "database",
                        "sourceSchemas": {},
                        "primaryKey": true
                    },
                    {
                        "name": "status",
                        "storageName": "status",
                        "type": "varchar",
                        "nullable": false,
                        "persisted": true,
                        "generated": "none",
                        "enum": "StatusCode",
                        "sourceSchemas": {}
                    }
                ],
                "relations": [],
                "indexes": [],
                "constraints": []
            }
        ]
    }))
    .unwrap();

    let error = generate_artifacts(&model, Some("seaorm-rust"), None)
        .unwrap_err()
        .to_string();
    assert!(error.contains("requires string values"));
}

#[test]
fn seaorm_reports_missing_target_entity_without_panicking() {
    let model: openmodels_rs::CanonicalModel = serde_json::from_value(serde_json::json!({
        "version": "0.1",
        "entities": [
            {
                "name": "Thing",
                "table": "things",
                "sourceSchemas": {},
                "fields": [
                    {
                        "name": "id",
                        "storageName": "id",
                        "type": "uuid",
                        "nullable": false,
                        "persisted": true,
                        "generated": "database",
                        "sourceSchemas": {},
                        "primaryKey": true
                    }
                ],
                "relations": [
                    {
                        "name": "owner",
                        "kind": "belongsTo",
                        "targetEntity": "User",
                        "ownership": "owner",
                        "foreignKey": "ownerId",
                        "references": "id"
                    }
                ],
                "indexes": [],
                "constraints": []
            }
        ]
    }))
    .unwrap();

    let error = generate_artifacts(&model, Some("seaorm-rust"), None)
        .unwrap_err()
        .to_string();
    assert!(error.contains("Unknown target entity 'User'."));
}
