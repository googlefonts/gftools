"""FreeType + HarfBuzz rendering backend.

HarfBuzz handles shaping; FreeType rasterises each glyph. The two are kept
in sync on variable fonts by applying the variation coords to both.
"""

from __future__ import annotations

from pathlib import Path

import freetype
import uharfbuzz as hb
from fontTools.ttLib import TTFont
from PIL import Image


def render_row(
    font_path: Path,
    text: str,
    ppem: int,
    variations: dict[str, float] | None = None,
    *,
    target_height: int,
    baseline_y: int,
) -> Image.Image:
    glyph_infos, glyph_positions = _shape(font_path, text, ppem, variations)
    ft_face = _make_ft_face(font_path, ppem, variations)

    pen_x = 0
    glyphs: list[tuple[Image.Image, int, int]] = []
    for info, pos in zip(glyph_infos, glyph_positions):
        ft_face.load_glyph(info.codepoint, freetype.FT_LOAD_RENDER)
        slot = ft_face.glyph
        bm = slot.bitmap
        if bm.width and bm.rows:
            glyph_img = Image.frombytes("L", (bm.width, bm.rows), bytes(bm.buffer))
            x = pen_x + (pos.x_offset // 64) + slot.bitmap_left
            y = baseline_y - (pos.y_offset // 64) - slot.bitmap_top
            glyphs.append((glyph_img, x, y))
        pen_x += pos.x_advance // 64

    width = max(pen_x, 1) + 4
    canvas = Image.new("L", (width, target_height), 255)
    for glyph_img, x, y in glyphs:
        ink = Image.new("L", glyph_img.size, 0)
        canvas.paste(ink, (x + 2, y), mask=glyph_img)
    return canvas.convert("RGB")


def _shape(
    font_path: Path,
    text: str,
    ppem: int,
    variations: dict[str, float] | None,
):
    blob = hb.Blob.from_file_path(str(font_path))
    face = hb.Face(blob)
    font = hb.Font(face)
    font.scale = (ppem * 64, ppem * 64)
    if variations:
        font.set_variations(variations)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf)
    return buf.glyph_infos, buf.glyph_positions


def _make_ft_face(
    font_path: Path, ppem: int, variations: dict[str, float] | None
) -> freetype.Face:
    face = freetype.Face(str(font_path))
    face.set_pixel_sizes(0, ppem)
    if variations:
        coords = _design_coords_in_axis_order(font_path, variations)
        if coords is not None:
            face.set_var_design_coords(coords)
    return face


def _design_coords_in_axis_order(
    font_path: Path, variations: dict[str, float]
) -> list[float] | None:
    with TTFont(font_path) as font:
        if "fvar" not in font:
            return None
        return [
            variations.get(axis.axisTag, axis.defaultValue)
            for axis in font["fvar"].axes
        ]
