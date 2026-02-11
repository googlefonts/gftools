use clap::Parser;
use fontations::read::TableProvider;
use gftools::list_some_things;

#[derive(Debug, Parser)]
#[command(version, about, long_about = None)]
/// Print out vendorId of the fonts
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
                Some(vec![os2_table.ach_vend_id()])
            } else {
                log::warn!("{}: No 'OS/2' table found, skipping", filename);
                None
            }
        },
        &["vendorId"],
        args.csv,
    );
}
