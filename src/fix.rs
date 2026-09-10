use fontspector_hotfix::{apply_hotfixes, Testable};

use crate::GftoolsError;
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum IncludeSourceFixes {
    Yes,
    #[default]
    No,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum Interactive {
    Yes,
    #[default]
    No,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum FixFvarTable {
    #[default]
    Yes,
    No,
}

pub fn fix_font(
    font_path: &str,
    output_path: &str,
    include_source_fixes: IncludeSourceFixes,
    interactive: Interactive,
    fix_fvar_table: FixFvarTable,
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
        // Fix no ps name
        "googlefonts/metadata/valid_nameid25",
        // Fix COLR font
        "googlefonts/color_fonts",
        "empty_glyph_on_gid1_for_colrv0",
        // fix_hhea_caret_slope_run
        "opentype/caret_slope",
    ];
    if let IncludeSourceFixes::Yes = include_source_fixes {
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
    if let FixFvarTable::Yes = fix_fvar_table {
        check_ids.push("googlefonts/fvar_instances");
    }
    let check_ids: Vec<String> = check_ids.into_iter().map(String::from).collect();
    apply_hotfixes(
        &mut font,
        &check_ids,
        matches!(interactive, Interactive::Yes),
    )
    .map_err(|_| GftoolsError::Misc("Failed to apply hotfixes".to_string()))?;
    // Save the fixed font
    std::fs::write(output_path, &font.contents)?;
    Ok(())
}

pub fn fix_runner(
    font_path: &str,
    output_path: &str,
    verbosity: u8,
    check_ids: &[String],
    interactive: bool,
) -> Result<(), GftoolsError> {
    env_logger::Builder::from_env(
        env_logger::Env::default().default_filter_or(match verbosity {
            0 => "warn",
            1 => "info",
            _ => "debug",
        }),
    )
    .init();
    let mut font = Testable::new(font_path)?;
    apply_hotfixes(&mut font, check_ids, interactive)
        .map_err(|_| GftoolsError::Misc("Failed to apply hotfixes".to_string()))?;
    // Save the fixed font
    std::fs::write(output_path, &font.contents)?;
    Ok(())
}
