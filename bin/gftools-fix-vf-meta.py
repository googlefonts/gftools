#!/usr/bin/env python3
"""
Add a STAT table to a weight only variable font.

This script can also add STAT tables to a variable font family which
consists of two fonts, one for Roman, the other for Italic.
Both of these fonts must also only contain a weight axis.

For variable fonts with multiple axes, use DaMa statmake:
https://github.com/daltonmaag/statmake


Usage:

Single family:
gftools fix-vf-meta FontFamily[wght].ttf

Roman + Italic family:
gftools fix-vf-meta FontFamily[wght].ttf FontFamily-Italic[wght].ttf
"""
from gftools.util.google_fonts import _KNOWN_WEIGHTS
from fontTools.otlLib.builder import buildStatTable
from fontTools.ttLib import TTFont
import argparse


WGHT_NAMES = {v:k for k,v in _KNOWN_WEIGHTS.items() if k != "Hairline"}
WGHT_NAMES[400] = "Regular"
WGHT_NAMES[1000] = "ExtraBlack"


def font_is_italic(ttfont):
    stylename = ttfont["name"].getName(2, 3, 1, 0x409).toUnicode()
    return True if "Italic" in stylename else False


def font_has_mac_names(ttfont):
    for record in ttfont['name'].names:
        if record.platformID == 1:
            return True
    return False


def build_stat(roman_font, italic_font=None):
    roman_wght_axis = dict(
        tag="wght",
        name="Weight",
        values=build_axis_values(roman_font),
    )
    roman_axes = [roman_wght_axis]
    if italic_font:
    # We need to create a new Italic axis in the Roman font
        roman_axes.append(
            dict(
                tag="ital",
                name="Italic",
                values=[
                    dict(
                        name="Roman",
                        flags=2,
                        value=0.0,
                        linkedValue=1.0,
                    )
                    
                ]
            )
        )
        italic_wght_axis = dict(
            tag="wght",
            name="Weight",
            values=build_axis_values(italic_font),
        )
        italic_axes = [italic_wght_axis]
        italic_axes.append(
            dict(
                tag="ital",
                name="Italic",
                values=[
                    dict(
                        name="Italic",
                        value=1.0,
                    )
                ]
            )
        )
        buildStatTable(italic_font, italic_axes)
    buildStatTable(roman_font, roman_axes)


def build_axis_values(ttfont):
    results = []
    nametable = ttfont['name']
    instances = ttfont['fvar'].instances
    has_bold = any([True for i in instances if i.coordinates['wght'] == 700])
    for instance in instances:
        name = nametable.getName(
            instance.subfamilyNameID,
            3,
            1,
            1033
        ).toUnicode()
        name = name.replace("Italic", "").strip()
        if name == "":
            name = "Regular"
        inst = {
            "name": name,
            "value": instance.coordinates['wght'],
        }
        if inst["value"] == 400:
            inst["flags"] = 0x2
            if has_bold:
                inst["linkedValue"] = 700
        results.append(inst)
    return results


def update_nametable(ttfont):
    """
    - Add nameID 25
    - Update fvar instance names and add fvar instance postscript names
    """
    is_italic = font_is_italic(ttfont)
    has_mac_names = font_has_mac_names(ttfont)

    # Add nameID 25
    # https://docs.microsoft.com/en-us/typography/opentype/spec/name#name-ids
    vf_ps_name = _add_nameid_25(ttfont, is_italic, has_mac_names)

    # Update fvar instances
    instances = ttfont["fvar"].instances
    for inst in instances:
        wght_val = inst.coordinates["wght"]
        if wght_val not in WGHT_NAMES:
            raise ValueError(f"Fvar instance coord {wght_val} needs to be "
                              "within range 0-1000 and be a multiple of 100")

        # Update instance subfamilyNameID
        inst_name = WGHT_NAMES[wght_val]
        if is_italic:
            inst_name = f"{inst_name} Italic"
            inst_name = inst_name.replace("Regular Italic", "Italic")
        ttfont['name'].setName(inst_name, inst.subfamilyNameID, 3, 1, 0x409)
        if has_mac_names:
            ttfont['name'].setName(inst_name, inst.subfamilyNameID, 1, 0, 0)

        # Add instance psName
        ps_name = f"{vf_ps_name}-{WGHT_NAMES[wght_val]}"
        ps_name_id = ttfont['name'].addName(ps_name)
        inst.postscriptNameID = ps_name_id


def _add_nameid_25(ttfont, is_italic, has_mac_names):
    name = ttfont['name'].getName(16, 3, 1, 1033) or \
        ttfont['name'].getName(1, 3, 1, 1033)
    name = name.toUnicode().replace(" ", "")
    if is_italic:
        name = f"{name}Italic"
    else:
        name = f"{name}Roman"
    ttfont['name'].setName(name, 25, 3, 1, 1033)
    if has_mac_names:
        ttfont['name'].setName(name, 25, 1, 0, 0)
    return name


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__
    )
    parser.add_argument("fonts", nargs="+", help=(
            "Paths to font files. Fonts must be part of the same family."
        )
    )
    args = parser.parse_args()
    fonts = args.fonts

    # This monstrosity exists so we don't break the v1 api.
    italic_font = None
    if len(fonts) > 2:
        raise Exception(
            "Can only add STAT tables to a max of two fonts. "
            "Run gftools fix-vf-meta --help for usage instructions"
        )
    elif len(fonts) == 2:
        if "Italic" in fonts[0]:
            italic_font = TTFont(fonts[0])
            roman_font = TTFont(fonts[1])
        elif "Italic" in fonts[1]:
            italic_font = TTFont(fonts[1])
            roman_font = TTFont(fonts[0])
        else:
            raise Exception("No Italic font found!")
    else:
        roman_font = TTFont(fonts[0])
    update_nametable(roman_font)
    if italic_font:
        update_nametable(italic_font)
    build_stat(roman_font, italic_font)
    roman_font.save(roman_font.reader.file.name + ".fix")
    if italic_font:
        italic_font.save(italic_font.reader.file.name + ".fix")


if __name__ == "__main__":
    main()

