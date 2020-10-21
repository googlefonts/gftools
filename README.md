# Google Fonts Tools

This project contains tools used for working with the Google Fonts collection, plus **Google Fonts Glyph Set Documentation** in the [/encodings](https://github.com/googlefonts/gftools/tree/master/Lib/gftools/encodings) subdirectory. While these tools are primarily intended for contributors to the Google Fonts project, anyone who works with fonts could find them useful.

The tools and files under this directory are available under the Apache License v2.0, for details see [LICENSE](LICENSE)

## Google Fonts Official Glyph Sets (Encodings)

<https://github.com/googlefonts/gftools/tree/master/Lib/gftools/encodings>

## Usage Examples

Compare fonts:

    gftools compare-font font1.ttf font2.ttf

Add a METADATA.pb to a family directory

    gftools add-font ../ofl/newfamily

Sanity check a family directory:

    gftools sanity-check --repair_script=/tmp/fix.py ../ofl/josefinsans
    gftools sanity-check --repair_script=/tmp/fix.py --fix_type=fsSelection ../ufl

Check a font family against the same family hosted on Google Fonts:

    gftools qa [fonts.ttf] -gfb -a -o qa

Check a variable font family against the same family as static fonts:

    gftools qa -f [vf_fonts] -fb [static_fonts] --diffenator --diffbrowsers -o ~/path/out

Add a DSIG table to a font

    gftools fix-dsig font1.ttf

Fix a non hinted font

    gftools fix-nonhinting font_in.ttf font_out.ttf

Package and PR a family update to google/fonts. Much more detailed [documentation](./docs/gftools-packager).

    gftools packager "Family Sans" path/to/local/google/fonts -py

## Installation

Please install these tools using pip:

    pip install gftools

If you need to use `gftools qa`, you will need to install Harfbuzz, Cairo, FreeType and pkg-config. These can be installed on OS X using homebrew:

    brew install cairo freetype harfbuzz pkg-config

Once You have installed these system packages, install gftools using the following command:

    pip install 'gftools[qa]'


### Requirements and Dependencies

These tools depend on the submodule `GlyphsInfo`.
Make sure the submodule is up to date by running:

    git submodule update --init --recursive

`gftool packager` needs the command line `git` program in a version >= Git 2.5 (Q2 2015) in order to perform a shallow clone (`--depth 1`) of the font upstream repository and branch. This is not supported by pygit2/libgit2 yet.

### Google Fonts API Key

In order to use the scripts **gftools qa** and **gftools family-html-snippet**, you will need to generate a Google Fonts api key, https://developers.google.com/fonts/. You will then need to create a new text file located on your system at `~/.gf-api-key` (where ~ is your home directory), which contains the following:

```
[Credentials]
key = your-newly-generated-googlefonts-api-key

```

**Upstream project repos**

* https://github.com/schriftgestalt/GlyphsInfo
* https://github.com/google/google-apputils
* https://github.com/google/protobuf
* https://github.com/behdad/fonttools
