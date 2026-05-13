# gftools render-text — Spec

**Status:** Design — not yet implemented.

## Purpose

Render a string from a font as a waterfall PNG, using the platform-native text rendering backend (CoreText on macOS, DirectWrite on Windows, FreeType on Linux). The motivating use case is a GitHub Actions matrix job that produces one image per platform so rendering regressions can be diff'd across backends.

## Synopsis

```
gftools render-text FONT TEXT [-o OUTPUT] [--variations AXES | --all] [--backend BACKEND]
```

## Examples

```
gftools render-text Roboto-Regular.ttf "The quick brown fox jumps"
gftools render-text Roboto[wght].ttf "Hamburgefonstiv" --variations wght=400,wdth=75
gftools render-text Roboto[wght].ttf "Hamburgefonstiv" --all
gftools render-text Roboto-Regular.ttf "..." --backend freetype
```

## Output

Default output is a waterfall PNG containing the string rendered at the following ppem sizes, stacked vertically:

```
8, 10, 12, 14, 16, 20, 24, 36
```

### Output filename

If `-o` is **not** provided, the output filename is derived from the input font:

| Invocation | Output |
|---|---|
| `Roboto-Regular.ttf` (default instance) | `Roboto-Regular.png` |
| `Roboto[wght].ttf --variations wght=400,wdth=75` | `Roboto-wght400-wdth75.png` |
| `Roboto[wght].ttf --all` | `Roboto[wght]_imgs/Roboto-Regular.png`, `Roboto[wght]_imgs/Roboto-Bold.png`, `Roboto[wght]_imgs/Roboto-SemiBoldCondensed.png`, … |

For `--all`, the default output directory is `<font_stem>_imgs/` next to the font. Per-image filenames inside the directory take the suffix from each fvar instance's subfamily name (read from the `fvar` instance records), with non-filesystem-safe characters stripped (spaces removed, slashes etc. replaced).

If `-o` **is** provided with `--all`, it is treated as the output directory (created if needed) and per-instance filenames are generated inside it.

## Flags

### `-o, --output PATH`

Optional. Output file path (or directory when used with `--all`). Defaults to `<font_stem>.png` next to the font.

### `--variations AXES`

Render at a specific variable-font location. Format: `axis=value` pairs, comma-separated, no spaces:

```
--variations wght=400,wdth=75
```

Mutually exclusive with `--all`. If the font is static, this flag is an error.

### `--all`

Render one image per fvar instance defined in the font.

- Mutually exclusive with `--variations`.
- On a **static** font, prints a warning to stderr ("font is static — rendering default style only") and renders a single default image. Exit code is 0.

### `--backend {coretext,directwrite,freetype}`

Force a specific rendering backend. If omitted, the backend is selected from the host platform:

| Platform | Default backend |
|---|---|
| macOS | CoreText |
| Windows | DirectWrite |
| Linux | FreeType |

The override is primarily for (a) developing/testing the FreeType path on a Mac, and (b) letting CI assert which backend ran rather than inferring from `runs-on`.

## Shaping

**Native shaping per backend.** Each backend uses its own shaper:

- CoreText shapes via CoreText.
- DirectWrite shapes via DirectWrite.
- FreeType has no shaper, so the FreeType path uses HarfBuzz.

This tests the full platform stack (what users actually see end-to-end). The tradeoff is that a shaping bug and a rasterizer bug are indistinguishable in the diff — accepted for the v1 scope.

A future `--shaper harfbuzz` flag could force HarfBuzz everywhere to isolate the rasterizer, but is out of scope for v1.

## Out of scope (v1)

- Custom colors / themes (default is black-on-white).
- Custom DPI / device scaling.
- Multi-line text wrapping.
- PDF or SVG output.
- A `--shaper` override (see above).
