use clap::{Args, Parser};
use fontations::skrifa::{FontRef, MetadataProvider, prelude::*};
use tabled::{Table, Tabled, settings::Style};

#[derive(Args)]
#[group(required = true, multiple = false)]
struct Mode {
    #[arg(long)]
    glyphs: bool,

    #[arg(long)]
    family: bool,
}

#[derive(Parser)]
#[command(version, about)]
/// A Rust utility for printing bounding boxes to stdout.
///
/// Users can either check a collection of fonts bounding boxes (--family) or
/// the bounding box for each glyph in the collection of fonts (--glyphs).
struct CheckBboxArgs {
    fonts: Vec<String>,
    /// Output data in comma-separated-values format
    #[clap(long)]
    csv: bool,
    /// Print extremes coordinates for each category
    #[clap(long)]
    extremes: bool,
    #[clap(flatten)]
    mode: Mode,
}

#[derive(Tabled)]
struct Row {
    font: String,
    glyph: String,
    x_min: i32,
    y_min: i32,
    x_max: i32,
    y_max: i32,
}
impl Row {
    fn new(font: String, glyph: String, x_min: i32, y_min: i32, x_max: i32, y_max: i32) -> Self {
        Self {
            font,
            glyph,
            x_min,
            y_min,
            x_max,
            y_max,
        }
    }
}
fn main() {
    let args = CheckBboxArgs::parse();
    let mut rows = vec![];
    for font in args.fonts {
        let Ok(font_data) = std::fs::read(&font) else {
            log::warn!("{}: Failed to read font file, skipping", font);
            continue;
        };
        let Ok(fontref) = FontRef::new(&font_data) else {
            log::warn!("{}: Failed to parse font file, skipping", font);
            continue;
        };
        let metrics = fontref.metrics(Size::unscaled(), LocationRef::default());
        let global_bounds = metrics.bounds.unwrap_or_default();
        let max_glyph = metrics.glyph_count;
        if args.mode.glyphs {
            let glyph_metrics = fontref.glyph_metrics(Size::unscaled(), LocationRef::default());
            let glyph_names = fontref.glyph_names();
            for glyph_id in 0..max_glyph {
                let glyph_id = GlyphId::from(glyph_id);
                let bounds = glyph_metrics.bounds(glyph_id).unwrap_or_default();
                rows.push(Row::new(
                    font.clone(),
                    glyph_names
                        .get(glyph_id)
                        .map(|x| x.to_string())
                        .unwrap_or(format!("gid{}", glyph_id)),
                    bounds.x_min as i32,
                    bounds.y_min as i32,
                    bounds.x_max as i32,
                    bounds.y_max as i32,
                ));
            }
        } else {
            rows.push(Row::new(
                font.clone(),
                "family".to_string(),
                global_bounds.x_min as i32,
                global_bounds.y_min as i32,
                global_bounds.x_max as i32,
                global_bounds.y_max as i32,
            ));
        }
    }

    if args.extremes {
        let x_min = rows.iter().map(|x| x.x_min).min().unwrap_or_default();
        let y_min = rows.iter().map(|x| x.y_min).min().unwrap_or_default();
        let x_max = rows.iter().map(|x| x.x_max).max().unwrap_or_default();
        let y_max = rows.iter().map(|x| x.y_max).max().unwrap_or_default();
        rows = vec![Row::new(
            "extremes".to_string(),
            "".to_string(),
            x_min,
            y_min,
            x_max,
            y_max,
        )];
    }

    if args.csv {
        for data in rows {
            println!(
                "{},{},{},{},{},{}",
                data.font, data.glyph, data.x_min, data.y_min, data.x_max, data.y_max
            );
        }
    } else {
        let mut table = Table::new(&rows);
        table.with(Style::sharp());
        println!("{}", table);
    }
}
