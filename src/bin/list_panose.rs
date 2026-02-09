use clap::Parser;
use fontations::read::TableProvider;
use gftools::list_some_things;

#[derive(Debug, Parser)]
#[command(version, about, long_about = None)]
/// Print out Panose of the fonts
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
                let panose = os2_table.panose_10();
                Some(vec![
                    panose[0], panose[1], panose[2], panose[3], panose[4], panose[5], panose[6],
                    panose[7], panose[8], panose[9],
                ])
            } else {
                log::warn!("{}: No 'OS/2' table found, skipping", filename);
                None
            }
        },
        &[
            "bFamilyType",
            "bSerifStyle",
            "bWeight",
            "bProportion",
            "bContrast",
            "bStrokeVariation",
            "bArmStyle",
            "bLetterform",
            "bMidline",
            "bXHeight",
        ],
        args.csv,
    );
}
