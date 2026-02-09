use clap::{ArgAction, Parser};
use fontspector_hotfix::{Testable, apply_hotfixes};

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
    // Load font and wrap in a Testable
    let mut font = Testable::new(font_path).expect("Failed to load font");
    apply_hotfixes(&mut font, &["integer_ppem_if_hinted".to_string()])
        .expect("Failed to apply hotfixes");
    // Save the fixed font
    std::fs::write(output_path, &font.contents).expect("Failed to write fixed font");
}
