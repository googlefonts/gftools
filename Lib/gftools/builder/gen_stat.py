from fontTools.otlLib.builder import buildStatTable, _addName
from fontTools.ttLib import TTFont


# Should probably be in utils/util.styles...
def font_is_italic(ttfont):
    stylename = ttfont["name"].getName(2, 3, 1, 0x409).toUnicode()
    return True if "Italic" in stylename else False


# Should probably be in gftools.util.styles...
WGHT_NAMES = {
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


def gen_stat(variable_fonts, config):
    has_italic = len(variable_fonts) > 1
    for filepath in variable_fonts:
        # Create appropriate axes definitions
        tt = TTFont(filepath)
        axis_definition = create_axis_definition(tt, config, has_italic)
        if not axis_definition:
            continue
        buildStatTable(tt, axis_definition)
        update_fvar(tt)
        tt.save(filepath)


def create_axis_definition(ttFont, config):
    nametable = ttfont["name"]
    instances = ttfont["axes"].instances

    if has_italic:
        pass


def update_fvar(ttfont):
    fvar = ttfont["fvar"]
    nametable = ttfont["name"]
    family_name = nametable.getName(16, 3, 1, 1033) or nametable.getName(1, 3, 1, 1033)
    family_name = family_name.toUnicode()
    font_style = "Italic" if "Italic" in ttfont.reader.file.name else "Roman"
    ps_family_name = f"{family_name.replace(' ', '')}{font_style}"
    nametable.setName(ps_family_name, 25, 3, 1, 1033)
    for instance in fvar.instances:
        instance_style = nametable.getName(
            instance.subfamilyNameID, 3, 1, 1033
        ).toUnicode()
        instance_style = instance_style.replace("Italic", "").strip()
        if instance_style == "":
            instance_style = "Regular"
        ps_name = f"{ps_family_name}-{instance_style}"
        instance.postscriptNameID = _addName(nametable, ps_name, 256)


def build_wght_axis_values(ttfont):
    results = []
    nametable = ttfont["name"]
    instances = ttfont["fvar"].instances
    has_bold = any([True for i in instances if i.coordinates["wght"] == 700])
    for instance in instances:
        wght_val = instance.coordinates["wght"]
        desired_inst_info = WGHT[wght_val]
        name = nametable.getName(instance.subfamilyNameID, 3, 1, 1033).toUnicode()
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
    entries = (
        [results[0]["nominalValue"]]
        + [i["nominalValue"] for i in results]
        + [results[-1]["nominalValue"]]
    )
    for i, entry in enumerate(results):
        entry["rangeMinValue"] = (entries[i] + entries[i + 1]) / 2
        entry["rangeMaxValue"] = (entries[i + 1] + entries[i + 2]) / 2

    # Format 2 doesn't support linkedValues so we have to append another
    # Axis Value (format 3) for Reg which does support linkedValues
    if has_bold:
        inst = {"name": "Regular", "value": 400, "flags": 0x2, "linkedValue": 700}
        results.append(inst)
    return results
