"""gftools transfer_vtt_hintgs

Match nodes by euclidean distance, instead of node index

Usage:

gftools transfer-vtt-hints src.ttf dst.ttf
"""

from pyparsing import (
    Word,
    alphas,
    Suppress,
    delimitedList,
    nums,
    Group,
    ZeroOrMore,
    Optional,
    cppStyleComment,
    Literal,
    Combine,
)
import fontTools
from fontTools.ttLib import TTFont
from fontTools.misc.cliTools import makeOutputFileName
from copy import deepcopy
import argparse
from types import SimpleNamespace


__all__ = ["transfer_hints"]


MAXP_ATTRS = {
    "maxZones",
    "maxTwilightPoints",
    "maxStorage",
    "maxFunctionDefs",
    "maxInstructionDefs",
    "maxStackElements",
    "maxSizeOfInstructions",
}


# TSI3 parser
tsi3_func_name = Word(alphas)  # Function name consists of alphabetic characters
integer = Combine(Optional("-") + Word(nums)).setParseAction(
    lambda t: int(t[0])
)  # Define integers and convert them to int
tsi3_args = (
    Suppress("(") + Optional(delimitedList(integer)) + Suppress(")")
)  # Arguments within parentheses, optional for functions with no arguments

# Combine the grammar to define a function call, ensuring each call is grouped
tsi3_function_call = Group(tsi3_func_name("name") + tsi3_args("args"))

# Define a grammar for multiple function calls, ignoring comments
tsi3_parser = ZeroOrMore(tsi3_function_call)
tsi3_parser.ignore(cppStyleComment)


# TSI1 parser
tsi1_func_name = Word(
    alphas + "[]>=" + nums
)  # Function name consists of alphabetic characters
comma = Literal(",")  # Comma separator
tsi1_args = Suppress(Optional(comma)) + Optional(
    delimitedList(integer)
)  # Arguments within parentheses, optional for functions with no arguments

# Combine the grammar to define a function call, ensuring each call is grouped
tsi1_function_call = Group(tsi1_func_name("name") + tsi1_args("args"))

# Define a grammar for multiple function calls, ignoring comments
tsi1_parser = ZeroOrMore(tsi1_function_call)
tsi1_parser.ignore(cppStyleComment)


def _glyph_index_map(source_glyph, source_glyphset, target_glyph, target_glyphset):
    # Euclidiean node matching
    res = {}
    seen = set()
    for idx_a, [x_a, y_a] in enumerate(source_glyph.getCoordinates(source_glyphset)[0]):
        res[idx_a] = (float("inf"), float("inf"))
        for idx_b, (x_b, y_b) in enumerate(
            target_glyph.getCoordinates(target_glyphset)[0]
        ):
            if idx_b in seen:
                continue
            distance = ((x_a - x_b) ** 2 + (y_a - y_b) ** 2) ** 0.5
            if distance < res[idx_a][0]:
                res[idx_a] = (distance, idx_b)
        key = res[idx_a][1]
        seen.add(key)
    return {idx_a: idx_b for idx_a, (_, idx_b) in res.items()}


def _update_tsi3(instructions: list[SimpleNamespace], glyph_map):
    # Instruction node positions
    NODE_FUNCTION_ARGUMENTS = {
        "ResYAnchor": [0],
        "ResYDist": [0, 1],
        "YShift": [0, 1],
        "YAnchor": [0],
        "YInterpolate": [0, 1, 2],
        "YDist": [0, 1],
        "YDelta": [0, 1],
        "YDownToGrid": [0],
        "YIPAnchor": [0, 1, 2],
        "YLink": [0, 1],
        "YUpToGrid": [0],
    }

    res = []
    for instruction in instructions:
        if instruction.name in NODE_FUNCTION_ARGUMENTS:
            for idx in NODE_FUNCTION_ARGUMENTS[instruction.name]:
                instruction.args[idx] = glyph_map[instruction.args[idx]]
        res.append(instruction)
    return res


def _tsi3_to_string(instructions: list[SimpleNamespace]):
    res = []
    for instruction in instructions:
        res.append(instruction.name + "(" + ",".join(map(str, instruction.args)) + ")")
    return "\n".join(res)


def _update_tsi1(instructions: list[SimpleNamespace], gid_map, glyf):
    new_instructions = []
    component_idx = 0
    for instruction in instructions:
        if instruction.name == "OFFSET[R]":
            component = glyf.components[component_idx]
            instruction.args[0] = gid_map[component.glyphName]
            instruction.args[1] = component.x
            instruction.args[2] = component.y
            component_idx += 1
        new_instructions.append(instruction)
    return new_instructions


def transfer_tsi3(source_font: TTFont, target_font: TTFont, glyph_name: str):
    existing_program = source_font["TSI3"].glyphPrograms[glyph_name]
    glyph_map = _glyph_index_map(
        source_font["glyf"][glyph_name],
        source_font["glyf"],
        target_font["glyf"][glyph_name],
        target_font["glyf"],
    )
    if any(v == float("inf") for k, v in glyph_map.items()):
        target_font["TSI3"].glyphPrograms[glyph_name] = ""
        return glyph_name
    glyph_instructions = tsi3_parser.parseString(existing_program)
    updated_instructions = _update_tsi3(glyph_instructions, glyph_map)
    target_font["TSI3"].glyphPrograms[glyph_name] = _tsi3_to_string(
        updated_instructions
    )
    return None


def _tsi1_to_string(instructions: list[SimpleNamespace]):
    res = []
    for instruction in instructions:
        if len(instruction.args) == 0:
            res.append(instruction.name)
        else:
            res.append(instruction.name + "," + ",".join(map(str, instruction.args)))
    return "\n".join(res)


def transfer_tsi1(source_font: TTFont, target_font: TTFont, glyph_name: str):
    existing_program = source_font["TSI1"].glyphPrograms[glyph_name]
    target_glyph_order = {
        name: idx for idx, name in enumerate(target_font.getGlyphOrder())
    }
    glyph_instructions = tsi1_parser.parseString(existing_program)
    updated_instructions = _update_tsi1(
        glyph_instructions, target_glyph_order, target_font["glyf"][glyph_name]
    )
    target_font["TSI1"].glyphPrograms[glyph_name] = _tsi1_to_string(
        updated_instructions
    )


def printer(msg, items):
    items = sorted(items, key=lambda x: x[0])
    item_list = "\n".join([f"{idx},{name}" for idx, name in items])
    print(f"{msg}:\nGID,Glyph_Name:\n{item_list}\n")


def transfer_hints(source_font: TTFont, target_font: TTFont, skip_components=False):
    target_font["TSI0"] = fontTools.ttLib.newTable("TSI0")
    target_font["TSI2"] = fontTools.ttLib.newTable("TSI2")
    # Add a blank TSI1 and TSI3 table
    for tbl in ("TSI1", "TSI3"):
        target_font[tbl] = fontTools.ttLib.newTable(tbl)
        setattr(target_font[tbl], "glyphPrograms", {})
        setattr(target_font[tbl], "extraPrograms", {})

    target_gid = {name: idx for idx, name in enumerate(target_font.getGlyphOrder())}
    matched_glyphs = (
        source_font["TSI1"].glyphPrograms.keys() & target_font.getGlyphSet().keys()
    )
    unmatched_glyphs = (
        target_font.getGlyphSet().keys() - source_font.getGlyphSet().keys()
    )
    unmatched_glyphs = set((target_gid[g], g) for g in unmatched_glyphs)

    missing_hints = set()
    for glyph_name in matched_glyphs:
        source_is_composite = source_font["glyf"][glyph_name].isComposite()
        target_is_composite = target_font["glyf"][glyph_name].isComposite()
        if source_is_composite and target_is_composite and not skip_components:
            transfer_tsi1(source_font, target_font, glyph_name)
        elif source_is_composite and not target_is_composite:
            missing_hints.add((target_gid[glyph_name], glyph_name))
            target_font["TSI1"].glyphPrograms[glyph_name] = ""
            target_font["TSI3"].glyphPrograms[glyph_name] = ""
        elif not source_is_composite and target_is_composite:
            target_font["TSI1"].glyphPrograms[glyph_name] = ""
            target_font["TSI3"].glyphPrograms[glyph_name] = ""
            missing_hints.add((target_gid[glyph_name], glyph_name))
        elif glyph_name in source_font["TSI3"].glyphPrograms:
            failed_glyph = transfer_tsi3(source_font, target_font, glyph_name)
            if failed_glyph:
                missing_hints.add((target_gid[failed_glyph], failed_glyph))
        else:
            missing_hints.add((target_gid[glyph_name], glyph_name))

    if unmatched_glyphs:
        printer("Following glyphs are new", unmatched_glyphs)
    if missing_hints:
        printer(
            "Following glyphs are missing hints, have changed from components to outlines, or points differ too much",
            missing_hints,
        )

    # Copy over other hinting tables
    for tbl in ("TSI5", "fpgm", "prep", "TSIC", "cvt "):
        target_font[tbl] = deepcopy(source_font[tbl])

    # Copy over relevant maxp attributes
    for maxp_attr in MAXP_ATTRS:
        setattr(target_font["maxp"], maxp_attr, getattr(source_font["maxp"], maxp_attr))

    # Copy over extraPrograms
    for tbl in ("TSI1", "TSI3"):
        target_font[tbl].extraPrograms = source_font[tbl].extraPrograms

    transferred = len(matched_glyphs) - len(missing_hints)
    total = len(target_font.getGlyphSet().keys())
    print(f"Transferred {transferred}/{total} glyphs")
    print("Please still check glyphs look good on Windows platforms")


def main(args=None):
    parser = argparse.ArgumentParser(description="Transfer VTT hints between two fonts")
    parser.add_argument("source", type=str, help="Source font file")
    parser.add_argument("target", type=str, help="Target font file")
    parser.add_argument(
        "--skip-components",
        action="store_true",
        default=False,
        help="Skip component hints",
    )
    output = parser.add_mutually_exclusive_group(required=False)
    output.add_argument("-o", "--out", type=str, help="Output file")
    output.add_argument(
        "-i", "--inplace", action="store_true", help="Inplace modification"
    )
    args = parser.parse_args(args)

    source_font = TTFont(args.source)
    target_font = TTFont(args.target)

    transfer_hints(source_font, target_font, args.skip_components)

    if args.inplace:
        target_font.save(args.target)
    elif args.out:
        target_font.save(args.out)
    else:
        fp = makeOutputFileName(
            args.target, outputDir=None, extension=None, overWrite=False
        )
        target_font.save(fp)


if __name__ == "__main__":
    main()
