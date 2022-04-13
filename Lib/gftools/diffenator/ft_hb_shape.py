import freetype as ft
import numpy as np
import uharfbuzz as hb


def draw_text(
    filename,
    text,
    size=128,
    features=None,
    script=None,
    lang=None,
    ft_face=None,
    hb_font=None,
):
    if not ft_face:
        ft_face = ft.Face(filename)
    ft_face.set_char_size(size * 64)
    flags = ft.FT_LOAD_RENDER
    pen = ft.FT_Vector(0, 0)
    xmin, xmax = 0, 0
    ymin, ymax = 0, 0
    if not hb_font:
        with open(filename, "rb") as fontfile:
            fontdata = fontfile.read()
        hb_face = hb.Face(fontdata)
        hb_font = hb.Font(hb_face)
    hb_font.scale = (size * 64, size * 64)
    hb.ot_font_set_funcs(hb_font)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    if script:
        buf.script = str(script)
    if lang:
        buf.language = str(lang)
    hb.shape(hb_font, buf, features)

    for glyph, pos in zip(buf.glyph_infos, buf.glyph_positions):
        ft_face.load_glyph(glyph.codepoint, flags)
        bitmap = ft_face.glyph.bitmap
        width = bitmap.width
        rows = bitmap.rows
        top = ft_face.glyph.bitmap_top
        left = ft_face.glyph.bitmap_left
        x0 = (pen.x >> 6) + left + (pos.x_offset >> 6)
        x1 = x0 + width
        y0 = (pen.y >> 6) - (rows - top) + (pos.y_offset >> 6)
        y1 = y0 + rows
        xmin, xmax = min(xmin, x0), max(xmax, x1)
        ymin, ymax = min(ymin, y0), max(ymax, y1)
        pen.x += pos.x_advance
        pen.y += pos.y_advance

    L = np.zeros((ymax - ymin, xmax - xmin), dtype=np.ubyte)
    previous = 0
    pen.x, pen.y = 0, 0
    for glyph, pos in zip(buf.glyph_infos, buf.glyph_positions):
        ft_face.load_glyph(glyph.codepoint, flags)
        pitch = ft_face.glyph.bitmap.pitch
        width = bitmap.width
        rows = bitmap.rows
        top = ft_face.glyph.bitmap_top
        left = ft_face.glyph.bitmap_left
        x = (pen.x >> 6) - xmin + left + (pos.x_offset >> 6)
        y = (pen.y >> 6) - ymin - (rows - top) + (pos.y_offset >> 6)
        data = []
        for j in range(rows):
            data.extend(bitmap.buffer[j * pitch : j * pitch + width])
        if len(data):
            Z = np.array(data, dtype=np.ubyte).reshape(rows, width)
            L[y : y + rows, x : x + width] |= Z[::-1, ::1]
        pen.x += pos.x_advance
        pen.y += pos.y_advance

    return L


if __name__ == "__main__":
    import argparse
    import re

    parser = argparse.ArgumentParser(description="Draw some text")
    parser.add_argument("font", metavar="TTF")
    parser.add_argument("string", metavar="TEXT")
    parser.add_argument("--out", metavar="PNG", default="out.png")
    parser.add_argument("--lang", metavar="LANGUAGE")
    parser.add_argument("--script", metavar="SCRIPT")
    parser.add_argument("--features", metavar="FEATURES")
    args = parser.parse_args()
    features = None
    if args.features:
        features = {}
        for f in args.features.split(","):
            if f[0] == "-":
                features[f[1:]] = False
            elif f[0] == "+":
                features[f[1:]] = True
            else:
                features[f] = True

    img = draw_text(
        args.font, args.string, lang=args.lang, script=args.script, features=features
    )
    from PIL import Image

    I = Image.fromarray(img[::-1, ::1])
    I.save(args.out)
