use clap::{ArgAction, Parser};
use gftools::fix_runner;

#[derive(Debug, Parser)]
#[command(version, about)]
/// Update a collection of fonts fsType value to Installable Embedding.
///
/// Google Fonts requires Installable Embedding (0):
/// https://googlefonts.github.io/gf-guide/requirements.html#font-embedding-fstype
///
/// Microsoft OpenType specification:
/// https://www.microsoft.com/typography/otspec/os2.htm#fst
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
        &["googlefonts/fstype".to_string()],
    )
    .expect("Failed to fix fstype");
}
