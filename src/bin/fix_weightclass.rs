use clap::{ArgAction, Parser};
use gftools::fix_runner;

#[derive(Debug, Parser)]
#[command(version, about, long_about = None)]
/// Set a font's OS/2 usWeightClass value so it conforms to the Google Fonts specification.
///
/// The font's style name in the name record is used to determine the correct value.
struct Args {
    font_path: String,
    #[clap(long, short = 'o')]
    output_path: String,
    #[clap(short, long, action = ArgAction::Count)]
    verbosity: u8,
}

fn main() {
    let args = Args::parse();
    fix_runner(
        &args.font_path,
        &args.output_path,
        args.verbosity,
        &["googlefonts/weightclass".to_string()],
        false,
    )
    .expect("Failed to fix weight class");
}
