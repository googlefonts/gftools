from fontTools.otlLib.builder import buildStatTable
from gftools.fix import font_stylename, font_familyname
from gftools.axisreg import axis_registry


ELIDABLE_AXIS_VALUE_NAME = 0x2


# TODO we may have more of these. Please note that some applications may not
# implement variable font style linking.
LINKED_VALUES = {
    "wght": (400, 700),
    "ital": (0.0, 1.0),
}


def _gen_stat_from_fvar(ttfont, axis_reg=axis_registry):
    """Generate a STAT table using a ttfont's fvar and the GF axis registry.

    Args:
        axis_reg: gf axis registry
        ttfont: TTFont instance
    """
    fvar = ttfont["fvar"]

    axis_defaults = {a.axisTag: a.defaultValue for a in fvar.axes}
    results = {}
    for axis in fvar.axes:
        axis_tag = axis.axisTag
        if axis_tag not in axis_reg:
            log.warning(
                f"'{axis_tag}' isn't in our axis registry. Please open an issue "
                "to discuss the inclusion of this axis, "
                "https://github.com/google/ttfonts/issues"
            )
            continue
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


def _axes_in_family_stylenames(ttfonts):
    results = set()
    for ttfont in ttfonts:
        ttfont_style = font_stylename(ttfont)
        results |= set(stylename_to_axes(ttfont_style))
    return results


def stylename_to_axes(font_style, axisreg=axis_registry):
    """Get axis names for stylename particles using the axis registry e.g

    "Condensed Bold Italic" --> ["wdth", "wght", "ital"]

    Args:
        axisreg: gf axis registry
        font_style: str

    Returns: list(str,...)
    """
    axes = []
    seen = set()

    style_tokens = font_style.split()
    for token in style_tokens:
        for axis_tag, axis_object in axisreg.items():
            if token in [f.name for f in axis_object.fallback]:
                seen.add(token)
                axes.append(axis_tag)

    unparsed_tokens = set(style_tokens) - seen
    if unparsed_tokens:
        log.warning(
            "Following style tokens were not found in Axis Registry "
            "{list(unparsed_tokens)}. Axis Values will not be created "
            "for these tokens"
        )
    return axes


def _append_non_fvar_axes_to_stat(
    ttfont, stat_table, family_style_axes, axis_reg=axis_registry
):
    ttfont_style = font_stylename(ttfont)
    ttfont_style_axes = stylename_to_axes(ttfont_style)
    # {"wght": "Regular", "ital": "Roman", ...}
    ttfont_style_tokens = {
        k: v for k, v in zip(ttfont_style_axes, ttfont_style.split())
    }

    # Add axes to ttfont which exist across the family but are not in the ttfont's fvar
    axes_missing = family_style_axes - set(stat_table)
    for axis in axes_missing:
        axis_record = {
            "tag": axis,
            "name": axis_reg[axis].display_name,
            "values": [],
        }
        # Add axis value for axis which isn't in the fvar or ttfont stylename
        if axis not in ttfont_style_tokens:
            axis_record["values"].append(_default_axis_value(axis, axis_reg))
        # Add axis value for axis which isn't in the fvar but does exist in
        # the ttfont stylename
        else:
            style_name = ttfont_style_tokens[axis]
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
        for axis in stat_tbl:
            if axis not in seen_axis_values:
                seen_axis_values[axis] = set()
            seen_axis_values[axis] |= set(i["value"] for i in stat_tbl[axis]["values"])
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
    """Overwrite which axis values should be elided.

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


def _default_axis_value(axis, axisreg=axis_registry):
    axis_record = axisreg[axis]
    default_value = axis_record.default_value
    default_name = next(
        (i.name for i in axis_record.fallback if i.value == default_value), None
    )
    return _add_axis_value(default_name, default_value, flags=ELIDABLE_AXIS_VALUE_NAME)


def _validate_axis_order(axis_order, seen_axes):
    axes_not_ordered = seen_axes - set(axis_order)
    if axes_not_ordered:
        raise ValueError(f"Axis order arg is missing {axes_not_ordered} axes.")


def gen_stat_tables(
    ttfonts, axis_order, elided_axis_values=None, axis_reg=axis_registry
):
    """
    Generate a stat table for each font in a family using the Google Fonts
    Axis Registry.

    Args:
        fonts: [TTFont]
        axis_reg: dict
    """
    # Heuristic:
    # - Gen a STAT table for each font based on each font's fvar table
    # - Find which axes exist in each font's nametable (not fvar!)
    # - Append axis records to each stat table which are not part of each
    #   font's fvar but exist across the family. This step allows us to
    #   establish the relationship between fonts in a family.
    # - Update Axis Values which should be linked in each stat table
    # - Update Axis Values which should be elided based on the user arg
    #   elided_axis_values (optional)
    # - Sort axes in each stat table based on the arg axis_order
    # - Use fontTools to build each stat table for each font
    stat_tables = [_gen_stat_from_fvar(f) for f in ttfonts]
    family_style_axes = _axes_in_family_stylenames(ttfonts)
    stat_tables = [
        _append_non_fvar_axes_to_stat(f, s, family_style_axes)
        for f, s in zip(ttfonts, stat_tables)
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
    _validate_axis_order(axis_order, set(seen_axis_values.keys()))
    assert len(stat_tables) == len(ttfonts)
    axis_order = [a for a in axis_order if a in seen_axis_values.keys()]
    for stat_table, ttfont in zip(stat_tables, ttfonts):
        stat_table = [stat_table[axis] for axis in axis_order]
        _update_fvar_nametable_records(ttfont, stat_table)
        buildStatTable(ttfont, stat_table)


def _update_fvar_nametable_records(ttfont, stat_table):
    nametable = ttfont["name"]
    fvar = ttfont["fvar"]
    family_name = font_familyname(ttfont)
    axes_with_one_entry = [a['values'][0] for a in stat_table if len(a['values']) == 1]
    tokens = [v["name"] for v in axes_with_one_entry]
    ps_tokens = "".join(t for t in tokens)

    # Variations PostScript Name Prefix
    ps_prefix = f"{family_name}{ps_tokens}".replace(" ", "")
    for rec in [(25, 1, 0, 0), (25, 3, 1, 0x409)]:
        nametable.setName(ps_prefix, *rec)

    # Add or update fvar instance postscript names
    for instance in fvar.instances:
        subfamily_id = instance.subfamilyNameID
        name = nametable.getName(subfamily_id, 3, 1, 0x409).toUnicode()
        for token in tokens:
            name = name.replace(token, "")
            if name == "":
                name = "Regular"
        ps_name = f"{ps_prefix}-{name}".replace(" ", "")
        # Remove ps name records if they already exist
        if instance.postscriptNameID != 65535:
            nametable.removeNames(nameID=instance.postscriptNameID)
        instance.postscriptNameID = nametable.addName(ps_name)

