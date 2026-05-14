"""CoreText rendering backend (macOS).

Uses CoreText for shaping and CGBitmapContext for rasterisation. Runs only
on macOS — pyobjc-framework-CoreText / pyobjc-framework-Quartz must be
installed (declared as platform-conditional deps in pyproject.toml).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

try:
    import CoreText
    import Quartz
    from Foundation import NSData
except ModuleNotFoundError:
    raise ModuleNotFoundError(
        "gftools was installed without the QA dependencies. To install the "
        "dependencies, see the ReadMe, "
        "https://github.com/googlefonts/gftools#installation"
    )

PADDING = 2


def render_row(
    font_path: Path,
    text: str,
    ppem: int,
    variations: dict[str, float] | None = None,
    *,
    target_height: int,
    baseline_y: int,
) -> Image.Image:
    ct_font = _make_ct_font(font_path, ppem, variations)
    line = _make_line(ct_font, text)

    width_d, _ascent, _descent, _leading = _measure(line)
    width = max(int(width_d) + PADDING * 2, 1)
    # CG's drawing coords are bottom-left origin; convert baseline-from-top.
    baseline_y_cg = target_height - baseline_y

    ctx = _gray_bitmap_context(width, target_height)
    Quartz.CGContextSetGrayFillColor(ctx, 1.0, 1.0)
    Quartz.CGContextFillRect(ctx, ((0, 0), (width, target_height)))
    Quartz.CGContextSetGrayFillColor(ctx, 0.0, 1.0)
    Quartz.CGContextSetTextPosition(ctx, PADDING, baseline_y_cg)
    CoreText.CTLineDraw(line, ctx)

    pixels = Quartz.CGBitmapContextGetData(ctx).as_buffer(width * target_height)
    img = Image.frombytes("L", (width, target_height), bytes(pixels))
    return img.convert("RGB")


def _make_ct_font(font_path: Path, ppem: int, variations: dict[str, float] | None):
    data = NSData.dataWithContentsOfFile_(str(font_path))
    if data is None:
        raise FileNotFoundError(font_path)
    provider = Quartz.CGDataProviderCreateWithCFData(data)
    cg_font = Quartz.CGFontCreateWithDataProvider(provider)
    if cg_font is None:
        raise RuntimeError(f"CoreText could not load font: {font_path}")
    ct_font = CoreText.CTFontCreateWithGraphicsFont(cg_font, ppem, None, None)
    if not variations:
        return ct_font
    return _apply_variations(ct_font, variations, ppem)


def _apply_variations(ct_font, variations: dict[str, float], ppem: int):
    var_attr = {_tag_to_int(tag): float(value) for tag, value in variations.items()}
    descriptor = CoreText.CTFontCopyFontDescriptor(ct_font)
    new_desc = CoreText.CTFontDescriptorCreateCopyWithAttributes(
        descriptor, {CoreText.kCTFontVariationAttribute: var_attr}
    )
    return CoreText.CTFontCreateWithFontDescriptor(new_desc, ppem, None)


def _make_line(ct_font, text: str):
    attrs = {CoreText.kCTFontAttributeName: ct_font}
    astr = CoreText.CFAttributedStringCreate(None, text, attrs)
    return CoreText.CTLineCreateWithAttributedString(astr)


def _measure(line) -> tuple[float, float, float, float]:
    ascent, descent, leading = 0.0, 0.0, 0.0
    width = CoreText.CTLineGetTypographicBounds(line, None, None, None)
    if isinstance(width, tuple):
        width, ascent, descent, leading = width
    return width, ascent, descent, leading


def _gray_bitmap_context(width: int, height: int):
    color_space = Quartz.CGColorSpaceCreateDeviceGray()
    return Quartz.CGBitmapContextCreate(
        None, width, height, 8, width, color_space, Quartz.kCGImageAlphaNone
    )


def _tag_to_int(tag: str) -> int:
    if len(tag) != 4:
        raise ValueError(f"axis tag must be 4 chars: {tag!r}")
    b = tag.encode("ascii")
    return (b[0] << 24) | (b[1] << 16) | (b[2] << 8) | b[3]
