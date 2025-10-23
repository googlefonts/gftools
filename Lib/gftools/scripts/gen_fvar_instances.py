from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._f_v_a_r import NamedInstance
import argparse
import yaml
import os


def gen_fvar_instances(font, instances):
    if "fvar" not in font:
        raise ValueError("The provided font is not a variable font.")

    # rm old instances
    font["fvar"].instances = []

    font_axes = {
        a.axisTag: (a.minValue, a.defaultValue, a.maxValue) for a in font["fvar"].axes
    }
    default_coordinates = {a.axisTag: a.defaultValue for a in font["fvar"].axes}
    nametable = font["name"]
    for inst in instances:
        inst_coords = {}
        for axis in font_axes:
            if axis in inst["coordinates"]:
                inst_coords[axis] = inst["coordinates"][axis]
            else:
                print(
                    "Warning: Instance '{}' is missing axis '{}', using default value.".format(
                        inst["name"], axis
                    )
                )
                inst_coords[axis] = font_axes[axis][1]  # default value

        new_instance = NamedInstance()
        subfamilyNameID = nametable.findMultilingualName(
            {"en": inst["name"]}, windows=True, mac=False
        )
        if subfamilyNameID in {2, 17} and inst_coords == default_coordinates:
            # Instances can only reuse an existing name ID 2 or 17 if they are at the
            # default location across all axes, see:
            # https://github.com/fonttools/fonttools/issues/3825.
            new_instance.subfamilyNameID = subfamilyNameID
        else:
            new_instance.subfamilyNameID = nametable.addMultilingualName(
                {"en": inst["name"]}, windows=True, mac=False, minNameID=256
            )
        new_instance.coordinates = inst_coords
        font["fvar"].instances.append(new_instance)


def main(args=None):
    parser = argparse.ArgumentParser(
        description="Generate fvar instances for variable fonts from a YAML file."
    )
    parser.add_argument("fonts", nargs="+", help="Path to the font file.")
    parser.add_argument("src", help="Path to the YAML file defining fvar instances.")
    out_group = parser.add_mutually_exclusive_group(required=True)
    out_group.add_argument("--out", "-o", help="Output dir for fonts")
    out_group.add_argument(
        "--inplace", action="store_true", default=False, help="Overwrite input files"
    )
    args = parser.parse_args(args)

    fonts = [TTFont(f) for f in args.fonts]
    config = yaml.load(open(args.src), Loader=yaml.SafeLoader)
    for font in fonts:
        filename = os.path.basename(font.reader.file.name)
        gen_fvar_instances(font, config[filename])
        font.save(font.reader.file.name)

    if args.inplace:
        for font in fonts:
            font.save(font.reader.file.name)
    elif args.out:
        if not os.path.isdir(args.out):
            os.mkdir(args.out)
        for font in fonts:
            font.save(os.path.join(args.out, os.path.basename(font.reader.file.name)))


if __name__ == "__main__":
    main()
