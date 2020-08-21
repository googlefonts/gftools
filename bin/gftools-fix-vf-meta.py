#!/usr/bin/env python3
"""
Add a STAT table to a weight only variable font.

This script can also add STAT tables to a variable font family which
consists of two fonts, one for Roman, the other for Italic.
Both of these fonts must also only contain a weight axis.

For variable fonts with multiple axes, write a python script which
uses fontTools.otlLib.builder.buildStatTable e.g
https://github.com/googlefonts/literata/blob/master/sources/gen_stat.py

The generated STAT tables use format 2 Axis Values. These are needed in
order for Indesign to work.

Special mention to Thomas Linard for reviewing the output of this script.


Usage:

Single family:
gftools fix-vf-meta FontFamily[wght].ttf

Roman + Italic family:
gftools fix-vf-meta FontFamily[wght].ttf FontFamily-Italic[wght].ttf
"""
from fontTools.otlLib.builder import buildStatTable
from fontTools.ttLib import TTFont
import argparse


WGHT = {
    100: "Thin",
    200: "ExtraLight",
    300: "Light",
    400: "Regular",
    500: "Medium",
    600: "SemiBold",
    700: "Bold",
    800: "ExtraBold",
    900: "Black",
    1000: "ExtraBlack",
}


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
        wght_val = instance.coordinates["wght"]
        desired_inst_info = WGHT[wght_val]
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
            "nominalValue": wght_val,
        }
        if inst["nominalValue"] == 400:
            inst["flags"] = 0x2
        results.append(inst)

    # Dynamically generate rangeMinValues and rangeMaxValues
    entries = [results[0]["nominalValue"]] + \
              [i["nominalValue"] for i in results] + \
              [results[-1]["nominalValue"]]
    for i, entry in enumerate(results):
        entry["rangeMinValue"] = (entries[i] + entries[i+1]) / 2
        entry["rangeMaxValue"] = (entries[i+1] + entries[i+2]) / 2

    # Format 2 doesn't support linkedValues so we have to append another
    # Axis Value (format 3) for Reg which does support linkedValues
    if has_bold:
        inst = {
            "name": "Regular",
            "value": 400,
            "flags": 0x2,
            "linkedValue": 700
        }
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
        if wght_val not in WGHT:
            raise ValueError(f"Unsupported wght coord '{wght_val}'. Coord "
                              "needs to be in {WGHT.keys()}")

        # Update instance subfamilyNameID
        wght_name = WGHT[wght_val]
        inst_name = wght_name
        if is_italic:
            inst_name = f"{inst_name} Italic"
            inst_name = inst_name.replace("Regular Italic", "Italic")
        ttfont['name'].setName(inst_name, inst.subfamilyNameID, 3, 1, 0x409)
        if has_mac_names:
            ttfont['name'].setName(inst_name, inst.subfamilyNameID, 1, 0, 0)

        # Add instance psName
        ps_name = f"{vf_ps_name}-{wght_name}"
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

