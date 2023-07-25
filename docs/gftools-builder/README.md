# gftools-builder: Config-driven font project builder

This utility wraps fontmake and a number of post-processing fixes to
build variable, static OTF, static TTF and webfonts from Glyphs,
Designspace/UFO or UFO sources.

It should be instantiated with a configuration file, typically
`config.yaml`, which looks like this:

    sources:
      - Texturina.glyphs
      - Texturina-Italic.glyphs
    axisOrder:
      - opsz
      - wght
    outputDir: "../fonts"
    familyName: Texturina
    version: 1.005
    stat:
      - name: Width
        tag: wdth
        values:
        - name: UltraCondensed
          value: 50
          ...
      - name: Weight
        tag: wght
        values:
        - name: Regular
          value: 400
          flags: 2
        ...
    statFormat4:
      - name: Green
        location:
          wght: 300
          wdth: 200
      - name: Blue
        location:
          wght: 400
          wdth: 200
    ...
    instances:
      Texturina[wght].ttf:
      - coordinates:
          wght: 400
      - coordinates:
          wght: 500
      - familyName: "Texturina Exotic"
        styleName: "Medium"
        coordinates:
          wght: 500
        ...
      Texturina-Italic[wght].ttf:
      - coordinates:
          wght: 700
        ...
    vttSources:
      Texturina[wght].ttf: vtt-roman.ttx
      Texturina-Italic[wght].ttf: vtt-italic.ttx
    ...

To build a font family from the command line, use:

> gftools builder path/to/config.yaml

The config file may contain the following keys. The `sources` key is
required, all others have sensible defaults:

-   `sources`: Required. An array of Glyphs, UFO or designspace source
    files.

-   `logLevel`: Debugging log level. Defaults to `INFO`.

-   `stylespaceFile`: A statmake `.stylespace` file.

-   `stat`: A STAT table configuration. This may be either a list of
    axes and values as demonstrated above, or a dictionary mapping each
    variable font to a per-source list. If neither `stylespaceFile` or
    `stat` are provided, a STAT table is generated automatically using
    `gftools.stat`. The Flags key's values are explained in the [OpenType
    spec](https://learn.microsoft.com/en-us/typography/opentype/spec/stat#flags).

-   `instances`: A list of static font TTF instances to generate from
    each variable font as demonstrated above. If this argument isn\'t
    provided, static TTFs will be generated for each instance that is
    specified in the source files.

-   `buildVariable`: Build variable fonts. Defaults to true.

-   `buildStatic`: Build static fonts (OTF or TTF depending on `$buildOTF`
    and `$buildTTF`). Defaults to true.

-   `buildOTF`: Build OTF fonts. Defaults to true.

-   `buildTTF`: Build TTF fonts. Defaults to true.

-   `buildWebfont`: Build WOFF2 fonts. Defaults to `$buildStatic`.

-   `outputDir`: Where to put the fonts. Defaults to `../fonts/`

-   `vfDir`: Where to put variable fonts. Defaults to
    `$outputDir/variable`.

-   `ttDir`: Where to put TrueType static fonts. Defaults to
    `$outputDir/ttf`.

-   `otDir`: Where to put CFF static fonts. Defaults to
    `$outputDir/otf`.

-   `woffDir`: Where to put WOFF2 static fonts. Defaults to
    `$outputDir/webfonts`.

-   `cleanUp`: Whether or not to remove temporary files. Defaults to
    `true`.

-   `autohintTTF`: Whether or not to autohint TTF files. Defaults to
    `true`.

-   `ttfaUseScript`: Whether or not to detect a font\'s primary script
    and add a `-D<script>` flag to ttfautohint. Defaults to `false`.

-   `vttSources`: To patch a manual VTT hinting program (ttx format) to
    font binaries.

-   `axisOrder`: STAT table axis order. Defaults to fvar order.

-   `familyName`: Family name for variable fonts. Defaults to family
    name of first source file.

-   `flattenComponents`: Whether to flatten components on export.
    Defaults to `true`.

-   `decomposeTransformedComponents`: Whether to decompose transformed
    components on export. Defaults to `true`.

-   `googleFonts`: Whether this font is destined for release on Google
    Fonts. Used by GitHub Actions. Defaults to `false`.

-   `category`: If this font is destined for release on Google Fonts, a
    list of the categories it should be catalogued under. Used by GitHub
    Actions. Must be set if `googleFonts` is set.

-   `fvarInstanceAxisDflts`: Mapping to set every fvar instance\'s
    non-wght axis value e.g if a font has a wdth and wght axis, we can
    set the wdth to be 100 for every fvar instance. Defaults to `None`

-   `expandFeaturesToInstances`: Resolve all includes in the sources\'
    features, so that generated instances can be compiled without
    errors. Defaults to `true`.

-   `reverseOutlineDirection`: Reverse the outline direction when
    compiling TTFs (no effect for OTFs). Defaults to fontmake\'s
    default.

-   `removeOutlineOverlaps`: Remove overlaps when compiling fonts.
    Defaults to fontmake\'s default.

-   `glyphData`: An array of custom GlyphData XML files for with glyph
    info (production name, script, category, subCategory, etc.).
    Used only for Glyphs sources.
