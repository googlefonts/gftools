use clap::Parser;
use fontations::{
    read::TableProvider,
    skrifa::{self},
};
use tabled::{Table, settings::Style};

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

    let mut info: Vec<(String, f32)> = Vec::new();
    for font in args.fonts.iter() {
        let Ok(font_data) = std::fs::read(font) else {
            log::warn!("{}: Failed to read font file, skipping", font);
            continue;
        };
        let Ok(fontref) = skrifa::FontRef::new(&font_data) else {
            log::warn!("{}: Failed to parse font file, skipping", font);
            continue;
        };
        if let Ok(post_table) = fontref.post() {
            info.push((font.to_string(), post_table.italic_angle().to_f32()));
        } else {
            log::warn!("{}: No 'post' table found, skipping", font);
        }
    }
    if args.csv {
        println!("font,italicAngle");
        for (font, angle) in info {
            println!("{},{}", font, angle);
        }
    } else {
        let mut table = Table::new(&info);
        table.with(Style::sharp());
        println!("{}", table);
    }
}
