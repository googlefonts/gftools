from gftools.instancer import gen_static_font
from fontTools.ttLib import TTFont
import pytest
import os

TEST_DATA = os.path.join("data", "test")


@pytest.fixture
def var_font():
    """VF family consisting of a single font with two axes, wdth, wght"""
    return TTFont(os.path.join(TEST_DATA, "Inconsolata[wdth,wght].ttf"))


def _name_record(ttFont, nameID):
    nametable = ttFont["name"]
    record = nametable.getName(nameID, 3, 1, 0x409)
    if record:
        return record.toUnicode()
    return None


def test_gen_static_font(var_font):
    static_font = gen_static_font(var_font, {"wght": 600, "wdth": 75})
    assert _name_record(static_font, 1) == "Inconsolata Condensed SemiBold"
    assert _name_record(static_font, 2) == "Regular"
    assert _name_record(static_font, 16) == "Inconsolata Condensed"
    assert _name_record(static_font, 17) == "SemiBold"

    assert static_font["OS/2"].usWeightClass == 600
    assert static_font["OS/2"].usWidthClass == 5
    assert static_font["OS/2"].fsSelection & (1 << 6)
    assert static_font["head"].macStyle == 0


def test_gen_static_font_custom_names(var_font):
    static_font = gen_static_font(var_font, {"wght": 900}, "Custom Family", "Black")
    assert _name_record(static_font, 1) == "Custom Family Black"
    assert _name_record(static_font, 2) == "Regular"
    assert _name_record(static_font, 16) == "Custom Family"
    assert _name_record(static_font, 17) == "Black"


def test_gen_static_font_custom_names_without_declaring_wght(var_font):
    static_font = gen_static_font(
        var_font, {"wght": 900}, "Custom Family", "8pt SemiCondensed"
    )
    assert _name_record(static_font, 1) == "Custom Family 8pt SemiCondensed"
    assert _name_record(static_font, 2) == "Regular"
    assert _name_record(static_font, 16) == None
    assert _name_record(static_font, 17) == None


def test_gen_static_font_custom_names_ribbi(var_font):
    static_font = gen_static_font(
        var_font, {"wght": 900}, "Custom Family", "8pt SemiCondensed Bold Italic"
    )
    assert _name_record(static_font, 1) == "Custom Family 8pt SemiCondensed"
    assert _name_record(static_font, 2) == "Bold Italic"
    assert _name_record(static_font, 16) == None
    assert _name_record(static_font, 17) == None


def test_gen_static_font_custom_names_non_ribbi(var_font):
    static_font = gen_static_font(
        var_font, {"wght": 900}, "Custom Family", "8pt SemiCondensed Medium"
    )
    assert _name_record(static_font, 1) == "Custom Family 8pt SemiCondensed Medium"
    assert _name_record(static_font, 2) == "Regular"
    assert _name_record(static_font, 16) == "Custom Family 8pt SemiCondensed"
    assert _name_record(static_font, 17) == "Medium"
