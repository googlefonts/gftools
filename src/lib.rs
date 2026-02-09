mod error;
mod push;
mod utils;

use std::{fmt::Display, path::Path};

use error::GftoolsError;
#[allow(unused_imports)]
pub(crate) use gf_metadata::DesignerInfoProto;
pub(crate) use gf_metadata::{AxisProto, FamilyProto};
use tabled::settings::Style;

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

pub fn list_some_things<T: Display>(
    font_files: &[String],
    lister: impl Fn(&str, &fontations::skrifa::FontRef) -> Option<Vec<T>>,
    headers: &[&str],
    csv: bool,
) {
    let mut info: Vec<Vec<String>> = Vec::new();
    for font in font_files.iter() {
        let Ok(font_data) = std::fs::read(font) else {
            log::warn!("{}: Failed to read font file, skipping", font);
            continue;
        };
        let Ok(fontref) = fontations::skrifa::FontRef::new(&font_data) else {
            log::warn!("{}: Failed to parse font file, skipping", font);
            continue;
        };
        if let Some(result) = lister(font, &fontref) {
            info.push(
                std::iter::once(font.to_string())
                    .chain(result.into_iter().map(|x| x.to_string()))
                    .collect::<Vec<String>>(),
            );
        } // list should do its own error reporting
    }
    if csv {
        println!("font,{}", headers.join(","));
        for row in info {
            println!("{}", row.join(","));
        }
    } else {
        let mut builder = tabled::builder::Builder::default();
        builder.push_record(headers.iter().map(|s| s.to_string()));
        for row in info {
            builder.push_record(row);
        }
        let mut table = builder.build();
        table.with(Style::sharp());
        println!("{}", table);
    }
}
