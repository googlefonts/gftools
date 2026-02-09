use clap::Parser;
use fontations::read::TableProvider;
use gftools::list_some_things;

#[derive(Debug, Parser)]
#[command(version, about, long_about = None)]
/// Print out italicAngle of the fonts
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
            if let Ok(post_table) = fontref.post() {
                Some(vec![post_table.italic_angle().to_f32()])
            } else {
                log::warn!("{}: No 'post' table found, skipping", filename);
                None
            }
        },
        &["italicAngle"],
        args.csv,
    );
}
