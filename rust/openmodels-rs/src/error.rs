use thiserror::Error;

#[derive(Debug, Error)]
pub enum OpenModelsError {
    #[error("{0}")]
    Message(String),
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),
    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),
    #[error("YAML error: {0}")]
    Yaml(#[from] serde_yaml::Error),
}

pub type Result<T> = std::result::Result<T, OpenModelsError>;

pub fn message(message: impl Into<String>) -> OpenModelsError {
    OpenModelsError::Message(message.into())
}
