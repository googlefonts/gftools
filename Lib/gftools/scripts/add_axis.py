#!/usr/bin/env python3
"""Create or author Google Fonts axisregistry {AXIS_NAME}.textproto files."""
import sys
import argparse
from gftools.axes_pb2 import AxisProto, FallbackProto
from google.protobuf import text_format
from fontTools.ttLib import TTFont


parser = argparse.ArgumentParser(
    prog="gftools add-axis",
    description=__doc__,
)

parser.add_argument("font", type=str, help="The font file to the axis values from.")


class ProgramAbortError(Exception):
    pass


class UserAbortError(Exception):
    pass


def _get_fvar_axis(name_table, fvar_table):
    axes = []
    for axis in fvar_table.axes:
        axes.append(
            (
                axis,
                f"{name_table.getName(axis.axisNameID, 3, 1, 0x0409)} {axis.axisTag}",
            )
        )
    axes.sort(key=lambda a: a[0].axisTag)
    choices = "\n".join(
        [f"  {index}: {label}" for index, (_, label) in enumerate(axes)]
    )
    question = "Found axes:\n" f"{choices}" "\n" "pick one by number (e.g. 0), q=quit:"
    while True:
        try:
            answer = input(question).strip()
            if answer == "q":
                raise UserAbortError()
            index = int(answer)  # raises ValueError
            fvar_axis, _ = axes[index]  # raises IndexError
        except (ValueError, IndexError):
            # must try again
            continue
        print(f"You picked: {fvar_axis.axisTag}.")
        return fvar_axis


def _get_fallbacks_gen(name_table, stat_axis_index, AxisValue):
    for stat_axis_value in AxisValue:
        if stat_axis_value.Format in (1, 3):
            if stat_axis_value.AxisIndex == stat_axis_index:
                yield (
                    name_table.getName(stat_axis_value.ValueNameID, 3, 1, 0x0409),
                    stat_axis_value.Value,
                )
        elif stat_axis_value.Format == 4:
            for avr in stat_axis_value.AxisValueRecord:
                if avr.AxisIndex == stat_axis_index:
                    yield (
                        name_table.getName(stat_axis_value.ValueNameID, 3, 1, 0x0409),
                        avr.Value,
                    )
        else:
            print(
                f"SKIP STAT AxisValue can't handel Format {stat_axis_value.Format} "
                f"({name_table.getName(stat_axis_value.ValueNameID, 3, 1, 0x0409)})"
            )


def add_axis(font: str):
    axis_proto = AxisProto()
    ttFont = TTFont(font)
    name_table = ttFont["name"]
    try:
        fvar_table = ttFont["fvar"]
    except KeyError:
        raise ProgramAbortError("No fvar present")
    fvar_axis = _get_fvar_axis(name_table, fvar_table)

    # Axis tag
    axis_proto.tag = fvar_axis.axisTag
    # Display name for axis, e.g. "Optical size" for 'opsz'
    # Like 'Name' in
    # https://docs.microsoft.com/en-us/typography/opentype/spec/dvaraxistag_opsz
    # name_table.getName(
    #           NameID,
    #           <Platform ID: 3 = Windows>,
    #           <encodingID, Platform-specific encoding ID: 1 = Unicode BMP>,
    #           <Language ID: 0x0409 = 1033 = en_us>)
    axis_proto.display_name = (
        f"{name_table.getName(fvar_axis.axisNameID, 3, 1, 0x0409)}"
    )
    # Lower bound for the axis
    axis_proto.min_value = fvar_axis.minValue
    # The default position to use and to prefer for exemplars
    axis_proto.default_value = fvar_axis.defaultValue
    # Upper bound for the axis
    axis_proto.max_value = fvar_axis.maxValue
    # Input values for this axis must aligned to 10^precision
    axis_proto.precision = 1  # ask user?
    # Short descriptive paragraph
    axis_proto.description = (  # ask user?
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod"
        " tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim"
        " veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea"
        " commodo consequat. Duis aute irure dolor in reprehenderit in voluptate"
        " velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint"
        " occaecat cupidatat non proident, sunt in culpa qui officia deserunt"
        " mollit anim id est laborum."
    )

    fallback_proto = FallbackProto()
    fallback_proto.name = "Default"
    fallback_proto.value = fvar_axis.defaultValue
    axis_proto.fallback.append(fallback_proto)
    # Is the axis fallback only?
    axis_proto.fallback_only = False

    text_proto = text_format.MessageToString(
        axis_proto, as_utf8=True, use_index_order=True
    )
    filename = f"{axis_proto.display_name.lower()}.textproto"
    with open(filename, "x") as f:
        f.write(text_proto)
    print(f"DONE create {filename}!")


def main(args=None):
    try:
        args = parser.parse_args(args)
        add_axis(args.font)
    except UserAbortError:
        print("Aborted by user!")
        sys.exit(1)
    except ProgramAbortError as e:
        print(f"Aborted by program: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
