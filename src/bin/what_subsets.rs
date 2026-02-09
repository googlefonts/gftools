use std::collections::HashSet;

use clap::Parser;
use fontations::{read::FontRef, skrifa::MetadataProvider};

#[derive(Debug, Parser)]
#[command(version, about, long_about = None)]
/// Tool to print subsets supported by a given font file.
struct Args {
    fonts: Vec<String>,
    /// What percentage of subset codepoints have to be supported for a non-ext subset.
    #[clap(long, default_value = "0.01")]
    min_pct: f32,
    /// What percentage of subset codepoints have to be supported for an -ext subset
    #[clap(long)]
    min_pct_ext: Option<f32>,
}

fn main() {
    let args = Args::parse();

    for font_path in args.fonts {
        let Ok(font_data) = std::fs::read(&font_path) else {
            log::warn!("{}: Failed to read font file, skipping", font_path);
            continue;
        };
        let Ok(fontref) = FontRef::new(&font_data) else {
            log::warn!("{}: Failed to parse font file, skipping", font_path);
            continue;
        };
        let codepoints = fontref
            .charmap()
            .mappings()
            .map(|(cp, _gid)| cp)
            .collect::<HashSet<u32>>();
        let subsets =
            google_fonts_subsets::subsets_in_font(&codepoints, args.min_pct, args.min_pct_ext);
        println!("{}: {}", font_path, subsets.join(", "));
    }
}
