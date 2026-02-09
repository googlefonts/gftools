mod error;
mod push;
mod utils;

use std::path::Path;

use error::GftoolsError;
#[allow(unused_imports)]
pub(crate) use gf_metadata::DesignerInfoProto;
pub(crate) use gf_metadata::{AxisProto, FamilyProto};

fn parse_metadatapb<T>(path: &Path) -> Result<T, GftoolsError>
where
    T: protobuf::MessageFull,
{
    let meta_file = path.join("METADATA.pb");
    let meta_contents = std::fs::read(meta_file)?;
    let contents = std::str::from_utf8(&meta_contents)
        .map_err(|_| GftoolsError::Misc("METADATA.pb is not valid UTF-8".to_string()))?;
    let data = protobuf::text_format::parse_from_str::<T>(contents)
        .map_err(GftoolsError::ProtobufParse)?;
    Ok(data)
}
