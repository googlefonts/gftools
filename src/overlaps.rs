use crate::GftoolsError;
use kurbo::{BezPath, Point, Shape};
use linesweeper::{BinaryOp, FillRule, binary_op};
use skrifa::{
    GlyphId,
    raw::{TableProvider, tables::glyf::CurvePoint},
};
use write_fonts::{
    FontBuilder,
    from_obj::FromTableRef,
    tables::glyf::{Contour, GlyfLocaBuilder, Glyph, SimpleGlyph},
};

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
        } else {
            // Push an empty glyph so we don't get out of sync
            builder
                .add_glyph(&Glyph::Simple(SimpleGlyph::default()))
                .map_err(|e| GftoolsError::Misc(format!("Failed to add empty glyph: {}", e)))?;
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

        // println!("Before removing overlaps: {:?}", bezpath_before);

        let contours = binary_op(
            &bezpath_before,
            &BezPath::new(),
            FillRule::NonZero,
            BinaryOp::Union,
        )
        .map_err(|e| crate::GftoolsError::Misc(format!("Failed to remove overlaps: {}", e)))?;
        let bezpath = enforce_tt_orientation(contours.contours().map(|c| to_quadratic(&c.path)));
        *glyph =
            Glyph::Simple(SimpleGlyph::from_bezpath(&bezpath).map_err(|e| {
                GftoolsError::Misc(format!("Failed to create simple glyph: {:?}", e))
            })?);
    }
    Ok(())
}

/// Convert one TrueType (quadratic) contour into a closed cubic [`BezPath`].
fn contour_to_bez(contour: &Contour) -> BezPath {
    let mut cubic = BezPath::new();
    let pt = |p: &CurvePoint| Point::new(p.x as f64, p.y as f64);

    let points: Vec<&CurvePoint> = contour.iter().collect();
    let n = points.len();
    if n == 0 {
        return cubic;
    }

    // Start drawing from an on-curve point so that walking
    // `start_idx..start_idx + count` visits every point of the contour exactly
    // once without revisiting the start point.
    let (start, start_idx, count) = if points[0].on_curve {
        (pt(points[0]), 1, n - 1)
    } else if points[n - 1].on_curve {
        // The contour effectively starts at its last point; the first point is
        // an off-curve control point that follows it.
        (pt(points[n - 1]), 0, n - 1)
    } else {
        // Entirely off-curve contour: start at the implied on-curve point
        // between the last and first points, and treat every point as a control.
        (pt(points[n - 1]).midpoint(pt(points[0])), 0, n)
    };

    cubic.move_to(start);
    let mut control_point: Option<Point> = None;
    for i in 0..count {
        let c = &points[(start_idx + i) % n];
        let c_pt = pt(c);
        if c.on_curve {
            match control_point.take() {
                // `linesweeper` only handles cubics correctly, so raise quadratics to cubics before passing them along.
                Some(cp) => raise_quad(&mut cubic, cp, c_pt),
                None => cubic.line_to(c_pt),
            }
        } else {
            // Two successive off-curve points have an implied on-curve point
            // halfway between them.
            if let Some(last_cp) = control_point {
                raise_quad(&mut cubic, last_cp, last_cp.midpoint(c_pt));
            }
            control_point = Some(c_pt);
        }
    }
    // Close the cycle back to the start point; if we finished on an off-curve
    // point the closing segment is a curve through it, otherwise `close_path`
    // supplies the implicit straight line.
    if let Some(cp) = control_point {
        raise_quad(&mut cubic, cp, start);
    }
    cubic.close_path();
    cubic
}

/// Append the quadratic segment (`control`, `end`) to `path`, raised to a cubic.
fn raise_quad(path: &mut BezPath, control: Point, end: Point) {
    let start = path
        .current_position()
        .expect("quadratic segment without a preceding move/line");
    let cubic = kurbo::QuadBez::new(start, control, end).raise();
    path.curve_to(cubic.p1, cubic.p2, cubic.p3);
}

/// Convert a cubic BezPath (as returned by `linesweeper`) into an
/// equivalent quadratic one.
fn to_quadratic(cubic: &BezPath) -> BezPath {
    let mut quad = BezPath::new();
    for el in cubic.elements() {
        match el {
            kurbo::PathEl::MoveTo(p) => quad.move_to(*p),
            kurbo::PathEl::LineTo(p) => quad.line_to(*p),
            kurbo::PathEl::QuadTo(p1, p2) => quad.quad_to(*p1, *p2),
            kurbo::PathEl::CurveTo(p1, p2, p3) => {
                let start = quad
                    .current_position()
                    .expect("cubic segment without a preceding move/line");
                let cubic_bez = kurbo::CubicBez::new(start, *p1, *p2, *p3);
                for (_, _, q) in cubic_bez.to_quads(1.0) {
                    quad.quad_to(q.p1, q.p2);
                }
            }
            kurbo::PathEl::ClosePath => quad.close_path(),
        }
    }
    quad
}

fn enforce_tt_orientation(contours: impl IntoIterator<Item = BezPath>) -> BezPath {
    let mut path = BezPath::new();
    let mut largest_area = 0.0_f64;
    for contour in contours {
        let area = contour.area();
        if area.abs() > largest_area.abs() {
            largest_area = area;
        }
        path.extend(contour);
    }
    if largest_area > 0.0 {
        path.reverse_subpaths()
    } else {
        path
    }
}

#[cfg(test)]
mod tests {
    use kurbo::Shape;

    use super::*;

    fn pt(x: i16, y: i16, on_curve: bool) -> CurvePoint {
        CurvePoint::new(x, y, on_curve)
    }

    /// Run one contour through the whole quadratic -> cubic -> quadratic
    /// conversion and return the points of the resulting glyph contour.
    fn round_trip(points: Vec<CurvePoint>) -> Vec<CurvePoint> {
        let cubic = contour_to_bez(&Contour::from(points));
        let quad = to_quadratic(&cubic);
        let glyph =
            SimpleGlyph::from_bezpath(&quad).expect("converted outline should be a valid glyph");
        assert_eq!(glyph.contours.len(), 1, "expected exactly one contour");
        glyph.contours[0].iter().copied().collect()
    }

    /// TrueType contours are cyclic, so a converted contour may be a rotation of
    /// the original point list as long as the order and flags are preserved.
    fn assert_cyclic_eq(actual: &[CurvePoint], expected: &[CurvePoint]) {
        assert_eq!(
            actual.len(),
            expected.len(),
            "point count changed: {:?} != {:?}",
            actual,
            expected
        );
        let n = expected.len();
        let matches = (0..n).any(|r| (0..n).all(|i| actual[i] == expected[(r + i) % n]));
        assert!(
            matches,
            "contours differ: {:?} is not a rotation of {:?}",
            actual, expected
        );
    }

    /// A contour may begin on an off-curve point. This used to panic inside
    /// `contour_to_bez` because the first point was processed twice, emitting a
    /// quadratic segment before any `MoveTo`.
    #[test]
    fn contour_starting_off_curve() {
        let points = vec![pt(100, 0, false), pt(100, 100, false), pt(0, 100, true)];
        assert_cyclic_eq(&round_trip(points.clone()), &points);
    }

    /// A contour made entirely of off-curve points gets an implied on-curve
    /// start point halfway between its last and first points. This also used to
    /// panic.
    #[test]
    fn contour_entirely_off_curve() {
        let points = vec![
            pt(0, 0, false),
            pt(100, 0, false),
            pt(100, 100, false),
            pt(0, 100, false),
        ];
        assert_cyclic_eq(&round_trip(points.clone()), &points);
    }

    /// A contour that *ends* on an off-curve point must close through that
    /// control point. The trailing control point was previously dropped and the
    /// closing curve silently replaced by a straight line, distorting the shape.
    #[test]
    fn contour_ending_off_curve() {
        let points = vec![pt(0, 0, true), pt(100, 0, false), pt(100, 100, false)];
        assert_cyclic_eq(&round_trip(points.clone()), &points);
    }

    /// A contour that both starts and ends on an on-curve point.
    #[test]
    fn contour_closing_off_curve() {
        let points = vec![
            pt(0, 0, true),
            pt(100, 0, false),
            pt(100, 100, false),
            pt(0, 100, true),
        ];
        assert_cyclic_eq(&round_trip(points.clone()), &points);
    }

    /// Build a closed rectangular contour; `clockwise` selects the winding.
    fn rect(x0: f64, y0: f64, x1: f64, y1: f64, clockwise: bool) -> BezPath {
        let mut corners = [
            Point::new(x0, y0),
            Point::new(x1, y0),
            Point::new(x1, y1),
            Point::new(x0, y1),
        ];
        if clockwise {
            corners.reverse();
        }
        let mut path = BezPath::new();
        path.move_to(corners[0]);
        for p in &corners[1..] {
            path.line_to(*p);
        }
        path.close_path();
        path
    }

    fn combine(contours: &[BezPath]) -> BezPath {
        let mut path = BezPath::new();
        for contour in contours {
            path.extend(contour.clone());
        }
        path
    }

    /// A single anti-clockwise outer contour must be reversed, an already
    /// clockwise one must be left alone.
    #[test]
    fn enforces_clockwise_outer_contour() {
        let ccw = rect(0.0, 0.0, 100.0, 100.0, false);
        let cw = rect(0.0, 0.0, 100.0, 100.0, true);
        // Sanity-check the sign convention: clockwise means negative area.
        assert!(ccw.area() > 0.0);
        assert!(cw.area() < 0.0);

        assert_eq!(enforce_tt_orientation([ccw.clone()]), cw.clone());
        assert_eq!(enforce_tt_orientation([cw.clone()]), cw);
    }

    /// Holes must end up anti-clockwise, i.e. opposite to their outer contour.
    #[test]
    fn enforces_anticlockwise_holes() {
        // As returned by a boolean op: outer anti-clockwise, hole clockwise.
        let flipped = vec![
            rect(0.0, 0.0, 100.0, 100.0, false),
            rect(25.0, 25.0, 75.0, 75.0, true),
        ];
        assert_eq!(
            enforce_tt_orientation(flipped.clone()),
            combine(&flipped).reverse_subpaths()
        );
        assert!(enforce_tt_orientation(flipped).area() < 0.0);

        // Already correct: outer clockwise, hole anti-clockwise.
        let correct = vec![
            rect(0.0, 0.0, 100.0, 100.0, true),
            rect(25.0, 25.0, 75.0, 75.0, false),
        ];
        assert_eq!(enforce_tt_orientation(correct.clone()), combine(&correct));
        assert!(enforce_tt_orientation(correct).area() < 0.0);
    }
}
