# Google Fonts Tools

This project contains miscellaneous tools for working with the Google Fonts collection, plus **Google Fonts Glyph Set Documentation** in the [/encodings](/encodings) subdirectory.

The tools and files under this directory are available under the Apache License v2.0, for details see [LICENSE](LICENSE)

## Usage

Compare fonts:

    gftools compare-font font1.ttf font2.ttf

Add a METADATA.pb to a family directory

    gftools add-font ../ofl/newfamily

Sanity check a family directory:

    gftools sanity-check --repair_script=/tmp/fix.py ../ofl/josefinsans
    gftools sanity-check --repair_script=/tmp/fix.py --fix_type=fsSelection ../ufl

## Installation

Please install these tools using our pip package hosted on PyPI:

    sudo easy_install pip
    pip install --upgrade gftools

### Requirements and Dependencies

These tools are intended to work with Python 2.7 systems. 
While these tools may work with Python 3.x, if so, that's a happy accident.
Pull Requests welcome! :)

These tools depend on the submodule `GlyphsInfo`.
Make sure the submodule is up to date by running:

    git submodule update --init --recursive

Upstream project repos:

* https://github.com/schriftgestalt/GlyphsInfo
* https://github.com/google/google-apputils
* https://github.com/google/protobuf
* https://github.com/behdad/fonttools
