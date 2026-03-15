use crate::error::Result;
use crate::model::{CanonicalModel, JsonObject};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GeneratedFile {
    pub path: String,
    pub content: String,
}

pub trait BackendAdapter: Sync {
    fn key(&self) -> &'static str;
    fn description(&self) -> &'static str;
    fn default_filename(&self) -> &'static str;
    fn generate_files(
        &self,
        canonical_model: &CanonicalModel,
        filename: Option<&str>,
        options: Option<&JsonObject>,
    ) -> Result<Vec<GeneratedFile>>;
}
