use std::io::IsTerminal;

use clap::{ArgAction, Parser};
use gftools::fix_font;

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
    #[clap(short, long)]
    non_interactive: bool,
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
    let interactive = !args.non_interactive && std::io::stdin().is_terminal();
    fix_font(font_path, output_path, include_source_fixes, interactive)
        .expect("Failed to fix font");
}
