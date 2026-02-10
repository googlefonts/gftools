use clap::{ArgAction, Parser};
use gftools::fix_runner;

#[derive(Debug, Parser)]
#[command(version, about, long_about = None)]
/// Set a font's monospace properties.
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
        &["opentype/monospace".to_string()],
    )
    .expect("Failed to fix monospace properties");
}
