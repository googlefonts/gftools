"""
Fontmake can only generate a single variable font. It cannot generate a
family of variable fonts, that are related to one another.

This script will update the nametables and STAT tables so a family
which has more than one variable font will work correctly in desktop
applications.

It will also work on single font VF families by creating a better STAT
table.

TODO make script work on VFs which have multiple axises. We'll need to
change the axis array format to v4 (we're using v1),
https://docs.microsoft.com/en-us/typography/opentype/spec/stat#axis-value-table-format-4

Atm, the script will work well for single axis fonts and families which
have a single vf for Roman and another for Italic/Condensed, both using the wght
axis (covers 95% of GF cases).
"""
from argparse import ArgumentParser
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables


def fonts_are_same_family(ttfonts):
    """Check fonts have the same preferred family name or family name"""
    family_names = []
    for ttfont in ttfonts:
        pref_family_name = ttfont['name'].getName(16, 3, 1, 1033)
        family_name = ttfont['name'].getName(1, 3, 1, 1033)
        name = pref_family_name if pref_family_name else family_name
        family_names.append(name.toUnicode())
    if len(set(family_names)) != 1:
        return False
    return True


def fix_nametable(ttfont):
    """Cleanup nametable issues caused by fontmake"""
    table = ttfont['name']
    family_name = table.getName(1, 3, 1, 1033).toUnicode()

    # Remove style from family name. Often happens for Italic fonts
    # Family Name Light --> Family Name
    for style in (' Regular', ' Light', ' Bold'):
        if style in family_name:
            table.setName(family_name.replace(style, ''), 1, 3, 1, 1033)
    # Remove preferred family name and prefered style
    idx = 0
    while idx < len(table.names) - 1:
        if table.names[idx].nameID in [16, 17]:
            table.names.pop(idx)
            idx = 0
        else:
            idx += 1

    # Update existing nameids based on the varfont's default style
    default_style = _get_vf_default_style(ttfont)
    family_name = table.getName(1, 3, 1, 1033).toUnicode()
    table.setName(default_style, 2, 3, 1, 1033)

    fullname = '{} {}'.format(family_name, default_style)
    table.setName(unicode(fullname), 4, 3, 1, 1033)

    psname = '{}-{}'.format(family_name, default_style.replace(' ', ''))
    table.setName(unicode(psname), 6, 3, 1, 1033)

    # uniqueid basedon fontmake output version;vendorid;psname
    font_version = format(ttfont['head'].fontRevision, '.3f')
    vendor = ttfont['OS/2'].achVendID
    uniqueid = '{};{};{}'.format(font_version, vendor, psname)
    table.setName(unicode(uniqueid), 3, 3, 1, 1033)


def create_stat_table(ttfont):
    """Atm, Fontmake is only able to produce a basic stat table. Because of
    this, we'll create a STAT using the font's fvar table."""
    stat = newTable('STAT')
    stat.table = otTables.STAT()
    stat.table.Version = 0x00010002

    # # Build DesignAxisRecords from fvar
    stat.table.DesignAxisRecord = otTables.AxisRecordArray()
    stat.table.DesignAxisRecord.Axis = []

    stat_axises = stat.table.DesignAxisRecord.Axis

    # TODO (M Foley) add support for fonts which have multiple
    # axises e.g Barlow
    if len(ttfont['fvar'].axes) > 1:
        raise Exception('VFs with more than one axis are currently '
                        'not supported.')

    for idx, axis in enumerate(ttfont['fvar'].axes):
        append_stat_axis(stat, axis.axisTag, axis.axisNameID)

    # Build AxisValueArrays for each namedInstance from fvar namedInstances
    stat.table.AxisValueArray = otTables.AxisValueArray()
    stat.table.AxisValueArray.AxisValue = []

    for idx, instance in enumerate(ttfont['fvar'].instances):
        append_stat_record(stat, 0, instance.coordinates.values()[0], instance.subfamilyNameID)

    # Set ElidedFallbackNameID
    stat.table.ElidedFallbackNameID = 2
    ttfont['STAT'] = stat


def _get_vf_types(ttfonts):
    styles = []
    for ttfont in ttfonts:
        styles.append(_get_vf_type(ttfont))
    return styles


def _get_vf_type(ttfont):
    style = ttfont['name'].getName(2, 3, 1, 1033).toUnicode()
    return 'Italic' if 'Italic' in style else 'Roman'


def _get_vf_default_style(ttfont):
    """Return the name record string of the default style"""
    default_fvar_val = ttfont['fvar'].axes[0].defaultValue

    name_id = None
    for inst in ttfont['fvar'].instances:
        if inst.coordinates['wght'] == default_fvar_val:
            name_id = inst.subfamilyNameID
    return ttfont['name'].getName(name_id, 1, 0, 0).toUnicode()


def add_other_vf_styles_to_nametable(ttfont, text_records):
    """Each nametable in a font must reference every font in the family.
    Since fontmake doesn't append the other families to the nametable,
    we'll do this ourselves. Skip this step if these records already
    exist."""
    found = set()
    for name in ttfont['name'].names[:-len(text_records)-1:-1]:
        found.add(name.toUnicode())
    leftover = set(text_records) - found

    if leftover:
        nameid = ttfont['name'].names[-1].nameID + 1
        for record in leftover:
            ttfont['name'].setName(unicode(record), nameid, 3, 1, 1033)
            nameid += 1


def get_custom_name_record(ttfont, text):
    """Return a name record by text. Record ID must be greater than 255"""
    for record in ttfont['name'].names[::-1]:
        if record.nameID > 255:
            rec_text = record.toUnicode()
            if rec_text == text:
                return record
    return None


def append_stat_axis(stat, tag, namerecord_id):
    """Add a STAT axis if the tag does not exist already."""
    has_tags = []
    axises = stat.table.DesignAxisRecord.Axis
    for axis in axises:
        has_tags.append(axis.AxisTag)

    if tag in has_tags:
        raise Exception('{} has already been declared in the STAT table')

    axis_record = otTables.AxisRecord()
    axis_record.AxisTag = tag
    axis_record.AxisNameID = namerecord_id
    axis_record.AxisOrdering = len(axises)
    axises.append(axis_record)


def append_stat_record(stat, axis_index, value, namerecord_id, linked_value=None):
    records = stat.table.AxisValueArray.AxisValue
    axis_record = otTables.AxisValue()
    axis_record.Format = 1
    axis_record.ValueNameID = namerecord_id
    axis_record.Value = value
    axis_record.AxisIndex = axis_index

    axis_record.Flags = 0
    if linked_value:
        axis_record.Format = 3
        axis_record.LinkedValue = linked_value
    records.append(axis_record)


def get_stat_axis_index(ttfont, axis_name):
    axises = ttfont['STAT'].table.DesignAxisRecord.Axis
    available_axises = [a.AxisTag for a in axises]
    for idx, axis in enumerate(axises):
        if axis.AxisTag == axis_name:
            return idx
    raise Exception('{} is not a valid axis. Font has [{}] axises'.format(
        axis_name, available_axises)
    )


def set_stat_for_font_in_family(ttfont, family_styles):
    """Based on examples from:
    https://docs.microsoft.com/en-us/typography/opentype/spec/stat"""
    font_type = _get_vf_type(ttfont)
    # See example 5
    if font_type == 'Roman' and 'Italic' in family_styles:
        name_record = get_custom_name_record(ttfont, 'Italic')
        append_stat_axis(ttfont['STAT'], 'ital', name_record.nameID)

        name_record = get_custom_name_record(ttfont, 'Roman')
        axis_idx = get_stat_axis_index(ttfont, 'ital')
        append_stat_record(ttfont['STAT'], axis_idx, 0, name_record.nameID, linked_value=1.0)

    elif font_type == 'Italic' and 'Roman' in family_styles:
        name_record = get_custom_name_record(ttfont, 'Italic')
        append_stat_axis(ttfont['STAT'], 'ital', name_record.nameID)

        name_record = get_custom_name_record(ttfont, 'Italic')
        axis_idx = get_stat_axis_index(ttfont, 'ital')
        append_stat_record(ttfont['STAT'], axis_idx, 1.0, name_record.nameID)


def harmonize_vf_families(ttfonts):
    """Make sure the fonts which are part of a vf family reference each other
    in both the nametable and STAT table. For examples see:
    https://docs.microsoft.com/en-us/typography/opentype/spec/stat

    """
    family_styles = _get_vf_types(ttfonts)
    for ttfont in ttfonts:
        add_other_vf_styles_to_nametable(ttfont, family_styles)
        set_stat_for_font_in_family(ttfont, family_styles)


def main():
    parser = ArgumentParser()
    parser.add_argument('fonts', nargs='+',
                        help='All fonts within a font family must be included')
    args = parser.parse_args()
    font_paths = args.fonts
    ttfonts = [TTFont(p) for p in font_paths]
    if not fonts_are_same_family(ttfonts):
        raise Exception('Fonts have different family_names: [{}]'.format(
            ', '.join(map(os.path.basename, ttfonts))
        ))

    map(fix_nametable, ttfonts)
    map(create_stat_table, ttfonts)
    harmonize_vf_families(ttfonts)

    for path, ttfont in zip(font_paths, ttfonts):
        ttfont.save(path + '.fix')

if __name__ == '__main__':
    main()
