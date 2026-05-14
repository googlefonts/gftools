"""Render strings from a font as a waterfall PNG.

The rendering backend is platform-native by default:
    macOS   -> CoreText
    Windows -> DirectWrite (implemented via Skia-Python; see
               directwrite_backend.py for rationale)
    Linux   -> FreeType (with HarfBuzz for shaping)

See ``docs/gftools-render-text/spec.md`` for the design spec.
"""

from __future__ import annotations

import platform
import re
import sys
from pathlib import Path
from typing import Iterable, Iterator

from fontTools.ttLib import TTFont
from PIL import Image, ImageChops, ImageDraw, ImageFont


DEFAULT_PPEMS: tuple[int, ...] = (8, 10, 12, 14, 16, 20, 24, 36)
ROW_PADDING = 6
CANVAS_PADDING = 12
# Per-row vertical padding above ascender and below descender. Shared by all
# backends so row heights match exactly across platforms.
ROW_VPAD = 2


def default_backend() -> str:
    if sys.platform == "darwin":
        return "coretext"
    if sys.platform == "win32":
        return "directwrite"
    return "freetype"


def parse_variations(spec: str) -> dict[str, float]:
    """Parse ``wght=400,wdth=75`` into ``{"wght": 400.0, "wdth": 75.0}``."""
    result: dict[str, float] = {}
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        if "=" not in token:
            raise ValueError(f"variation token {token!r} missing '='")
        axis, value = token.split("=", 1)
        axis = axis.strip()
        if len(axis) != 4:
            raise ValueError(f"axis tag must be 4 chars, got {axis!r}")
        result[axis] = float(value.strip())
    return result


def is_variable(font_path: Path) -> bool:
    with TTFont(font_path) as font:
        return "fvar" in font


def iter_fvar_instances(
    font_path: Path,
) -> Iterator[tuple[str, dict[str, float]]]:
    """Yield ``(subfamily_name, {axis_tag: value})`` for each fvar instance."""
    with TTFont(font_path) as font:
        if "fvar" not in font:
            return
        fvar = font["fvar"]
        name = font["name"]
        for inst in fvar.instances:
            label = name.getDebugName(inst.subfamilyNameID) or "Instance"
            yield label, dict(inst.coordinates)


_FILENAME_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _filename_safe(s: str) -> str:
    return _FILENAME_SAFE_RE.sub("", s)


def _format_value(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def _format_variations_suffix(variations: dict[str, float]) -> str:
    return "-".join(f"{tag}{_format_value(val)}" for tag, val in variations.items())


def output_path_for(
    font_path: Path,
    *,
    variations: dict[str, float] | None = None,
    output: str | Path | None = None,
) -> Path:
    if output is not None:
        return Path(output)
    stem = font_path.stem
    if variations:
        stem = f"{stem}-{_format_variations_suffix(variations)}"
    return font_path.parent / f"{stem}.png"


def output_dir_for_all(
    font_path: Path, *, output_dir: str | Path | None = None
) -> Path:
    if output_dir is not None:
        return Path(output_dir)
    return font_path.parent / f"{font_path.stem}_imgs"


def output_dir_for_diff(
    after_font_path: Path, *, output_dir: str | Path | None = None
) -> Path:
    if output_dir is not None:
        return Path(output_dir)
    return after_font_path.parent / f"{after_font_path.stem}_diff"


def output_path_for_instance(
    font_path: Path, instance_name: str, output_dir: Path
) -> Path:
    return output_dir / f"{font_path.stem}-{_filename_safe(instance_name)}.png"


def output_subdir_for_instance(out_dir: Path, instance_name: str) -> Path:
    """Return a per-instance subdirectory inside ``out_dir`` (used by ``diff --all``)."""
    return out_dir / _filename_safe(instance_name)


def render_waterfall(
    font_path: Path,
    text: str,
    *,
    ppems: Iterable[int] = DEFAULT_PPEMS,
    variations: dict[str, float] | None = None,
    backend: str | None = None,
) -> Image.Image:
    """Render ``text`` from ``font_path`` at each ppem and stack vertically."""
    backend = backend or default_backend()
    render_row = _load_backend(backend)
    ascent_du, descent_du, upem = _font_line_metrics(font_path)
    rows = []
    for ppem in ppems:
        ascent_px = int(round(ascent_du * ppem / upem))
        descent_px = int(round(descent_du * ppem / upem))
        target_h = ascent_px + descent_px + ROW_VPAD * 2
        baseline_y = ascent_px + ROW_VPAD
        rows.append(
            render_row(
                font_path,
                text,
                ppem,
                variations,
                target_height=target_h,
                baseline_y=baseline_y,
            )
        )
    canvas = _compose_waterfall(rows)
    _annotate_platform(canvas, backend)
    return canvas


def _font_line_metrics(font_path: Path) -> tuple[int, int, int]:
    """Return ``(ascent_du, descent_du, upem)`` from OS/2 typo metrics.

    All backends use this single source so row heights match across platforms.
    Falls back to ``hhea`` for fonts without an OS/2 table.
    """
    with TTFont(font_path) as font:
        upem = font["head"].unitsPerEm
        os2 = font.get("OS/2")
        if os2 is not None:
            return os2.sTypoAscender, -os2.sTypoDescender, upem
        hhea = font["hhea"]
        return hhea.ascender, -hhea.descender, upem


_BACKEND_DISPLAY = {
    "coretext": "CoreText",
    "directwrite": "DirectWrite",
    "freetype": "FreeType",
}


def _annotate_platform(canvas: Image.Image, backend: str) -> None:
    label = f"{platform.system()} / {_BACKEND_DISPLAY.get(backend, backend)}"
    font = ImageFont.load_default(size=12)
    draw = ImageDraw.Draw(canvas)
    bbox = draw.textbbox((0, 0), label, font=font)
    text_height = bbox[3] - bbox[1]
    x = CANVAS_PADDING // 2
    y = canvas.height - text_height - CANVAS_PADDING // 2
    draw.text((x, y), label, fill=(128, 128, 128), font=font)


def _load_backend(name: str):
    if name == "freetype":
        from . import freetype_backend

        return freetype_backend.render_row
    if name == "coretext":
        from . import coretext_backend

        return coretext_backend.render_row
    if name == "directwrite":
        from . import directwrite_backend

        return directwrite_backend.render_row
    raise ValueError(f"unknown backend {name!r}")


def _compose_waterfall(rows: list[Image.Image]) -> Image.Image:
    width = max((row.width for row in rows), default=0) + CANVAS_PADDING * 2
    height = (
        sum(row.height for row in rows)
        + ROW_PADDING * (len(rows) - 1 if rows else 0)
        + CANVAS_PADDING * 2
    )
    canvas = Image.new("RGB", (width, height), "white")
    y = CANVAS_PADDING
    for row in rows:
        canvas.paste(row, (CANVAS_PADDING, y))
        y += row.height + ROW_PADDING
    return canvas


def pad_to_match(images: list[Image.Image]) -> list[Image.Image]:
    """Pad each image with white to the max (width, height) of the set."""
    if not images:
        return []
    w = max(im.width for im in images)
    h = max(im.height for im in images)
    return [_pad_white(im, w, h) for im in images]


def _pad_white(im: Image.Image, w: int, h: int) -> Image.Image:
    if im.size == (w, h):
        return im
    canvas = Image.new(im.mode, (w, h), "white")
    canvas.paste(im, (0, 0))
    return canvas


def diff_image(before: Image.Image, after: Image.Image) -> Image.Image:
    """Return the absolute per-pixel difference (PIL's 'difference' blend mode).

    The two inputs must be the same size; use :func:`pad_to_match` first.
    Identical pixels become black; differing pixels become brighter.
    """
    if before.size != after.size:
        raise ValueError(
            f"diff inputs must match in size; got {before.size} vs {after.size}"
        )
    return ImageChops.difference(after, before)


def save_animation(
    frames: list[Image.Image], path: Path, duration_ms: int = 500
) -> None:
    """Save an animated GIF cycling through ``frames`` (infinite loop)."""
    if not frames:
        raise ValueError("no frames to animate")
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=0,
    )
