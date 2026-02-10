mod error;
mod push;
mod utils;

use std::{fmt::Display, path::Path};

pub use error::GftoolsError;
use fontspector_hotfix::{Testable, apply_hotfixes};
// Have to make this pub so our scripts can use it
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

pub fn fix_font(
    font_path: &str,
    output_path: &str,
    include_source_fixes: bool,
) -> Result<(), GftoolsError> {
    // Load font and wrap in a Testable
    let mut font = Testable::new(font_path).expect("Failed to load font");
    let mut check_ids = vec![
        // fix license strings
        // "name/license",
        // "name/license_url",
        // Fix hinted font
        "integer_ppem_if_hinted",
        // Fix unhinted font
        "googlefonts/gasp",
        // Fix no ps anme
        "googlefonts/metadata/valid_nameid25",
        // Fix COLR font
        "googlefonts/color_fonts",
        "empty_glyph_on_gid1_for_colrv0",
        // fix_hhea_caret_slope_run
        "opentype/caret_slope",
    ];
    if include_source_fixes {
        check_ids.extend([
            // remove tables
            "unwanted_tables",
            // fix nametable,
            "googlefonts/font_names",
            // fix FS type
            "googlefonts/fstype",
            // fix FS selection
            "googlefonts/use_typo_metrics",
            "opentype/fsselection",
            // Fix mac style
            "opentype/mac_style",
            // fix weight class
            "googlefonts/weightclass",
            // fix italic angle
            "opentype/italic_angle",
        ]);
    }
    let check_ids: Vec<String> = check_ids.into_iter().map(String::from).collect();
    apply_hotfixes(&mut font, &check_ids)
        .map_err(|_| GftoolsError::Misc("Failed to apply hotfixes".to_string()))?;
    // Save the fixed font
    std::fs::write(output_path, &font.contents)?;
    Ok(())
}
