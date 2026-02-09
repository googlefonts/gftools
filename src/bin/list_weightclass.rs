use clap::Parser;
use fontations::read::TableProvider;
use gftools::list_some_things;

#[derive(Debug, Parser)]
#[command(version, about, long_about = None)]
/// Print out usWeightClass of the fonts
struct Args {
    fonts: Vec<String>,
    #[clap(long)]
    csv: bool,
}

fn main() {
    let args = Args::parse();
    list_some_things(
        &args.fonts,
        |filename, fontref| {
            if let Ok(os2_table) = fontref.os2() {
                Some(vec![os2_table.us_weight_class()])
            } else {
                log::warn!("{}: No 'post' table found, skipping", filename);
                None
            }
        },
        &["italicAngle"],
        args.csv,
    );
}
