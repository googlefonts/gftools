use clap::{ArgAction, Parser};
use gftools::fix_runner;

#[derive(Debug, Parser)]
#[command(version, about)]
/// Hinted fonts must have head table flag bit 3 set.
///
/// Per https://docs.microsoft.com/en-us/typography/opentype/spec/head,
/// bit 3 of Head::flags decides whether PPEM should be rounded.
/// This bit should always be set for hinted fonts.
/// Note:
/// Bit 3 = Force ppem to integer values for all internal scaler math;
///         May use fractional ppem sizes if this bit is clear;
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
        &["integer_ppem_if_hinted".to_string()],
    )
    .expect("Failed to fix integer ppem if hinted");
}
