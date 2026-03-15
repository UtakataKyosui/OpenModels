pub mod adapter;
pub mod drizzle;
pub mod error;
pub mod generate;
pub mod mappers;
pub mod migration;
pub mod model;
pub mod model_io;
pub mod normalize;
pub mod openapi;
pub mod registry;
pub mod schema;
pub mod seaorm;
pub mod utils;
pub mod validate;

pub use adapter::{BackendAdapter, GeneratedFile};
pub use drizzle::generate_drizzle_schema;
pub use error::{OpenModelsError, Result};
pub use generate::{generate_artifacts, generate_artifacts_to_directory, write_generated_files};
pub use mappers::{build_mapper_report, generate_mapper_files, MapperReport};
pub use migration::{plan_migration, MigrationPlan};
pub use model::CanonicalModel;
pub use model_io::load_canonical_model;
pub use normalize::{
    canonical_model_to_pretty_json, canonical_model_to_value, normalize_openapi_document,
};
pub use openapi::{load_openapi_document, write_json_file};
pub use registry::{get_adapter, list_adapters};
pub use schema::{validate_canonical_model_schema, validate_x_openmodels_schema};
pub use validate::{
    validate_canonical_model_semantics, validate_examples, validate_x_openmodels_semantics,
    Diagnostic as ValidationDiagnostic,
};
