from ttfautohint import ttfautohint
from fontTools.ttLib import TTFont
from ttfautohint.options import parse_args as ttfautohint_parse_args
from fontTools import unicodedata
from collections import Counter
import sys

AUTOHINT_SCRIPTS = [
    "adlm",
    "arab",
    "armn",
    "avst",
    "bamu",
    "beng",
    "buhd",
    "cakm",
    "cans",
    "cari",
    "cher",
    "copt",
    "cprt",
    "cyrl",
    "deva",
    "dsrt",
    "ethi",
    "geor",
    "geok",
    "glag",
    "goth",
    "grek",
    "gujr",
    "guru",
    "hebr",
    "hmnp",
    "kali",
    "khmr",
    "khms",
    "knda",
    "lao",
    "latn",
    "latb",
    "latp",
    "lisu",
    "mlym",
    "medf",
    "mong",
    "mymr",
    "nkoo",
    "olck",
    "orkh",
    "osge",
    "osma",
    "rohg",
    "saur",
    "shaw",
    "sinh",
    "sund",
    "taml",
    "tavt",
    "telu",
    "tfng",
    "thai",
    "vaii",
    "yezi",
]


def autohint_script_tag(ttFont):
    script_count = Counter()
    for x in ttFont.getBestCmap().keys():
        for script in unicodedata.script_extension(chr(x)):
            if script[0] != "Z":
                script_count[script] += 1
    # If there isn't a clear winner, give up
    if (
        len(script_count) > 2
        and script_count.most_common(2)[0][1] < 2 * script_count.most_common(2)[1][1]
    ):
        return

    most_common = script_count.most_common(1)
    if most_common:
        script = most_common[0][0].lower()
        if script in AUTOHINT_SCRIPTS:
            return script


def autohint(infile, outfile, args=None, add_script=False):
    font = TTFont(infile)
    if not args:
        args = []
        if add_script:
            script = autohint_script_tag(font)
            if script:
                args.append("-D" + script)

    ttfautohint(**ttfautohint_parse_args([infile, outfile, *args]))
