from fontTools.otlLib.builder import buildStatTable, _addName
from fontTools.ttLib import TTFont


def gen_stat(variable_fonts, config):
    for filepath in variable_fonts:
        # Create appropriate axes definitions
        tt = TTFont(filepath)
        axis_definition = create_axis_definition(tt, config)
        if not axis_definition:
            continue
        buildStatTable(tt, axis_definition)
        update_fvar(tt)
        tt.save(filepath)


def create_axis_definition(ttFont, config):
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
