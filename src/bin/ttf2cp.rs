use std::collections::BTreeSet;

use clap::Parser;
use fontations::{read::FontRef, skrifa::MetadataProvider};

#[derive(Debug, Parser)]
#[command(version, about, long_about = None)]
/// Utility to dump codepoints in a font.
///
/// Prints codepoints supported by the font, one per line, in hex (0xXXXX).
struct Args {
    fonts: Vec<String>,
    /// Print the actual character
    show_char: bool,
    /// Print what subsets, if any, char is in
    show_subsets: bool,
}

fn main() {
    let args = Args::parse();
    let mut codepoints = BTreeSet::new();
    for font_path in args.fonts {
        let Ok(font_data) = std::fs::read(&font_path) else {
            log::warn!("{}: Failed to read font file, skipping", font_path);
            continue;
        };
        let Ok(fontref) = FontRef::new(&font_data) else {
            log::warn!("{}: Failed to parse font file, skipping", font_path);
            continue;
        };
        codepoints.extend(fontref.charmap().mappings().map(|(cp, _gid)| cp))
    }
    for cp in codepoints {
        let the_char = char::from_u32(cp).unwrap_or('\u{FFFD}');
        let show_char_arg = if args.show_char {
            format!(
                " {} {}",
                the_char,
                unicode_names2::name(the_char)
                    .map(|x| x.to_string())
                    .unwrap_or("UNKNOWN".to_string())
            )
        } else {
            "".to_string()
        };
        let show_subsets_arg = if args.show_subsets {
            let subsets = google_fonts_subsets::subsets_for_codepoint(cp).collect::<Vec<_>>();
            format!(" {}", subsets.join(", "))
        } else {
            "".to_string()
        };

        println!("0x{:04X}{}{}", cp, show_char_arg, show_subsets_arg);
    }
}
