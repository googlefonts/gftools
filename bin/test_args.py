#!/usr/bin/env python3
import sys

target_modules = [
    "gftools-build-font2ttf",
    "gftools-fix-ascii-fontmetadata",
    "gftools-fix-familymetadata",
    "gftools-fix-fsselection",
    "gftools-fix-gasp",
    "gftools-fix-glyph-private-encoding",
    "gftools-fix-glyphs",
    "gftools-fix-nameids",
    # "gftools-fix-nonhinting", #this one do not even use argparse module
    "gftools-fix-ttfautohint",
    "gftools-fix-vendorid",
    "gftools-fix-vertical-metrics",
    "gftools-list-panose",
    "gftools-list-weightclass",
    "gftools-list-widthclass",
    "gftools-metadata-vs-api",
    "gftools-update-families",
]


help_text = {}
for module_name in target_modules:
    target = __import__(module_name)
    help_text[module_name] = target.parser.format_help()

# We need to extend this list with our
# minimal common interface for all scripts:
mandatory_args = ["[-h]"]

# This is a catch-all that contains most args
# used in some of the current scripts.
# We probably want to reduce this list to the bare minimum
# and maybe make some of these mandatory.
optional_args = [
    "[-v]",
    "[--autofix]",
    "[--csv]",
    "[--verbose]",
    "[-a ASCENTS]",
    "[-ah ASCENTS_HHEA]",
    "[-at ASCENTS_TYPO]",
    "[-aw ASCENTS_WIN]",
    "[-d DESCENTS]",
    "[-dh DESCENTS_HHEA]",
    "[-dt DESCENTS_TYPO]",
    "[-dw DESCENTS_WIN]",
    "[-l LINEGAPS]",
    "[-lh LINEGAPS_HHEA]",
    "[-lt LINEGAPS_TYPO]",
    "[--api API]",
    "[--cache CACHE]",
    "[--set SET]",
    "[--platform PLATFORM]",
    "[--id ID]",
    "[--ignore-copy-existing-ttf]",
    "[--with-otf]",
    "[-e EXISTING]",
]

failed = False
for arg in mandatory_args:
    missing = []
    for module_name in help_text.keys():
        if arg not in help_text[module_name]:
            missing.append(module_name)

    if missing != []:
        failed = True
        print(
            (
                "ERROR: These modules lack the {} command line argument:"
                "\nERROR:\t{}\n"
            ).format(arg, "\nERROR:\t".join(missing))
        )

import re

for module_name in help_text.keys():
    text = help_text[module_name]
    args = re.findall("(\[\-[^\[]*\])", text)
    #  print (args)
    #  print ("INFO: {}: {}".format(module_name, text))
    for arg in args:
        if arg not in optional_args + mandatory_args:
            print(
                (
                    "WARNING: Module {} has cmdline argument {}"
                    " which is not in the list of optional ones."
                    ""
                ).format(module_name, arg)
            )

# TODO: we also need to verify positional attributes like font and ttfont

if failed:
    sys.exit(
        "Some errors were detected in the command-line"
        " arguments of the Font Bakery scripts."
    )
