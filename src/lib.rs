mod error;
// mod push;
mod fix;
mod names;
mod utils;

pub use fix::{fix_font, fix_runner, FixFvarTable, IncludeSourceFixes, Interactive};
use kurbo::{BezPath, Point};
use linesweeper::{binary_op, BinaryOp, FillRule};
use skrifa::{
    raw::{tables::glyf::CurvePoint, TableProvider},
    GlyphId,
};
use std::{fmt::Display, path::Path};
use write_fonts::{
    from_obj::FromTableRef,
    tables::glyf::{Contour, GlyfLocaBuilder, Glyph, SimpleGlyph},
    FontBuilder,
};

pub use error::GftoolsError;
pub use names::{update_name_table, AxisLimits, AxisTriple};
// Have to make this pub so our scripts can use it
#[allow(unused_imports)]
pub(crate) use gf_metadata::DesignerInfoProto;
pub(crate) use gf_metadata::{AxisProto, FamilyProto};
use tabled::settings::Style;

fn parse_metadatapb<T>(path: &Path) -> Result<T, GftoolsError>
where
    T: protobuf::MessageFull,
{
    let meta_file = path.join("METADATA.pb");
    let meta_contents = std::fs::read(meta_file)?;
    let contents = std::str::from_utf8(&meta_contents)
        .map_err(|_| GftoolsError::Misc("METADATA.pb is not valid UTF-8".to_string()))?;
    let data = protobuf::text_format::parse_from_str::<T>(contents)
        .map_err(GftoolsError::ProtobufParse)?;
    Ok(data)
}

pub fn list_some_things<T: Display>(
    font_files: &[String],
    lister: impl Fn(&str, &skrifa::FontRef) -> Option<Vec<T>>,
    headers: &[&str],
    csv: bool,
) {
    let mut info: Vec<Vec<String>> = Vec::new();
    for font in font_files.iter() {
        let Ok(font_data) = std::fs::read(font) else {
            log::warn!("{}: Failed to read font file, skipping", font);
            continue;
        };
        let Ok(fontref) = skrifa::FontRef::new(&font_data) else {
            log::warn!("{}: Failed to parse font file, skipping", font);
            continue;
        };
        if let Some(result) = lister(font, &fontref) {
            info.push(
                std::iter::once(font.to_string())
                    .chain(result.into_iter().map(|x| x.to_string()))
                    .collect::<Vec<String>>(),
            );
        } // list should do its own error reporting
    }
    if csv {
        println!("font,{}", headers.join(","));
        for row in info {
            println!("{}", row.join(","));
        }
    } else {
        let mut builder = tabled::builder::Builder::default();
        builder.push_record(headers.iter().map(|s| s.to_string()));
        for row in info {
            builder.push_record(row);
        }
        let mut table = builder.build();
        table.with(Style::sharp());
        println!("{}", table);
    }
}

// layer.shapes = contours
//     .contours()
//     .map(|x| crate::Shape::Path(x.path.clone().into()))
//     .collect();

pub fn remove_overlaps(font_in: &[u8]) -> Result<Vec<u8>, GftoolsError> {
    let fontref = skrifa::FontRef::new(font_in)
        .map_err(|_| GftoolsError::Misc("Failed to parse font".to_string()))?;
    // Assert this is a static font
    if fontref.fvar().is_ok() {
        return Err(GftoolsError::Misc(
            "Can only remove overlaps in static fonts".to_string(),
        ));
    }
    let loca = fontref.loca(None)?;
    let glyf = fontref.glyf()?;
    let glyph_count: u32 = fontref.maxp()?.num_glyphs().into();
    let mut builder = GlyfLocaBuilder::new();
    for i in 0..glyph_count {
        let gid = GlyphId::from(i);
        if let Ok(Some(g)) = loca.get_glyf(gid, &glyf) {
            let mut glyph = Glyph::from_table_ref(&g);
            remove_overlap_glyph(&mut glyph)?;
            builder
                .add_glyph(&glyph)
                .map_err(|e| GftoolsError::Misc(format!("Failed to add glyph: {}", e)))?;
        }
    }
    let (glyf, loca, _loca_format) = builder.build();
    let mut new_font = FontBuilder::new();
    new_font.add_table(&glyf)?;
    new_font.add_table(&loca)?;
    new_font.copy_missing_tables(fontref);
    Ok(new_font.build())
}

fn remove_overlap_glyph(glyph: &mut Glyph) -> Result<(), GftoolsError> {
    if let Glyph::Simple(simple_glyph) = glyph {
        let mut bezpath_before: BezPath = BezPath::new();
        for contour in &simple_glyph.contours {
            bezpath_before.extend(contour_to_bez(contour));
        }

        let contours = binary_op(
            &bezpath_before,
            &BezPath::new(),
            FillRule::NonZero,
            BinaryOp::Union,
        )
        .map_err(|e| crate::GftoolsError::Misc(format!("Failed to remove overlaps: {}", e)))?;
        let mut bezpath: BezPath = BezPath::new();
        for c in contours.contours() {
            bezpath.extend(to_quadratic(&c.path));
        }
        *glyph = Glyph::Simple(SimpleGlyph::from_bezpath(&bezpath).map_err(|e| {
            GftoolsError::Misc("Failed to create simple glyph: malformed path".to_string())
        })?);
    }
    Ok(())
}

fn contour_to_bez(contour: &Contour) -> BezPath {
    let mut bezpath = BezPath::new();
    let mut control_point: Option<Point> = None;
    let mut iter = contour.iter();
    let first = iter.next();
    let pt = |p: &CurvePoint| Point::new(p.x as f64, p.y as f64);
    if let Some(first_point) = first {
        if first_point.on_curve {
            bezpath.move_to(pt(first_point));
        } else {
            control_point = Some(pt(first_point));
        }
    }
    for c in contour.iter() {
        // The curve is in quadspline format, i.e. two successive off-curve points
        // have an implied on-curve point between them.
        if c.on_curve {
            if let Some(cp) = control_point {
                bezpath.quad_to(cp, pt(&c));
                control_point = None;
            } else {
                bezpath.line_to(pt(&c));
            }
        } else {
            if let Some(last_cp) = control_point {
                let implied_on = Point {
                    x: (last_cp.x + pt(&c).x) / 2.0,
                    y: (last_cp.y + pt(&c).y) / 2.0,
                };
                bezpath.quad_to(last_cp, implied_on);
            }
            control_point = Some(pt(&c));
        }
    }
    // Except we need it as a cubic
    BezPath::from_path_segments(bezpath.segments().map(|s| match s {
        kurbo::PathSeg::Line(_) => s,
        kurbo::PathSeg::Quad(quad_bez) => kurbo::PathSeg::Cubic(quad_bez.raise()),
        kurbo::PathSeg::Cubic(_) => unreachable!(),
    }))
}

fn to_quadratic(cubic: &BezPath) -> BezPath {
    let mut new_path_seg = Vec::new();
    for seg in cubic.segments() {
        match seg {
            kurbo::PathSeg::Line(_) => new_path_seg.push(seg),
            kurbo::PathSeg::Quad(_) => unreachable!(),
            kurbo::PathSeg::Cubic(cubic_bez) => {
                for (_, _, quad) in cubic_bez.to_quads(1.0) {
                    new_path_seg.push(kurbo::PathSeg::Quad(quad));
                }
            }
        }
    }

    BezPath::from_path_segments(new_path_seg.into_iter())
}
