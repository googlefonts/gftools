import pytest
import os
from glob import glob
from gftools.stat import *
from fontTools.ttLib import TTFont
import yaml


TEST_DATA = os.path.join("data", "test")


@pytest.fixture
def var_font():
    """VF family consisting of a single font with two axes, wdth, wght"""
    return TTFont(os.path.join(TEST_DATA, "Inconsolata[wdth,wght].ttf"))


@pytest.fixture
def var_fonts():
    """VF family consisting of two fonts, Roman, and Italic. Both have a
    weight axis"""
    paths = [
        os.path.join(TEST_DATA, "Raleway[wght].ttf"),
        os.path.join(TEST_DATA, "Raleway-Italic[wght].ttf")
    ]
    return [TTFont(p) for p in paths]


@pytest.fixture
def var_fonts2():
    """VF family consisting of four fonts, Roman, Italic, Condensed Roman,
    Condensed Italic. All only have a wght axis"""
    paths = [
        os.path.join(TEST_DATA, "cabin_split", "Cabin[wght].ttf"),
        os.path.join(TEST_DATA, "cabin_split", "Cabin-Italic[wght].ttf"),
        os.path.join(TEST_DATA, "cabin_split", "CabinCondensed[wght].ttf"),
        os.path.join(TEST_DATA, "cabin_split", "CabinCondensed-Italic[wght].ttf")
    ]
    return [TTFont(p) for p in paths]


@pytest.fixture
def var_fonts3():
    """VF family consisting of two fonts, Roman and Italic. Both have wdth and wght
    axies."""
    paths = [
        os.path.join(TEST_DATA, "cabin_multi", "Cabin[wdth,wght].ttf"),
        os.path.join(TEST_DATA, "cabin_multi", "Cabin-Italic[wdth,wght].ttf")
    ]
    return [TTFont(p) for p in paths]


def _get_axis_value(font, axis, name, value):
    nametable = font["name"]
    stat = font["STAT"].table
    axis_indexes = {i: a.AxisTag for i,a in enumerate(stat.DesignAxisRecord.Axis)}
    axis_values = stat.AxisValueArray.AxisValue 
    for axis_value in axis_values:
        axis_tag = axis_indexes[axis_value.AxisIndex]
        if axis_tag != axis:
            continue
        nameID = axis_value.ValueNameID
        name_string = nametable.getName(nameID, 3, 1, 0x409).toUnicode()
        if name_string != name:
            continue
        if axis_value.Value != value:
            continue
        return axis_value
    return None


def test_gen_stat(var_font):
    del var_font["STAT"]
    gen_stat_tables([var_font], axis_order=["wdth", "wght"])
    stat = var_font["STAT"].table
    axes = {i: a.AxisTag for i,a in enumerate(stat.DesignAxisRecord.Axis)}

    axis_values = var_font['STAT'].table.AxisValueArray.AxisValue 
    # Check both wght and wdth axes exist
    axes_in_axis_values = set(axes[a.AxisIndex] for a in axis_values)
    assert axes_in_axis_values == {"wght", "wdth"}

    # Check wght axis values
    wght_axis_values = [v for v in axis_values if axes[v.AxisIndex] == "wght"]
    # Inconsolata has a min fvar wght of 200 and a max of 900.
    for axis_value, desired_weight in zip(wght_axis_values, range(200, 1000, 100)):
        assert axis_value.Value == desired_weight

    # Check wdth axis values
    wdth_axis_values = [v for v in axis_values if axes[v.AxisIndex] == "wdth"]
    # Inconsolata has a min fvar wdth of 50 and a max of 200.
    expected_wdths = [50, 62.5, 75, 87.5, 100, 112.5, 125, 150, 200]
    for axis_value, width in zip(wdth_axis_values, expected_wdths):
        assert axis_value.Value == width

    # Check Regular is linked to Bold
    reg_axis_value = _get_axis_value(var_font, "wght", "Regular", 400)
    assert reg_axis_value.LinkedValue == 700

    # Check Regular is elided
    assert reg_axis_value.Flags & ELIDABLE_AXIS_VALUE_NAME == ELIDABLE_AXIS_VALUE_NAME

    # Check Normal width is elided
    normal_axis_value = _get_axis_value(var_font, "wdth", "Normal", 100)
    assert normal_axis_value.Flags & ELIDABLE_AXIS_VALUE_NAME == ELIDABLE_AXIS_VALUE_NAME


def test_gen_stat_linked_values(var_font):
    del var_font["STAT"]
    gen_stat_tables([var_font], axis_order=["wdth", "wght"])
    stat = var_font["STAT"].table

    reg_axis_value = _get_axis_value(var_font, "wght", "Regular", 400)
    assert reg_axis_value.LinkedValue == 700


def test_gen_stat_linked_values_2(var_fonts2):
    gen_stat_tables(var_fonts2, axis_order=["wdth", "wght", "ital"])
    for font in var_fonts2:
        stat = font["STAT"].table
        reg_axis_value = _get_axis_value(font, "wght", "Regular", 400)
        assert reg_axis_value.LinkedValue == 700


def test_gen_stat_dflt_elided_values(var_fonts3):
    gen_stat_tables(var_fonts3, axis_order=["wdth", "wght", "ital"])
    for font in var_fonts3:
        stat = font["STAT"].table
        # Check regular axis value is elided
        reg_axis_value = _get_axis_value(font, "wght", "Regular", 400)
        assert reg_axis_value.Flags & ELIDABLE_AXIS_VALUE_NAME == ELIDABLE_AXIS_VALUE_NAME

        # Check normal (wdth) axis value is elided
        normal_axis_value = _get_axis_value(font, "wdth", "Normal", 100)
        assert normal_axis_value.Flags & ELIDABLE_AXIS_VALUE_NAME == ELIDABLE_AXIS_VALUE_NAME


def test_gen_stat_user_elided_values(var_fonts3):
    gen_stat_tables(
        var_fonts3,
        axis_order=["wdth", "wght", "ital"],
        elided_axis_values={"wght": [700], "wdth": [75]}
    )

    for font in var_fonts3:
        stat = font["STAT"].table
        # First check that the dflt axis values are not elided!
        reg_axis_value = _get_axis_value(font, "wght", "Regular", 400)
        assert reg_axis_value.Flags & ELIDABLE_AXIS_VALUE_NAME != ELIDABLE_AXIS_VALUE_NAME

        normal_axis_value = _get_axis_value(font, "wdth", "Normal", 100)
        assert normal_axis_value.Flags & ELIDABLE_AXIS_VALUE_NAME != ELIDABLE_AXIS_VALUE_NAME

        # now check the user specified elided values are elided
        bold_axis_value = _get_axis_value(font, "wght", "Bold", 700)
        assert bold_axis_value.Flags & ELIDABLE_AXIS_VALUE_NAME == ELIDABLE_AXIS_VALUE_NAME

        condensed_axis_value = _get_axis_value(font, "wdth", "Condensed", 75)
        assert condensed_axis_value.Flags & ELIDABLE_AXIS_VALUE_NAME == ELIDABLE_AXIS_VALUE_NAME


def test_gen_stat_roman_and_italic_family(var_fonts):
    for var_font in var_fonts:
        del var_font["STAT"]
    gen_stat_tables(var_fonts, axis_order=["wght", "ital"])
    roman, italic = var_fonts

    roman_axis_val = _get_axis_value(roman, "ital", "Roman", 0.0)
    assert roman_axis_val != None
    assert roman_axis_val.LinkedValue == 1.0

    italic_axis_val = _get_axis_value(italic, "ital", "Italic", 1.0)
    assert italic_axis_val != None


def test_gen_stat_roman_and_italic_and_condensed_family(var_fonts2):
    gen_stat_tables(var_fonts2, axis_order=["wdth", "wght", "ital"])
    roman, italic, condensed_roman, condensed_italic = var_fonts2

    roman_ital_axis_val = _get_axis_value(roman, "ital", "Roman", 0.0)
    roman_wdth_axis_val = _get_axis_value(roman, "wdth", "Normal", 100.0)
    assert roman_ital_axis_val != None
    assert roman_wdth_axis_val != None

    italic_ital_axis_val = _get_axis_value(italic, "ital", "Italic", 1.0)
    italic_wdth_axis_val = _get_axis_value(italic, "wdth", "Normal", 100.0)
    assert italic_ital_axis_val != None
    assert italic_wdth_axis_val != None

    condensed_ital_axis_val = _get_axis_value(condensed_roman, "ital", "Roman", 0.0)
    condensed_wdth_axis_val = _get_axis_value(condensed_roman, "wdth", "Condensed", 75.0)
    assert condensed_ital_axis_val != None
    assert condensed_wdth_axis_val != None

    condensed_italic_ital_axis_val = _get_axis_value(condensed_italic, "ital", "Italic", 1.0)
    condensed_italic_wdth_axis_val = _get_axis_value(condensed_italic, "wdth", "Condensed", 75.0)
    assert condensed_italic_ital_axis_val != None
    assert condensed_italic_wdth_axis_val != None


def test_gen_stat_family_with_uneven_axes(var_fonts3):
    from fontTools.varLib.instancer import instantiateVariableFont
    roman, italic = var_fonts3
    # Drop the width axis from the roman font
    roman = instantiateVariableFont(roman, {"wdth": None})
    # We cannot add STAT tables to these families since the Google Fonts API
    # doesn't support them
    with pytest.raises(ValueError, match="fvar axes are not consistent across the family"):
        gen_stat_tables([roman, italic], axis_order=["wdth", "wght", "ital"])


def _check_ps_instance_names(ttfont, desired_names):
    nametable = ttfont['name']
    instances = ttfont['fvar'].instances
    for instance, desired_name in zip(instances, desired_names):
        ps_id = instance.postscriptNameID
        name = nametable.getName(ps_id, 3, 1, 0x409).toUnicode()
        assert name == desired_name


def test_gen_stat_update_fvar_instances_1(var_fonts):
    gen_stat_tables(var_fonts, axis_order=["wght", "ital"])
    roman, italic = var_fonts

    desired_roman_ps_names = [
        "RalewayRoman-Thin",
        "RalewayRoman-ExtraLight",
        "RalewayRoman-Light",
        "RalewayRoman-Regular",
        "RalewayRoman-Medium",
        "RalewayRoman-SemiBold",
        "RalewayRoman-Bold",
        "RalewayRoman-ExtraBold",
        "RalewayRoman-Black",
    ]
    _check_ps_instance_names(roman, desired_roman_ps_names)

    desired_italic_ps_names = [
        "RalewayItalic-Thin",
        "RalewayItalic-ExtraLight",
        "RalewayItalic-Light",
        "RalewayItalic-Regular",
        "RalewayItalic-Medium",
        "RalewayItalic-SemiBold",
        "RalewayItalic-Bold",
        "RalewayItalic-ExtraBold",
        "RalewayItalic-Black",
    ]
    _check_ps_instance_names(italic, desired_italic_ps_names)


def test_gen_stat_update_fvar_instances_2(var_fonts2):
    gen_stat_tables(var_fonts2, axis_order=["wdth", "wght", "ital"])
    roman, italic, condensed_roman, condensed_italic = var_fonts2

    desired_roman_ps_names = [
        "CabinNormalRoman-Regular",
        "CabinNormalRoman-Medium",
        "CabinNormalRoman-SemiBold",
        "CabinNormalRoman-Bold",
    ]
    _check_ps_instance_names(roman, desired_roman_ps_names)

    desired_italic_ps_names = [
        "CabinNormalItalic-Regular",
        "CabinNormalItalic-Medium",
        "CabinNormalItalic-SemiBold",
        "CabinNormalItalic-Bold",
    ]
    _check_ps_instance_names(italic, desired_italic_ps_names)

    desired_condensed_roman_ps_names = [
        "CabinCondensedRoman-Regular",
        "CabinCondensedRoman-Medium",
        "CabinCondensedRoman-SemiBold",
        "CabinCondensedRoman-Bold",
    ]
    _check_ps_instance_names(condensed_roman, desired_condensed_roman_ps_names)

    desired_condensed_italic_ps_names = [
        "CabinCondensedItalic-Regular",
        "CabinCondensedItalic-Medium",
        "CabinCondensedItalic-SemiBold",
        "CabinCondensedItalic-Bold",
    ]
    _check_ps_instance_names(condensed_italic, desired_condensed_italic_ps_names)


def test_gen_stat_update_fvar_instances_3(var_fonts3):
    gen_stat_tables(var_fonts3, axis_order=["wdth", "wght", "ital"])
    roman, italic = var_fonts3

    desired_roman_ps_names = [
        "CabinRoman-Regular",
        "CabinRoman-Medium",
        "CabinRoman-SemiBold",
        "CabinRoman-Bold",
    ]
    _check_ps_instance_names(roman, desired_roman_ps_names)

    desired_italic_ps_names = [
        "CabinItalic-Regular",
        "CabinItalic-Medium",
        "CabinItalic-SemiBold",
        "CabinItalic-Bold",
    ]
    _check_ps_instance_names(italic, desired_italic_ps_names)


def test_gen_stat_nameid_25_vf_postscript_name_1(var_font):
    gen_stat_tables([var_font], axis_order=['wdth', 'wght'])
    assert var_font['name'].getName(25, 3, 1, 0x409).toUnicode() == "Inconsolata"


def test_gen_stat_nameid_25_vf_postscript_name_2(var_fonts):
    gen_stat_tables(var_fonts, axis_order=['wght', 'ital'])
    roman, italic = var_fonts
    assert roman['name'].getName(25, 3, 1, 0x409).toUnicode() == "RalewayRoman"
    assert italic['name'].getName(25, 3, 1, 0x409).toUnicode() == "RalewayItalic"


def test_gen_stat_nameid_25_vf_postscript_name_3(var_fonts2):
    gen_stat_tables(var_fonts2, axis_order=["wdth", "wght", "ital"])
    roman, italic, condensed_roman, condensed_italic = var_fonts2
    assert roman['name'].getName(25, 3, 1, 0x409).toUnicode() == "CabinNormalRoman"
    assert italic['name'].getName(25, 3, 1, 0x409).toUnicode() == "CabinNormalItalic"
    assert condensed_roman['name'].getName(25, 3, 1, 0x409).toUnicode() == "CabinCondensedRoman"
    assert condensed_italic['name'].getName(25, 3, 1, 0x409).toUnicode() == "CabinCondensedItalic"

 
def test_gen_stat_nameid_25_vf_postscript_name_4(var_fonts3):
    gen_stat_tables(var_fonts3, axis_order=["wdth", "wght", "ital"])
    roman, italic = var_fonts3
    assert roman['name'].getName(25, 3, 1, 0x409).toUnicode() == "CabinRoman"
    assert italic['name'].getName(25, 3, 1, 0x409).toUnicode() == "CabinItalic"


def test_gen_stat_tables_from_config(var_fonts):
    config_text = """
      Raleway[wght].ttf:
      - name: Weight
        tag: wght
        values:
        - name: Regular
          value: 400
          flags: 2
        - name: Bold
          value: 700
        - name: SemiBold
          value: 600
      - name: Italic
        tag: ital
        values:
        - name: Roman
          value: 0
          linkedValue: 1
          flags: 2

      Raleway-Italic[wght].ttf:
      - name: Weight
        tag: wght
        values:
        - name: Regular
          value: 400
          flags: 2
        - name: Bold
          value: 700
        - name: SemiBold
          value: 600
      - name: Italic
        tag: ital
        values:
        - name: Italic
          value: 1
    """
    config = yaml.load(config_text)
    gen_stat_tables_from_config(config, var_fonts)
    roman, italic = var_fonts

    roman_axis_val = _get_axis_value(roman, "ital", "Roman", 0.0)
    assert roman_axis_val != None
    assert roman_axis_val.LinkedValue == 1.0

    italic_axis_val = _get_axis_value(italic, "ital", "Italic", 1.0)
    assert italic_axis_val != None

    roman_reg_val = _get_axis_value(roman, "wght", "Regular", 400)
    assert roman_reg_val != None
    assert roman_reg_val.Flags == 0x2

    ital_reg_val = _get_axis_value(italic, "wght", "Regular", 400)
    assert roman_reg_val != None
    assert roman_reg_val.Flags == 0x2

    assert _get_axis_value(roman, "wght", "Light", 300) == None
    assert _get_axis_value(italic, "wght", "Light", 300) == None
