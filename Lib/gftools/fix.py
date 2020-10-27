"""
Functions to fix fonts so they conform to the Google Fonts
specification
https://github.com/googlefonts/gf-docs/tree/master/Spec
"""
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import ttProgram
from fontTools.ttLib.tables._f_v_a_r import NamedInstance
from gftools.util.google_fonts import _KNOWN_WEIGHTS
from copy import deepcopy
import logging


log = logging.getLogger(__name__)


__all__ = [
    "remove_tables",
    "add_dummy_dsig",
    "fix_unhinted_font",
    "fix_hinted_font",
    "fix_fs_type",
    "fix_weight_class",
    "fix_fs_selection",
    "fix_mac_style",
    "font_stylename",
    "fix_fvar_instances",
    "update_nametable",
    "fix_nametable",
]


WEIGHT_NAMES = deepcopy(_KNOWN_WEIGHTS)

WEIGHTS = _KNOWN_WEIGHTS
for style in ["Hairline"]:
    del WEIGHTS[style]
    del WEIGHT_NAMES[style]
WEIGHTS = {v: k for k, v in WEIGHTS.items()}


UNWANTED_TABLES = frozenset(
    ["FFTM", "TTFA", "TSI0", "TSI1", "TSI2", "TSI3", "TSI5", "prop", "MVAR",]
)


def remove_tables(ttFont, tables=None):
    """Remove unwanted tables from a font. The unwanted tables must belong
    to the UNWANTED_TABLES set.

    Args:
        ttFont: a TTFont instance
        tables: an iterable containing tables remove
    """
    tables_to_remove = UNWANTED_TABLES if not tables else frozenset(tables)
    font_tables = frozenset(ttFont.keys())

    tables_not_in_font = tables_to_remove - font_tables
    if tables_not_in_font:
        log.warning(
            f"Cannot remove tables '{list(tables_not_in_font)}' since they are "
            f"not in the font."
        )

    essential_tables = tables_to_remove - UNWANTED_TABLES
    if essential_tables:
        log.warning(
            f"Cannot remove tables '{list(essential_tables)}' since they are required"
        )

    tables_to_remove = UNWANTED_TABLES & font_tables & tables_to_remove
    if not tables_to_remove:
        return
    log.info(f"Removing tables '{list(tables_to_remove)}' from font")
    for tbl in tables_to_remove:
        del ttFont[tbl]


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
    ttFont["OS/2"].fsType = 0


def fix_weight_class(ttFont):
    """Set the OS/2 table's usWeightClass so it conforms to GF's supported
    styles:
    https://github.com/googlefonts/gf-docs/tree/master/Spec#supported-styles

    Args:
        ttFont: a TTFont instance
    """
    stylename = font_stylename(ttFont)

    for style in sorted(WEIGHTS.values(), key=lambda k: len(k), reverse=True):
        italic_variant = f"{style} Italic"
        if style in stylename or italic_variant in stylename:
            ttFont["OS/2"].usWeightClass = WEIGHT_NAMES[style]
            return
    raise ValueError(
        f"Cannot determine usWeightClass because font style, '{stylename}' "
        "doesn't have a weight token which is in our known "
        "weights, '{WEIGHTS.keys()}'"
    )


def fix_fs_selection(ttFont):
    """Fix the OS/2 table's fsSelection

    Args:
        ttFont: a TTFont instance
    """
    stylename = font_stylename(ttFont)
    tokens = set(stylename.split())
    fs_selection = ttFont["OS/2"].fsSelection

    # turn off all bits except for bit 7 (USE_TYPO_METRICS)
    fs_selection &= 0b10000000

    if "Italic" in tokens:
        fs_selection |= 1 << 0
    if set(["Bold"]) & tokens:
        fs_selection |= 1 << 5
    # enable Regular bit for all other styles
    if not tokens & set(["Bold", "Italic"]):
        fs_selection |= 1 << 6
    ttFont["OS/2"].fsSelection = fs_selection


def fix_mac_style(ttFont):
    """Fix the head table's macStyle

    Args:
        ttFont: a TTFont instance
    """
    stylename = font_stylename(ttFont)
    tokens = set(stylename.split())
    mac_style = 0
    if "Italic" in tokens:
        mac_style |= 1 << 1
    if "Bold" in tokens:
        mac_style |= 1 << 0
    ttFont["head"].macStyle = mac_style


def font_stylename(ttFont):
    """Get a font's stylename using the name table. Since our fonts use the
    RIBBI naming model, use the Typographic SubFamily Name (NAmeID 17) if it
    exists, otherwise use the SubFamily Name (NameID 2)

    Args:
        ttFont: a TTFont instance
    """
    name = ttFont["name"]
    style_record = name.getName(17, 3, 1, 0x409) or name.getName(2, 3, 1, 0x409)
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
    font_is_roman_and_italic = any(
        a for a in ("slnt", "ital") if a in default_axis_vals
    )

    wght_axis = next((a for a in fvar.axes if a.axisTag == "wght"), None)
    wght_min = int(wght_axis.minValue)
    wght_max = int(wght_axis.maxValue)

    def gen_instances(is_italic):
        results = []
        for wght_val in range(wght_min, wght_max + 100, 100):
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


def update_nametable(ttFont, family_name=None, style_name=None):
    """..."""
    nametable = ttFont["name"]

    # Remove nametable records which are not Win US English since they
    # are redundant
    platforms = set()
    for rec in nametable.names:
        platforms.add((rec.platformID, rec.platEncID, rec.langID))
    platforms_to_remove = platforms ^ set([(3, 1, 0x409)])
    if platforms_to_remove:
        log.warning(f"Removing records which are not Win US English, {list(platforms_to_remove)}")
        for platformID, platEncID, langID in platforms_to_remove:
            nametable.removeNames(platformID=platformID, platEncID=platEncID, langID=langID)

    if not family_name:
        family_name = nametable.getName(16, 3, 1, 0x409) or nametable.getName(
            1, 3, 1, 0x409
        )
        family_name = family_name.toUnicode()

    if not style_name:
        style_name = nametable.getName(17, 3, 1, 0x409) or nametable.getName(
            2, 3, 1, 0x409
        )
        style_name = style_name.toUnicode()

    is_ribbi = style_name in ("Regular", "Bold", "Italic", "Bold Italic")

    nameids = {}
    if is_ribbi:
        nameids[1] = family_name
        nameids[2] = style_name
    else:
        tokens = style_name.split()
        family_name_suffix = " ".join([t for t in tokens if t not in ["Italic"]])
        nameids[1] = f"{family_name} {family_name_suffix}"
        nameids[2] = "Regular" if "Italic" not in tokens else "Italic"
        nameids[16] = f"{family_name} {' '.join(t for t in tokens if t not in list(WEIGHT_NAMES) + ['Italic'])}"
        nameids[17] = f"{' '.join(t for t in tokens if t in list(WEIGHT_NAMES) + ['Italic'])}"

    family_name = nameids.get(16) or nameids.get(1)
    style_name = nameids.get(17) or nameids.get(2)

    # create NameIDs 3, 4, 6
    nameids[4] = f"{family_name} {style_name}"
    nameids[6] = f"{family_name.replace(' ', '')}-{style_name.replace(' ', '')}"
    nameids[3] = _unique_name(ttFont, nameids)

    # Pass through all records and replace occurences of the old family name
    # with the new family name
    current_family_name = nametable.getName(16, 3, 1, 0x409) or nametable.getName(
        1, 3, 1, 0x409
    )
    current_family_name = current_family_name.toUnicode()
    for record in nametable.names:
        string = record.toUnicode()
        if current_family_name in string:
            nametable.setName(
                string.replace(current_family_name, family_name),
                record.nameID,
                record.platformID,
                record.platEncID,
                record.langID,
            )

    # Remove previous typographic names
    for nameID in (16, 17):
        nametable.removeNames(nameID=nameID)

    # Update nametable with new names
    for nameID, string in nameids.items():
        nametable.setName(string, nameID, 3, 1, 0x409)


def _unique_name(ttFont, nameids):
    font_version = _font_version(ttFont)
    vendor = ttFont["OS/2"].achVendID.strip()
    ps_name = nameids[6]
    return f"{font_version};{vendor};{ps_name}"


def _font_version(font, platEncLang=(3, 1, 0x409)):
    nameRecord = font["name"].getName(5, *platEncLang)
    if nameRecord is None:
        return f'{font["head"].fontRevision:.3f}'
    # "Version 1.101; ttfautohint (v1.8.1.43-b0c9)" --> "1.101"
    # Also works fine with inputs "Version 1.101" or "1.101" etc
    versionNumber = nameRecord.toUnicode().split(";")[0]
    return versionNumber.lstrip("Version ").strip()


def fix_nametable(ttFont):
    name = ttFont["name"]
    # make family_name its own function
    family_name = name.getName(16, 3, 1, 0x409) or name.getName(1, 3, 1, 0x409)
    family_name = family_name.toUnicode()
    style_name = font_stylename(font)
    update_nametable(ttFont, family_name, style_name)
