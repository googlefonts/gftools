from ttfautohint import ttfautohint
from fontTools.ttLib import TTFont
from ttfautohint.options import parse_args as ttfautohint_parse_args
from gftools.utils import primary_script
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


def autohint_script_tag(ttFont, discount_latin=False):
    script = primary_script(ttFont, discount_latin=discount_latin)
    if script in AUTOHINT_SCRIPTS:
        return script
    return


def autohint(infile, outfile, args=None, add_script=False):
    font = TTFont(infile)
    if not args:
        args = []
        if add_script:
            script = autohint_script_tag(font)
            if script:
                args.append("-D" + script)
    args_dict = ttfautohint_parse_args([infile, outfile, *args])
    if not args_dict:
        raise ValueError("Could not parse arguments")
    ttfautohint(**args_dict)
