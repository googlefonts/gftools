"""
Functions to fix fonts so they conform to the Google Fonts
specification
https://github.com/googlefonts/gf-docs/tree/master/Spec
"""
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import ttProgram


__all__ = [
    "add_dummy_dsig",
    "fix_unhinted_font",
    "fix_hinted_font",
    "fix_fs_selection",
    "fix_mac_style",
    "font_stylename",
]


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
