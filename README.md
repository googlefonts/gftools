# Google Fonts Tools

This project contains tools used for working with the Google Fonts collection, plus **Google Fonts Glyph Set Documentation** in the [/encodings](/encodings) subdirectory. While these tools are primarily intended for contributors to the Google Fonts project, anyone who works with fonts could find them useful.

The tools and files under this directory are available under the Apache License v2.0, for details see [LICENSE](LICENSE)

## Usage Examples

Compare fonts:

    gftools compare-font font1.ttf font2.ttf

Add a METADATA.pb to a family directory

    gftools add-font ../ofl/newfamily

Sanity check a family directory:

    gftools sanity-check --repair_script=/tmp/fix.py ../ofl/josefinsans
    gftools sanity-check --repair_script=/tmp/fix.py --fix_type=fsSelection ../ufl

## Installation

Please install these tools using our [pip](https://pip.pypa.io/en/stable/installing/) package hosted on [PyPI](https://pypi.org/project/gftools/):

    pip install --upgrade gftools

### Requirements and Dependencies

These tools are intended to work with both Python 2.7 and Python 3, If a tool isn't working with Python 3 please make an issue. Python 2 support is being phased out and `gftools` will be Python 3 only soon. Pull Requests welcome! :)

These tools depend on the submodule `GlyphsInfo`.
Make sure the submodule is up to date by running:

    git submodule update --init --recursive


### Google Fonts API Key

In order to use the scripts **gftools qa** and **gftools family-html-snippet**, you will need to generate a Google Fonts api key, https://developers.google.com/fonts/. You will then need to create a new file located on your system at `~/.gf-api-key`, which contains the following:

```
[Credentials]
key = your-newly-generated-googlefonts-api-key

```

**Upstream project repos**

* https://github.com/schriftgestalt/GlyphsInfo
* https://github.com/google/google-apputils
* https://github.com/google/protobuf
* https://github.com/behdad/fonttools
