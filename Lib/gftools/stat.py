"""Generate STAT tables for a Variable Font Family

This module exports the functions "gen_stat_tables" and
"gen_stat_tables_from_config" which can be used to
generate a STAT table for each font in a Variable Font Family.

The STAT AxisValues are constructed using the Google Font's Axis Registry,
https://github.com/google/fonts/tree/master/axisregistry

The function should be able to make STAT tables for any family with the
following properties:
- All fonts contain the same amount of fvar axes
- All fvar axes have the same ranges
"""
from fontTools.ttLib import TTFont
from fontTools.otlLib.builder import buildStatTable
from gftools.utils import font_stylename, font_familyname, font_is_italic
from gftools.axisreg import axis_registry
import os
import logging


__all__ = ["gen_stat_tables", "gen_stat_tables_from_config", "ELIDABLE_AXIS_VALUE_NAME"]


log = logging.getLogger(__name__)


ELIDABLE_AXIS_VALUE_NAME = 0x2


# TODO we may have more of these. Please note that some applications may not
# implement variable font style linking.
LINKED_VALUES = {
    "wght": (400, 700),
    "ital": (0.0, 1.0),
}


def _gen_stat_from_fvar(ttFont, axis_reg=axis_registry):
    """Generate a STAT table using a ttFont's fvar and the GF axis registry.

    Args:
        axis_reg: gf axis registry
        ttFont: a TTFont instance
    """
    fvar = ttFont["fvar"]

    axis_defaults = {a.axisTag: a.defaultValue for a in fvar.axes}
    results = {}
    for axis in fvar.axes:
        axis_tag = axis.axisTag
        if axis_tag not in axis_reg:
            log.warning(
                f"'{axis_tag}' isn't in our axis registry. Please open an issue "
                "to discuss the inclusion of this axis, "
                "https://github.com/google/fonts/issues"
            )
            continue
        # Add Axis Record
        results[axis_tag] = {
            "tag": axis_tag,
            "name": axis_reg[axis_tag].display_name,
            "values": [],
        }
        # Add Axis Values
        min_value = axis.minValue
        max_value = axis.maxValue
        for fallback in axis_reg[axis_tag].fallback:
            if fallback.value >= min_value and fallback.value <= max_value:
                axis_value = _add_axis_value(fallback.name, fallback.value)
                # set elided axis_values
                # if axis is opsz, we want to use the fvar default
                if axis_tag == "opsz" and axis_defaults[axis_tag] == fallback.value:
                    axis_value["flags"] |= ELIDABLE_AXIS_VALUE_NAME
                # for all other weights, we want to use the axis reg default
                elif fallback.value == axis_reg[axis_tag].default_value:
                    axis_value["flags"] |= ELIDABLE_AXIS_VALUE_NAME
                results[axis_tag]["values"].append(axis_value)
    return results


def _axes_in_family_name_records(ttFonts):
    results = set()
    for ttFont in ttFonts:
        familyname = font_familyname(ttFont)
        stylename = font_stylename(ttFont)
        results |= set(stylename_to_axes(familyname)) | set(
            stylename_to_axes(stylename)
        )
    return results


def stylename_to_axes(font_style, axis_reg=axis_registry):
    """Get axis names for stylename particles using the axis registry e.g

    "Condensed Bold Italic" --> ["wdth", "wght", "ital"]

    Args:
        axis_reg: gf axis registry
        font_style: str

    Returns: list(str,...)
    """
    axes = []
    unparsed_tokens = []

    tokens = font_style.split()
    for token in tokens:
        axis = style_token_to_axis(token)
        if axis:
            axes.append(axis)
        else:
            unparsed_tokens.append(token)

    if unparsed_tokens:
        log.debug(
            f"Following tokens were not found in the Axis Registry "
            f"{list(unparsed_tokens)}. Axis Values will not be created "
            f"for these tokens"
        )
    return axes


def style_token_to_axis(string, axis_reg=axis_registry):
    # Condensed --> width
    for axis_tag, axis in axis_reg.items():
        for fallback in axis.fallback:
            if fallback.name == string:
                return axis_tag
    return None


def _append_non_fvar_axes_to_stat(
    ttFont, stat_table, axes_in_family_name_records, axis_reg=axis_registry
):
    stylename = font_stylename(ttFont)
    familyname = font_familyname(ttFont)
    style = f"{familyname} {stylename}"
    # {"wght": "Regular", "ital": "Roman", ...}
    font_axes_in_namerecords = {style_token_to_axis(t): t for t in style.split()}

    # Add axes to ttFont which exist across the family but are not in the
    # ttFont's fvar
    axes_missing = axes_in_family_name_records - set(stat_table)
    for axis in axes_missing:
        axis_record = {
            "tag": axis,
            "name": axis_reg[axis].display_name,
            "values": [],
        }
        # Add Axis Value for axis which isn't in the fvar or ttFont style
        # name/family name
        if axis not in font_axes_in_namerecords:
            axis_record["values"].append(_default_axis_value(axis, axis_reg))
        # Add Axis Value for axis which isn't in the fvar but does exist in
        # the ttFont style name/family name
        else:
            style_name = font_axes_in_namerecords[axis]
            value = next(
                (i.value for i in axis_reg[axis].fallback if i.name == style_name),
                None,
            )
            axis_value = _add_axis_value(style_name, value)
            axis_record["values"].append(axis_value)
        stat_table[axis] = axis_record
    return stat_table


def _seen_axis_values(stat_tables):
    seen_axis_values = {}
    for stat_tbl in stat_tables:
        for axis_tag, axis in stat_tbl.items():
            if axis_tag not in seen_axis_values:
                seen_axis_values[axis_tag] = set()
            seen_axis_values[axis_tag] |= set(i["value"] for i in axis["values"])
    return seen_axis_values


def _add_linked_axis_values_to_stat(stat_table, seen_axis_values):
    for axis_tag, axis in stat_table.items():
        if axis_tag not in LINKED_VALUES:
            continue
        start, end = LINKED_VALUES[axis_tag]
        for axis_value in axis["values"]:
            if axis_value["value"] == start and end in seen_axis_values[axis_tag]:
                axis_value["linkedValue"] = end
    return stat_table


def _add_elided_axis_values_to_stat(stat_table, elided_values):
    """Overwrite which Axis Values should be elided.

    Args:
        stat: a stat table
        elided_values: dict structured as {"axisTag": [100,200 ...]}"""
    for axis_tag, axis in stat_table.items():
        if axis_tag not in elided_values:
            continue
        for val in axis["values"]:
            if val["value"] in elided_values[axis_tag]:
                val["flags"] |= ELIDABLE_AXIS_VALUE_NAME
            else:
                val["flags"] &= ~ELIDABLE_AXIS_VALUE_NAME
    return stat_table


def _add_axis_value(style_name, value, flags=0x0, linked_value=None):
    value = {"value": value, "name": style_name, "flags": flags}
    if linked_value:
        value["linkedValue"] = linked_value
    return value


def _default_axis_value(axis, axis_reg=axis_registry):
    axis_record = axis_reg[axis]
    default_value = axis_record.default_value
    default_name = next(
        (i.name for i in axis_record.fallback if i.value == default_value), None
    )
    return _add_axis_value(default_name, default_value, flags=ELIDABLE_AXIS_VALUE_NAME)


def validate_axis_order(axis_order, seen_axes):
    axes_not_ordered = seen_axes - set(axis_order)
    if axes_not_ordered:
        raise ValueError(f"Axis order arg is missing {axes_not_ordered} axes.")


def validate_family_fvar_tables(ttFonts):
    """Google Fonts requires all VFs in a family to have the same
    amount of fvar axes and each fvar axis should have the same range.

    Args:
        ttFonts: an iterable containing TTFont instances
    """
    for ttFont in ttFonts:
        if "fvar" not in ttFont:
            raise ValueError(f"Font is missing fvar table")

    failed = False
    src_fvar = ttFonts[0]["fvar"]
    src_axes = {a.axisTag: a.__dict__ for a in src_fvar.axes}
    for ttFont in ttFonts:
        fvar = ttFont["fvar"]
        axes = {a.axisTag: a.__dict__ for a in fvar.axes}
        if len(axes) != len(src_axes):
            failed = True
            break
        for axis_tag in axes:
            if axes[axis_tag]["minValue"] != src_axes[axis_tag]["minValue"]:
                failed = True
            if axes[axis_tag]["maxValue"] != src_axes[axis_tag]["maxValue"]:
                failed = True
            # TODO should this fail if default values are different?
    if failed:
        raise ValueError("fvar axes are not consistent across the family")


def _update_fvar_nametable_records(ttFont, stat_table):
    """Add postscript names to fvar instances and add nameID 25 to a
    font's nametable"""
    nametable = ttFont["name"]
    fvar = ttFont["fvar"]
    family_name = font_familyname(ttFont)
    axes_with_one_axis_value = [
        a["values"][0] for a in stat_table if len(a["values"]) == 1
    ]
    tokens = [v["name"] for v in axes_with_one_axis_value]
    tokens = [t for t in tokens if t not in family_name.split()]
    ps_tokens = "".join(t for t in tokens)

    # Variations PostScript Name Prefix
    ps_prefix = f"{family_name}{ps_tokens}".replace(" ", "")
    for rec in [(25, 1, 0, 0), (25, 3, 1, 0x409)]:
        nametable.setName(ps_prefix, *rec)

    # Add or update fvar instance postscript names
    for instance in fvar.instances:
        subfamily_id = instance.subfamilyNameID
        subfamily_name = nametable.getName(subfamily_id, 3, 1, 0x409).toUnicode()
        for token in tokens:
            subfamily_name = subfamily_name.replace(token, "")
            if subfamily_name == "":
                subfamily_name = "Regular"
        ps_name = f"{ps_prefix}-{subfamily_name}".replace(" ", "")
        # Remove ps name records if they already exist
        if instance.postscriptNameID != 65535:
            nametable.removeNames(nameID=instance.postscriptNameID)
        instance.postscriptNameID = nametable.addName(ps_name)


def gen_stat_tables(
    ttFonts, axis_order, elided_axis_values=None, axis_reg=axis_registry
):
    """
    Generate a stat table for each font in a family using the Google Fonts
    Axis Registry.

    Args:
        ttFonts: an iterable containing ttFont instances
        axis_order: a list containing the axis order
        elided_axis_values: a dict containing axes and their values to elide
        e.g {"wght": [400], "wdth": [100]}
        axis_reg: Google Fonts axis registry
    """
    # Heuristic:
    # 1. Gen a STAT table for each font using their fvar tables only
    # 2. Collect all the axes which exist in every font's family name and
    #    and style name
    # 3. Add further Axis Records to each font's stat table for the axes we
    #    found in step 2. Only add them if the stat table doesn't contain them
    #    already.
    # 4. Add an AxisValue to each of the Axes Records we added in step 3.
    #    For each axis in each font, do the following:
    #      a. If a font's name table contains the axis and it is not in the
    #         fvar, we will create a new Axis Value using the axis registry
    #         fallbacks.
    #      b. If a font's name table doesn't contain the axis, we will create a
    #         new Axis Value based the default values found in the axis registry
    #
    #         Example:
    #
    #            Test Case:
    #            Axes in family names: ["wdth", "wght", "ital"]
    #            Font StyleName = "Condensed Bold"
    #            Axes in font fvar = ["wght"]
    #
    #            a result:
    #            axisValue = {"name": "Condensed", "value": 75.0}
    #            "Condensed" exists in our axis registry as a fallback in the
    #            wdth axis
    #
    #            b result:
    #            AxisValue = {"name": "Roman", "value": 0.0, flags=0x2}
    #            Since there isn't an ital token in the Font family name or
    #            style name, the AxisValue will be based on the default values
    #            for the axis in our axis registry
    #
    # 4. For each stat table, update Axis Values which should be linked
    # 5. For each stat table, update Axis Values which should be elided based
    #    on the user arg elided_axis_values (optional)
    # 6. For each stat table, sort axes based on the arg axis_order
    # 7. Use fontTools to build each stat table for each font
    validate_family_fvar_tables(ttFonts)
    stat_tables = [_gen_stat_from_fvar(f) for f in ttFonts]
    axes_in_family_name_records = _axes_in_family_name_records(ttFonts)
    stat_tables = [
        _append_non_fvar_axes_to_stat(ttFont, stat, axes_in_family_name_records)
        for ttFont, stat in zip(ttFonts, stat_tables)
    ]
    seen_axis_values = _seen_axis_values(stat_tables)
    stat_tables = [
        _add_linked_axis_values_to_stat(s, seen_axis_values) for s in stat_tables
    ]
    if elided_axis_values:
        stat_tables = [
            _add_elided_axis_values_to_stat(s, elided_axis_values) for s in stat_tables
        ]

    # TODO make axis_order an optional arg. We can only do this once we
    # have established an axis order in the axis registry
    validate_axis_order(axis_order, set(seen_axis_values.keys()))
    assert len(stat_tables) == len(ttFonts)
    axis_order = [a for a in axis_order if a in seen_axis_values.keys()]
    for stat_table, ttFont in zip(stat_tables, ttFonts):
        stat_table = [stat_table[axis] for axis in axis_order]
        _update_fvar_nametable_records(ttFont, stat_table)
        buildStatTable(ttFont, stat_table)

def gen_stat_tables_from_config(stat, varfonts, has_italic=None):
    """
    Generate a stat table for each font in a family from a Python configuration.

    Args:
        stat: either a dictionary or list as described below
        varfonts: a list of variable TTFont instances
        has_italic: a boolean indicating whether the family contains an italic.
            If not provided, the stylename of the font files are inspected to
            determine if any of them contain the word ``Italic``.

    The ``stat`` parameter should normally be a list of axis dictionaries in the
    format used by ``buildStatTable``. This list should *not* contain an entry
    for the ``ital`` axis, as this entry will be generated as appropriate for
    each font if ``has_italic`` is True.

    For example::

        varfonts = [
            "Source-Regular-VF[wdth].ttf",
            "Source-Italic-VF[wdth].ttf"
        ]
        stat = [
                { "tag":"wdth", "name": "Width", "values": [ ... ] }
        ]

    Alternately, to allow different STAT table entries for each font, the ``stat``
    parameter may be a dictionary, whose keys are source IDs (usually source
    filenames) corresponding to the appropriate entry in the ``varfonts``
    dictionary and whose values are the list of axis dictionaries for the font.
    Note that in this case, the axes list is passed to ``buildStatTable`` with
    no further manipulation, meaning that if you want an ``ital`` axis, you
    should specify it manually as part of the dictionary.

    For example::

        stat = {
            "Font[wght].ttf": [
                { "tag":"wdth", "name": "Width", "values": [ ... ] },
                { "tag":"ital", "name": "Italic", "values": [ ... ] }
            ],
            "Font-Italic[wght].ttf": [
                { "tag":"wdth", "name": "Width", "values": [ ... ] },
                { "tag":"ital", "name": "Italic", "values": [ ... ] }
            ]
        }
    """
    assert all("fvar" in f for f in varfonts)
    # Check we have no italic
    if isinstance(stat, list):
        if has_italic is None:
            has_italic = any(font_is_italic(f) for f in varfonts)
        if has_italic:
            for ax in stat:
                if ax["name"] == "ital":
                    raise ValueError("ital axis should not appear in stat config")
            ital_stat_for_roman = {
                "name": "Italic", "tag": "ital",
                "values": [dict(value=0, name="Roman", flags=0x2, linkedValue=1)]
            }
            ital_stat_for_italic = {
                "name": "Italic", "tag": "ital",
                "values": [dict(value=1, name="Italic")]
            }

            stat.append({})  # We will switch this entry between Roman and Italic

    for ttFont in varfonts:
        filename = os.path.basename(ttFont.reader.file.name)
        if isinstance(stat, dict):
            if filename not in stat:
                raise ValueError("Filename %s not found in stat dictionary" % filename)
            this_stat = stat[filename]
        else:
            if has_italic:
                if font_is_italic(ttFont):
                    stat[-1] = ital_stat_for_italic
                else:
                    stat[-1] = ital_stat_for_roman
            this_stat = stat
        buildStatTable(ttFont, this_stat)
