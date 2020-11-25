import pytest
import os
from glob import glob
from gftools.stat import *
from fontTools.ttLib import TTFont


TEST_DATA = os.path.join("data", "test")


@pytest.fixture
def static_font():
    return TTFont(os.path.join(TEST_DATA, "Lora-Regular.ttf"))


@pytest.fixture
def var_font():
    return TTFont(os.path.join(TEST_DATA, "Inconsolata[wdth,wght].ttf"))


@pytest.fixture
def var_fonts():
    paths = [
        os.path.join(TEST_DATA, "Raleway[wght].ttf"),
        os.path.join(TEST_DATA, "Raleway-Italic[wght].ttf")
    ]
    return [TTFont(p) for p in paths]


@pytest.fixture
def var_fonts2():
    paths = [
        os.path.join(TEST_DATA, "cabin_split", "Cabin[wght].ttf"),
        os.path.join(TEST_DATA, "cabin_split", "Cabin-Italic[wght].ttf"),
        os.path.join(TEST_DATA, "cabin_split", "CabinCondensed[wght].ttf"),
        os.path.join(TEST_DATA, "cabin_split", "CabinCondensed-Italic[wght].ttf")
    ]
    return [TTFont(p) for p in paths]


@pytest.fixture
def var_fonts3():
    paths = [
        os.path.join(TEST_DATA, "cabin_multi", "Cabin[wdth,wght].ttf"),
        os.path.join(TEST_DATA, "cabin_multi", "Cabin-Italic[wdth,wght].ttf")
    ]
    return [TTFont(p) for p in paths]


@pytest.fixture
def static_fonts():
    return [TTFont(f) for f in glob(os.path.join("data", "test", "mavenpro", "*.ttf"))]


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
    weight = 200
    for axis_value in wght_axis_values:
        assert axis_value.Value == weight
        weight += 100

    # Check wdth axis values
    wdth_axis_values = [v for v in axis_values if axes[v.AxisIndex] == "wdth"]
    # Inconsolata has a min fvar wdth of 50 and a max of 200.
    expected_wdths = [50, 62.5, 75, 87.5, 100, 112.5, 125, 150, 200]
    for axis_value, width in zip(wdth_axis_values, expected_wdths):
        assert axis_value.Value == width

        
def test_gen_stat_linked_values(var_font):
    del var_font["STAT"]
    gen_stat_tables([var_font], axis_order=["wdth", "wght"])
    stat = var_font["STAT"].table

    reg_axis_value = next(
        (a for a in stat.AxisValueArray.AxisValue if a.Value == 400),
        None
    )
    assert reg_axis_value.LinkedValue == 700


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
    with pytest.raises(ValueError, match="fvar axes are not consistent across the family"):
        gen_stat_tables([roman, italic], axis_order=["wdth", "wght", "ital"])


