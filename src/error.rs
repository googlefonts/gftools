use thiserror::Error;

#[derive(Error, Debug)]
pub enum GftoolsError {
    #[error("problem parsing font: {0}")]
    FontParse(#[from] fontations::skrifa::raw::ReadError),
    #[error("problem writing font: {0}")]
    FontWrite(#[from] fontations::write::error::Error),
    #[error("problem building font: {0}")]
    FontBuild(#[from] fontations::write::BuilderError),
    #[error("problem parsing JSON: {0}")]
    JsonParse(#[from] serde_json_path_to_error::Error),
    #[error("problem parsing TOML: {0}")]
    TomlParse(#[from] toml::de::Error),
    #[error("problem reading file: {0}")]
    FileRead(#[from] std::io::Error),
    #[error("miscellaneous error: {0}")]
    Misc(String),
    #[error("problem parsing protobuf: {0}")]
    ProtobufParse(#[from] protobuf::text_format::ParseError),
    #[error("HTTP error: {0}")]
    HttpError(#[from] reqwest::Error),
}
