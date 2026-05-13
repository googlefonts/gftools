"""Render strings from a font as a waterfall PNG.

The rendering backend is platform-native by default:
    macOS   -> CoreText
    Windows -> DirectWrite (implemented via Skia-Python; see
               directwrite_backend.py for rationale)
    Linux   -> FreeType (with HarfBuzz for shaping)

See ``docs/gftools-render-text/spec.md`` for the design spec.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable, Iterator

from fontTools.ttLib import TTFont
from PIL import Image


DEFAULT_PPEMS: tuple[int, ...] = (8, 10, 12, 14, 16, 20, 24, 36)
ROW_PADDING = 6
CANVAS_PADDING = 12


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


def output_path_for_instance(
    font_path: Path, instance_name: str, output_dir: Path
) -> Path:
    return output_dir / f"{font_path.stem}-{_filename_safe(instance_name)}.png"


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
    rows = [render_row(font_path, text, ppem, variations) for ppem in ppems]
    return _compose_waterfall(rows)


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
