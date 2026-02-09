use clap::{ArgAction, Parser};
use fontspector_hotfix::{Testable, apply_hotfixes};

#[derive(Debug, Parser)]
#[command(version, about, long_about = None)]
/// Update a font so it conforms to the Google Fonts specification
struct Args {
    font_path: String,
    #[clap(long, short = 'o')]
    output_path: String,
    #[clap(long)]
    include_source_fixes: bool,
    #[clap(short, long, action = ArgAction::Count)]
    verbosity: u8,
}

fn main() {
    let args = Args::parse();
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or(
        match args.verbosity {
            0 => "warn",
            1 => "info",
            _ => "debug",
        },
    ))
    .init();
    let font_path = &args.font_path;
    let output_path = &args.output_path;
    let include_source_fixes = args.include_source_fixes;
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
    apply_hotfixes(&mut font, &check_ids).expect("Failed to apply hotfixes");
    // Save the fixed font
    std::fs::write(output_path, &font.contents).expect("Failed to write fixed font");
}
