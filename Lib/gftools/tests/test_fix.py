from fontTools.ttLib import newTable, TTFont
from gftools.fix import *
import pytest
import os

@pytest.fixture
def static_font():
    f = TTFont(os.path.join("data", "test", "Lora-Regular.ttf"))
    return f


def test_remove_tables(static_font):
    # Test removing a table which is part of UNWANTED_TABLES
    tsi1_tbl = newTable("TSI1")
    static_font["TSI1"] = tsi1_tbl
    assert "TSI1" in static_font

    tsi2_tbl = newTable("TSI2")
    static_font["TSI2"] = tsi2_tbl
    remove_tables(static_font, ["TSI1", "TSI2"])
    assert "TSI1" not in static_font
    assert "TSI2" not in static_font

    # Test removing a table which is essential
    remove_tables(static_font, ["glyf"])
    assert "glyf" in static_font


def test_add_dummy_dsig(static_font):
    assert "DSIG" not in static_font
    add_dummy_dsig(static_font)
    assert "DSIG" in static_font


def test_fix_hinted_font(static_font):
    static_font["head"].flags &= ~(1 << 3)
    assert static_font["head"].flags & (1 << 3) != 8
    fix_hinted_font(static_font)
    assert static_font["head"].flags & (1 << 3) == 8


def test_fix_unhinted_font(static_font):
    for tbl in ("prep", "gasp"):
        if tbl in static_font:
            del static_font[tbl]

    fix_unhinted_font(static_font)
    assert static_font["gasp"].gaspRange == {65535: 15}
    assert "prep" in static_font


def test_fix_fs_type(static_font):
    static_font["OS/2"].fsType = 1
    assert static_font["OS/2"].fsType == 1
    fix_fs_type(static_font)
    assert static_font["OS/2"].fsType == 0


# Taken from https://github.com/googlefonts/gf-docs/tree/master/Spec#supported-styles
STYLE_HEADERS = "style, weight_class, fs_selection, mac_style"
STYLE_TABLE = [
    ("Thin", 100, (1 << 6), (0 << 0)),
    ("ExtraLight", 200, (1 << 6), (0 << 0)),
    ("Light", 300, (1 << 6), (0 << 0)),
    ("Regular", 400, (1 << 6), (0 << 0)),
    ("Medium", 500, (1 << 6), (0 << 0)),
    ("SemiBold", 600, (1 << 6), (0 << 0)),
    ("Bold", 700, (1 << 5), (1 << 0)),
    ("ExtraBold", 800, (1 << 6), (0 << 0)),
    ("Black", 900, (1 << 6), (0 << 0)),
    ("Thin Italic", 100, (1 << 0), (1 << 1)),
    ("ExtraLight Italic", 200, (1 << 0), (1 << 1)),
    ("Light Italic", 300, (1 << 0), (1 << 1)),
    ("Italic", 400, (1 << 0), (1 << 1)),
    ("Medium Italic", 500, (1 << 0), (1 << 1)),
    ("SemiBold Italic", 600, (1 << 0), (1 << 1)),
    ("Bold Italic", 700, (1 << 0) | (1 << 5), (1 << 0) | (1 << 1)),
    ("ExtraBold Italic", 800, (1 << 0), (1 << 1)),
    ("Black Italic", 900, (1 << 0), (1 << 1)),
    # Variable fonts may have tokens other than weight and italic in their names
    ("SemiCondensed Bold Italic", 700, (1 << 0) | (1 << 5), (1 << 0) | (1 << 1)),
    ("12pt Italic", 400, (1 << 0), (1 << 1)),
]

@pytest.mark.parametrize(
    STYLE_HEADERS,
    STYLE_TABLE
)
def test_weight_class(static_font, style, weight_class, fs_selection, mac_style):
    name = static_font["name"]
    if style in ("Regular", "Italic", "Bold", "Bold Italic"):
        name.setName(style, 2, 3, 1, 0x409)
    else:
        if "Italic" in style:
            name.setName("Italic", 2, 3, 1, 0x409)
        else:
            name.setName("Regular", 2, 3, 1, 0x409)
        name.setName(style, 17, 3, 1, 0x409)
    fix_weight_class(static_font)
    assert static_font["OS/2"].usWeightClass == weight_class


@pytest.mark.parametrize(
    STYLE_HEADERS,
    STYLE_TABLE
)
def test_fs_selection(static_font, style, weight_class, fs_selection, mac_style):
    # disable fsSelection bits above 6
    for i in range(7, 12):
        static_font["OS/2"].fsSelection &= ~(1 << i)
    name = static_font["name"]
    name.setName(style, 17, 3, 1, 0x409)
    fix_fs_selection(static_font)
    assert static_font["OS/2"].fsSelection == fs_selection


@pytest.mark.parametrize(
    STYLE_HEADERS,
    STYLE_TABLE
)
def test_fix_mac_style(static_font, style, weight_class, fs_selection, mac_style):
    name = static_font["name"]
    name.setName(style, 17, 3, 1, 0x409)
    fix_mac_style(static_font)
    assert static_font["head"].macStyle == mac_style
