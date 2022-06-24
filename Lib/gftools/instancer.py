from fontTools.varLib.instancer import instantiateVariableFont, OverlapMode
from axisregistry import build_name_table
from gftools.fix import fix_fs_selection, fix_mac_style
from gftools.utils import font_stylename, font_familyname


__all__ = ["gen_static_font"]


def gen_static_font(
    var_font, axes, family_name=None, style_name=None, keep_overlaps=False, dst=None
):
    """Generate a GF spec compliant static font from a variable font.

    Args:
        var_font: a variable TTFont instance
        family_name: font family name
        style_name: font style name
        axes: dictionary containing axis positions e.g {"wdth": 100, "wght": 400}
        keep_overlaps: If true, keep glyph overlaps
        dst: Optional. Path to output font

    Returns:
        A TTFont instance or a filepath if an out path has been provided
    """
    if "fvar" not in var_font:
        raise ValueError("Font is not a variable font!")
    if not keep_overlaps:
        keep_overlaps = OverlapMode.REMOVE

    # if the axes dict doesn't include all fvar axes, add default fvar vals to it
    fvar_dflts = {a.axisTag: a.defaultValue for a in var_font["fvar"].axes}
    for k, v in fvar_dflts.items():
        if k not in axes:
            axes[k] = v

    update_style_name = True if not style_name else False
    static_font = instantiateVariableFont(
        var_font, axes, overlap=keep_overlaps, updateFontNames=update_style_name
    )

    if not family_name:
        family_name = font_familyname(static_font)
    if not style_name:
        style_name = font_stylename(static_font)
    # We need to reupdate the name table using our own update function
    # since GF requires axis particles which are not wght or ital to
    # be appended to the family name. See func for more details.
    build_name_table(static_font, family_name, style_name)
    fix_fs_selection(static_font)
    fix_mac_style(static_font)
    static_font["OS/2"].usWidthClass = 5
    if dst:
        static_font.save(dst)
    return static_font
