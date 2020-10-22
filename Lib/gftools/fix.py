"""
Functions to fix fonts so they conform to the Google Fonts
specification
https://github.com/googlefonts/gf-docs/tree/master/Spec
"""
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import ttProgram


def add_dummy_dsig(ttFont):
    """Add a dummy dsig table to a font. Older versions of MS Word
    require this table.

    Args:
        ttFont: a TTFont instance
    """
    newDSIG = ttLib.newTable("DSIG")
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
