use clap::{ArgAction, Parser};
use fontations::{
    read::tables::gasp::GaspRangeBehavior,
    skrifa::{FontRef, raw::TableProvider},
    write::FontBuilder,
};
use fontspector_hotfix::{Testable, apply_hotfixes};

#[derive(Debug, Parser)]
#[command(version, about)]
/// Fixes TTF GASP table
struct Args {
    /// Path to the font file to be fixed
    font_path: String,
    /// Path to save the fixed font file
    #[clap(long, short = 'o')]
    output_path: String,
    /// Verbosity level (can be increased with multiple -v)
    #[clap(short, long, action = ArgAction::Count)]
    verbosity: u8,
    /// Apply autofix
    #[clap(long)]
    autofix: bool,
    /// Change gasprange value of key 65535 to new value
    #[clap(long)]
    set: Option<u16>,
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
    if args.autofix {
        let mut font = Testable::new(&args.font_path).expect("Failed to load font");
        apply_hotfixes(&mut font, &["googlefonts/gasp".to_string()], false)
            .expect("Failed to apply hotfixes");
        std::fs::write(args.output_path, &font.contents).expect("Failed to save fixed font");
        return;
    }
    let Ok(font_data) = std::fs::read(&args.font_path) else {
        log::warn!("{}: Failed to read font file, skipping", args.font_path);
        return;
    };
    let Ok(fontref) = FontRef::new(&font_data) else {
        log::warn!("{}: Failed to parse font file, skipping", args.font_path);
        return;
    };
    if let Some(new_value) = args.set {
        let new_gasp = fontations::write::tables::gasp::Gasp {
            version: 0,
            gasp_ranges: vec![fontations::write::tables::gasp::GaspRange {
                range_max_ppem: 0xFFFF,
                range_gasp_behavior: GaspRangeBehavior::from_bits(new_value).unwrap_or_else(|| {
                    eprintln!("Invalid GASP behavior value: {}. It should be a valid combination of GaspRangeBehavior flags.", new_value);
                    std::process::exit(1);
                }),
            }],
            num_ranges: 1,
        };
        let mut new_font = FontBuilder::new();
        new_font
            .add_table(&new_gasp)
            .expect("Failed to add GASP table");
        new_font.copy_missing_tables(fontref);
        let new_font_data = new_font.build();

        std::fs::write(args.output_path, new_font_data).expect("Failed to save fixed font");
    } else {
        let Ok(gasp_table) = fontref.gasp() else {
            eprintln!("GASP table not found in the font.");
            return;
        };
        // Just show
        gasp_table
            .gasp_ranges()
            .iter()
            .find(|x| x.range_max_ppem() == 65535)
            .map(|x| {
                println!(
                    "Current gasprange value for key 65535: {:?}",
                    x.range_gasp_behavior()
                );
            })
            .unwrap_or_else(|| {
                eprintln!("GASPRANGE with key 65535 not found in the GASP table.");
            });
    }
}
