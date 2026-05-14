"""DirectWrite rendering backend (Windows), implemented via Skia-Python.

We *don't* call DirectWrite directly through comtypes. The rationale:

- DirectWrite is a deep COM hierarchy. A direct comtypes implementation
  needs ~400 lines of vtable scaffolding (interface declarations for
  IDWriteFactory, IDWriteTextAnalyzer, IDWriteGdiInterop,
  IDWriteBitmapRenderTarget, plus DWRITE structs and GDI plumbing for
  pixel readback) before any actual rendering happens.
- Skia delegates to ``SkFontMgr_DirectWrite`` and ``SkScalerContext_DW``
  on Windows, so font loading and glyph rasterisation still hit the
  platform-native DirectWrite stack — Skia just adds a thin
  gamma/contrast layer in front of it. The platform-rendering signal we
  care about (ClearType, subpixel positioning, DWrite hinting) is
  preserved.
- Symmetrically, Skia uses CoreText on macOS and FreeType+FontConfig on
  Linux, so anyone wanting a uniformly Skia-based matrix could use this
  backend on all three platforms via ``--backend directwrite`` (though
  ``coretext`` and ``freetype`` remain the platform defaults).

Fidelity tradeoff: Skia's default text path uses HarfBuzz for shaping,
not DirectWrite's shaper. For Latin pangrams this is invisible; for a
complex-script regression test it would matter and we'd need to
revisit.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

try:
    import skia
except ModuleNotFoundError:
    raise ModuleNotFoundError(
        "gftools was installed without the QA dependencies. To install the "
        "dependencies, see the ReadMe, "
        "https://github.com/googlefonts/gftools#installation"
    )

PADDING = 4


def render_row(
    font_path: Path,
    text: str,
    ppem: int,
    variations: dict[str, float] | None = None,
    *,
    target_height: int,
    baseline_y: int,
) -> Image.Image:
    typeface = skia.Typeface.MakeFromFile(str(font_path))
    if typeface is None:
        raise RuntimeError(f"Skia could not load font: {font_path}")
    if variations:
        typeface = _apply_variations(typeface, variations)

    font = skia.Font(typeface, float(ppem))
    font.setSubpixel(True)

    blob = skia.TextBlob.MakeFromString(text, font)
    bounds = blob.bounds()
    width = max(int(bounds.width()) + PADDING * 2, 1)

    surface = skia.Surface(width, target_height)
    with surface as canvas:
        canvas.clear(skia.ColorWHITE)
        paint = skia.Paint()
        paint.setColor(skia.ColorBLACK)
        paint.setAntiAlias(True)
        canvas.drawTextBlob(blob, PADDING, baseline_y, paint)

    info = skia.ImageInfo.Make(
        width, target_height, skia.kRGBA_8888_ColorType, skia.kUnpremul_AlphaType
    )
    buffer = bytearray(width * target_height * 4)
    if not surface.readPixels(info, buffer, width * 4, 0, 0):
        raise RuntimeError("Skia surface.readPixels failed")
    return Image.frombytes("RGBA", (width, target_height), bytes(buffer)).convert("RGB")


def _apply_variations(typeface, variations: dict[str, float]):
    Coord = skia.FontArguments.VariationPosition.Coordinate
    coord_list = skia.FontArguments.VariationPosition.Coordinates(
        [Coord(_tag_to_int(tag), float(val)) for tag, val in variations.items()]
    )
    pos = skia.FontArguments.VariationPosition(coord_list)
    args = skia.FontArguments()
    args.setVariationDesignPosition(pos)
    return typeface.makeClone(args)


def _tag_to_int(tag: str) -> int:
    if len(tag) != 4:
        raise ValueError(f"axis tag must be 4 chars: {tag!r}")
    b = tag.encode("ascii")
    return (b[0] << 24) | (b[1] << 16) | (b[2] << 8) | b[3]
