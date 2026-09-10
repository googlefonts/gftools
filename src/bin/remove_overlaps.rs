use clap::Parser;
use gftools::remove_overlaps;

#[derive(Debug, Parser)]
#[command(version, about, long_about = None)]
/// Remove overlaps from a font
struct Args {
    font_path: String,
    #[clap(long, short = 'o')]
    output_path: String,
}

fn main() {
    let args = Args::parse();
    let font_data = std::fs::read(&args.font_path).expect("Failed to read font file");
    remove_overlaps(&font_data)
        .and_then(|new_font_data| {
            std::fs::write(&args.output_path, new_font_data).map_err(|e| {
                gftools::GftoolsError::Misc(format!("Failed to write output font: {}", e))
            })
        })
        .expect("Failed to remove overlaps from font");
}
