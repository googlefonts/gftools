use clap::Parser;
use fontations::{
    read::{FontRef, ReadError, TableProvider, tables::glyf::Glyf},
    types::{GlyphId, Tag},
    write::{
        FontBuilder,
        from_obj::FromTableRef,
        tables::glyf::{GlyfLocaBuilder, Glyph},
    },
};
use gftools::GftoolsError;

#[derive(Parser)]
#[command(version, about)]
/// Drop hints from a font
struct Args {
    input: String,
    /// File to save font
    #[clap(long)]
    output: Option<String>,
}

fn dehinted(font: &FontRef) -> Result<Vec<u8>, GftoolsError> {
    let mut new_font = FontBuilder::new();
    let glyf_table_hinted = any_glyphs_have_instructions(font)?;
    for table in font.table_directory.table_records() {
        let tag = table.tag.get();
        if tag == Tag::new(b"fpgm") || tag == Tag::new(b"prep") || tag == Tag::new(b"cvt ") {
            continue;
        }
        if tag == Tag::new(b"glyf") && glyf_table_hinted {
            let glyf: Glyf = font.glyf()?;
            let loca = font.loca(None)?;
            let glyph_count: u32 = font.maxp()?.num_glyphs().into();
            let mut builder = GlyfLocaBuilder::new();
            let mut owned_glyphs: Vec<Glyph> = (0..glyph_count)
                .map(GlyphId::from)
                .flat_map(|gid| loca.get_glyf(gid, &glyf))
                .flatten()
                .map(|g| Glyph::from_table_ref(&g))
                .collect();
            for glyph in owned_glyphs.iter_mut() {
                if let Glyph::Simple(simple) = &mut *glyph {
                    // Coming to a write-fonts near you soon!
                    // log::warn!("TTF dehinting not yet implemented; upgrade write-fonts");
                    simple.instructions = vec![];
                }
                builder.add_glyph(glyph)?;
            }
            let (glyf, loca, _loca_format) = builder.build();
            new_font.add_table(&glyf)?;
            new_font.add_table(&loca)?;
            continue;
        }
        if let Some(table) = font.table_data(tag) {
            new_font.add_raw(tag, table);
        }
    }
    Ok(new_font.build())
}

fn any_glyphs_have_instructions(font: &FontRef<'_>) -> Result<bool, ReadError> {
    let glyf: Glyf = font.glyf()?;
    let loca = font.loca(None)?;
    let glyph_count: u32 = font.maxp()?.num_glyphs().into();
    Ok((0..glyph_count)
        .map(GlyphId::from)
        .flat_map(|gid| loca.get_glyf(gid, &glyf))
        .flatten()
        .take(100) // Limit to 100 glyphs to avoid performance issues
        .any(|g| match g {
            fontations::read::tables::glyf::Glyph::Simple(simple) => {
                !simple.instructions().is_empty()
            }
            _ => false,
        }))
}

fn main() {
    let args = Args::parse();
    let Ok(font_data) = std::fs::read(&args.input) else {
        log::warn!("{}: Failed to read font file, skipping", args.input);
        return;
    };
    let Ok(fontref) = FontRef::new(&font_data) else {
        log::warn!("{}: Failed to parse font file, skipping", args.input);
        return;
    };
    let output_path = args.output.unwrap_or_else(|| {
        let mut path = std::path::PathBuf::from(&args.input);
        path.set_file_name(format!(
            "{}-dehinted{}",
            path.file_stem().unwrap().to_string_lossy(),
            path.extension()
                .map(|ext| format!(".{}", ext.to_string_lossy()))
                .unwrap_or_default()
        ));
        path.to_string_lossy().into_owned()
    });
    if let Ok(dehinted_data) = dehinted(&fontref) {
        std::fs::write(output_path, dehinted_data).expect("Failed to write dehinted font");
    } else {
        log::warn!("{}: Failed to dehint font, skipping", args.input);
    }
}
