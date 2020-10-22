"""
Functions to fix fonts so they conform to the Google Fonts
specification
https://github.com/googlefonts/gf-docs/tree/master/Spec
"""
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import ttProgram
from fontTools.ttLib.tables._f_v_a_r import NamedInstance
from gftools.util.google_fonts import _KNOWN_WEIGHTS


__all__ = [
    "add_dummy_dsig",
    "fix_unhinted_font",
    "fix_hinted_font",
    "fix_fs_type",
    "fix_fs_selection",
    "fix_mac_style",
    "font_stylename",
    "fix_fvar_instances",
]


WEIGHTS = _KNOWN_WEIGHTS
for style in ("Hairline", ""):
    del WEIGHTS[style]
WEIGHTS = {v:k for k,v in WEIGHTS.items()}


def add_dummy_dsig(ttFont):
    """Add a dummy dsig table to a font. Older versions of MS Word
    require this table.

    Args:
        ttFont: a TTFont instance
    """
    newDSIG = newTable("DSIG")
    newDSIG.ulVersion = 1
    newDSIG.usFlag = 0
    newDSIG.usNumSigs = 0
    newDSIG.signatureRecords = []
    ttFont.tables["DSIG"] = newDSIG


def fix_unhinted_font(ttFont):
    """Improve the appearance of an unhinted font on Win platforms by:
        - Overwriting the GASP table with a newtable that has a single
          which range which is set to smooth.
        - Overwriting the prep table with a new table that includes new
          instructions.
    
    Args:
        ttFont: a TTFont instance
    """
    gasp = newTable("gasp")
    # Set GASP so all sizes are smooth
    gasp.gaspRange = {0xFFFF: 15}

    program = ttProgram.Program()
    assembly = ["PUSHW[]", "511", "SCANCTRL[]", "PUSHB[]", "4", "SCANTYPE[]"]
    program.fromAssembly(assembly)

    prep = newTable("prep")
    prep.program = program

    ttFont["gasp"] = gasp
    ttFont["prep"] = prep


def fix_hinted_font(ttFont):
    """Improve the appearance of a hinted font on Win platforms by enabling
    the head table's flag 3

    Args:
        ttFont: a TTFont instance
    """
    head_flags = ttFont["head"].flags
    if head_flags != head_flags | (1 << 3):
        ttFont["head"].flags |= 1 << 3
    else:
        print("Skipping. Font already has bit 3 enabled")


def fix_fs_type(ttFont):
    """Set the OS/2 table's fsType flag to 0 (Installable embedding)

    Args:
        ttFont: a TTFont instance
    """
    ttFont['OS/2'].fsType = 0


def fix_fs_selection(ttFont):
    """Fix the OS/2 table's fsSelection

    Args:
        ttFont: a TTFont instance
    """
    stylename = font_stylename(ttFont)
    fs_selection = ttFont["OS/2"].fsSelection

    # turn off all bits except for bit 7 (USE_TYPO_METRICS)
    fs_selection &= 0b10000000

    if "Italic" in stylename:
        fs_selection |= 0b1
    if stylename in ["Bold", "Bold Italic"]:
        fs_selection |= 0b100000
    # enable Regular bit for all other styles
    if stylename not in ["Bold", "Bold Italic"] and "Italic" not in stylename:
        fs_selection |= 0b1000000
    ttFont["OS/2"].fsSelection = fs_selection


def fix_mac_style(ttFont):
    """Fix the head table's macStyle

    Args:
        ttFont: a TTFont instance
    """
    stylename = font_stylename(ttFont)
    mac_style = 0b0
    if "Italic" in stylename:
        mac_style |= 0b10
    if stylename in ["Bold", "Bold Italic"]:
        mac_style |= 0b1
    ttFont["head"].macStyle = mac_style


def font_stylename(ttFont):
    """Get a font's stylename using the name table. Since our fonts use the
    RIBBI naming model, use the Typographic SubFamily Name (NAmeID 17) if it
    exists, otherwise use the SubFamily Name (NameID 2)

    Args:
        ttFont: a TTFont instance
    """
    name = ttFont["name"]
    style_record = name.getName(2, 3, 1, 0x409) or name.getName(17, 3, 1, 0x409)
    if not style_record:
        raise ValueError(
            "Cannot find stylename since NameID 2 and NameID 16 are missing"
        )
    return style_record.toUnicode()


def fix_fvar_instances(ttFont):
    """Replace a variable font's fvar instances with a set of instances that
    conform to the Google Fonts instance spec:
    https://github.com/googlefonts/gf-docs/tree/master/Spec#fvar-instances

    Args:
        ttFont: a TTFont instance
    """
    fvar = ttFont["fvar"]
    default_axis_vals = {a.axisTag: a.defaultValue for a in fvar.axes}
    nametable = ttFont["name"]
    subfamily_name = nametable.getName(2, 3, 1, 0x409)
    if not subfamily_name:
        raise ValueError("Name table is missing subFamily Name Record")
    is_italic = "italic" in nametable.getName(2, 3, 1, 0x409).toUnicode().lower()
    font_is_roman_and_italic = any(a for a in ("slnt", "ital") if a in default_axis_vals)

    wght_axis = next((a for a in fvar.axes if a.axisTag == "wght"), None)
    wght_min = int(wght_axis.minValue)
    wght_max = int(wght_axis.maxValue)

    def gen_instances(is_italic):
        results = []
        for wght_val in range(wght_min, wght_max+100, 100):
            name = WEIGHTS[wght_val] if not is_italic else f"{WEIGHTS[wght_val]} Italic"
            name = name.replace("Regular Italic", "Italic")

            coordinates = default_axis_vals
            coordinates["wght"] = wght_val

            inst = NamedInstance()
            inst.subfamilyNameID = nametable.addName(name)
            inst.coordinates = coordinates
            results.append(inst)
        return results

    instances = []
    if font_is_roman_and_italic:
        for bool_ in (False, True):
            instances += gen_instances(is_italic=bool_)
    elif font_is_italic:
        instances += gen_instances(is_italic=True)
    else:
        instances += gen_instances(is_italic=False)
    fvar.instances = instances

