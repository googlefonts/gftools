# gftools render-text — Spec

**Status:** Implemented.

## Purpose

Render strings from a font as waterfall PNGs, using the platform-native text
rendering backend (CoreText on macOS, DirectWrite on Windows via Skia-Python,
FreeType on Linux). The motivating use case is a GitHub Actions matrix job
that produces one image per platform so rendering regressions can be diff'd
across backends.

The tool has two subcommands:

- **`proof`** — render a single font as a waterfall PNG.
- **`diff`** — render two fonts (before + after) and emit before/after/diff
  images plus an animated GIF for visual comparison.

## Synopsis

```
gftools render-text proof FONT TEXT [-o OUTPUT] [--variations AXES | --all] [--backend BACKEND]
gftools render-text diff  BEFORE AFTER TEXT [-o PREFIX] [--variations AXES] [--backend BACKEND]
```

## Examples

```
gftools render-text proof Roboto-Regular.ttf "The quick brown fox jumps"
gftools render-text proof Roboto[wght].ttf "Hamburgefonstiv" --variations wght=400,wdth=75
gftools render-text proof Roboto[wght].ttf "Hamburgefonstiv" --all
gftools render-text proof Roboto-Regular.ttf "..." --backend freetype

gftools render-text diff Roboto-old.ttf Roboto-new.ttf "Hamburgefonstiv"
gftools render-text diff Roboto-old.ttf Roboto-new.ttf "..." --variations wght=700
```

## `proof` subcommand

Default output is a waterfall PNG containing the string rendered at the
following ppem sizes, stacked vertically:

```
8, 10, 12, 14, 16, 20, 24, 36
```

### Output filename

If `-o` is **not** provided, the output filename is derived from the input
font:

| Invocation | Output |
|---|---|
| `Roboto-Regular.ttf` (default instance) | `Roboto-Regular.png` |
| `Roboto[wght].ttf --variations wght=400,wdth=75` | `Roboto-wght400-wdth75.png` |
| `Roboto[wght].ttf --all` | `Roboto[wght]_imgs/Roboto-Regular.png`, `Roboto[wght]_imgs/Roboto-Bold.png`, `Roboto[wght]_imgs/Roboto-SemiBoldCondensed.png`, … |

For `--all`, the default output directory is `<font_stem>_imgs/` next to the
font. Per-image filenames inside the directory take the suffix from each fvar
instance's subfamily name (read from the `fvar` instance records), with
non-filesystem-safe characters stripped (spaces removed, slashes etc.
replaced).

If `-o` **is** provided with `--all`, it is treated as the output directory
(created if needed) and per-instance filenames are generated inside it.

### Flags

#### `-o, --output PATH`

Optional. Output file path (or directory when used with `--all`). Defaults
to `<font_stem>.png` next to the font.

#### `--variations AXES`

Render at a specific variable-font location. Format: `axis=value` pairs,
comma-separated, no spaces:

```
--variations wght=400,wdth=75
```

Mutually exclusive with `--all`.

#### `--all`

Render one image per fvar instance defined in the font.

- Mutually exclusive with `--variations`.
- On a **static** font, prints a warning to stderr ("font is static —
  rendering default style only") and renders a single default image. Exit
  code is 0.

## `diff` subcommand

Renders `BEFORE` and `AFTER` fonts independently with the existing waterfall
pipeline, then pads both renders to the maximum of `(width, height)` with
white and emits four artifacts into an output directory:

- `before.png` — the "before" waterfall, padded.
- `after.png` — the "after" waterfall, padded.
- `diff.png` — absolute per-pixel difference (PIL's "difference" blend
  mode: identical pixels are black, differing pixels are brighter).
- `anim.gif` — infinite-loop GIF alternating before/after at 500ms.

### Output directory

If `-o` is **not** provided, the directory is `<after_stem>_diff/` next to
the `AFTER` font (mirroring the `<font_stem>_imgs/` convention used by
`proof --all`):

```
gftools render-text diff Roboto-old.ttf Roboto-new.ttf "..."
# Produces (next to Roboto-new.ttf):
#   Roboto-new_diff/before.png
#   Roboto-new_diff/after.png
#   Roboto-new_diff/diff.png
#   Roboto-new_diff/anim.gif
```

If `-o PATH` is provided, `PATH` is used verbatim as the output directory
(created if needed) and the same four filenames are written inside it.

### Flags

#### `-o, --output PATH`

Output directory. Default: `<after_stem>_diff/` next to the after font.

#### `--variations AXES`

Variation location applied to **both** fonts (same axis values for before
and after, so the diff isolates the font change, not the variation change).
Same format as the `proof` subcommand.

`--all` is **not** supported with `diff` in v1.

## Shared flags

### `--backend {coretext,directwrite,freetype}`

Force a specific rendering backend. If omitted, the backend is selected
from the host platform:

| Platform | Default backend |
|---|---|
| macOS | CoreText |
| Windows | DirectWrite (via Skia-Python — see `directwrite_backend.py`) |
| Linux | FreeType |

The override is primarily for (a) developing/testing the FreeType path on
a Mac, and (b) letting CI assert which backend ran rather than inferring
from `runs-on`.

## Cross-backend dimensions

Row heights are normalised across backends using the font's `OS/2.sTypoAscender`
and `OS/2.sTypoDescender` (with `hhea` as fallback) read via fontTools, so
every backend produces images with identical row heights for a given font and
ppem. Widths remain backend-determined — different shapers will produce
slightly different total advances; that's the platform-rendering signal the
tool is meant to surface.

For the `diff` subcommand, both renders are padded to the maximum
`(width, height)` of the pair so the difference operation is well-defined.

## Platform stamp

Each rendered waterfall has a small grey label in the bottom-left corner
showing the platform and backend used (e.g. `Darwin / CoreText`,
`Linux / FreeType`, `Windows / DirectWrite`). Useful when triaging which
matrix artifact is which.

## Shaping

**Native shaping per backend (mostly).** Each backend uses its own shaper:

- CoreText shapes via CoreText.
- FreeType has no shaper, so the FreeType path uses HarfBuzz.
- The DirectWrite backend is implemented via Skia-Python, which uses
  HarfBuzz for shaping by default (not DirectWrite's native shaper). See
  `directwrite_backend.py` for the rationale (avoiding ~400 lines of
  comtypes vtable scaffolding).

A future `--shaper harfbuzz` flag could force HarfBuzz everywhere for
consistency; out of scope for v1.

## Installation

The render-text backends (`freetype-py` on Linux, `pyobjc-framework-CoreText`
+ `pyobjc-framework-Quartz` on macOS, `skia-python` on Windows) are declared
under the `[qa]` extra in `pyproject.toml`, not in base dependencies. Install
with:

```
pip install 'gftools[qa]'
```

Without the `[qa]` extra, invoking `gftools render-text` raises a
`ModuleNotFoundError` directing the user to the README.

## Out of scope (v1)

- Custom colors / themes (default is black-on-white).
- Custom DPI / device scaling.
- Multi-line text wrapping.
- PDF or SVG output.
- A `--shaper` override.
- `--all` combined with `diff`.
- Native DirectWrite shaping (uses Skia-Python's default HarfBuzz path).
