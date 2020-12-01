from fontTools.ttLib import newTable, TTFont
from gftools.fix import *
from glob import glob
import pytest
import os
from copy import deepcopy


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
def static_fonts():
    return [TTFont(f) for f in glob(os.path.join("data", "test", "mavenpro", "*.ttf"))]


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
    assert static_font["head"].flags & (1 << 3) != (1 << 3)
    static_font['fpgm'] = newTable("fpgm")
    fix_hinted_font(static_font)
    assert static_font["head"].flags & (1 << 3) == (1 << 3)


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
    ("Hairline", 1, (1 << 6), (0 << 0)),
    ("Thin", 100, (1 << 6), (0 << 0)),
    ("ExtraLight", 200, (1 << 6), (0 << 0)),
    ("Light", 300, (1 << 6), (0 << 0)),
    ("Regular", 400, (1 << 6), (0 << 0)),
    ("Medium", 500, (1 << 6), (0 << 0)),
    ("SemiBold", 600, (1 << 6), (0 << 0)),
    ("Bold", 700, (1 << 5), (1 << 0)),
    ("ExtraBold", 800, (1 << 6), (0 << 0)),
    ("Black", 900, (1 << 6), (0 << 0)),
    ("ExtraBlack", 1000, (1 << 6), (0 << 0)),
    ("Hairline Italic", 1, (1 << 0), (1 << 1)),
    ("Thin Italic", 100, (1 << 0), (1 << 1)),
    ("ExtraLight Italic", 200, (1 << 0), (1 << 1)),
    ("Light Italic", 300, (1 << 0), (1 << 1)),
    ("Italic", 400, (1 << 0), (1 << 1)),
    ("Medium Italic", 500, (1 << 0), (1 << 1)),
    ("SemiBold Italic", 600, (1 << 0), (1 << 1)),
    ("Bold Italic", 700, (1 << 0) | (1 << 5), (1 << 0) | (1 << 1)),
    ("ExtraBold Italic", 800, (1 << 0), (1 << 1)),
    ("Black Italic", 900, (1 << 0), (1 << 1)),
    ("ExtraBlack Italic", 1000, (1 << 0), (1 << 1)),
    # Variable fonts may have tokens other than weight and italic in their names
    ("SemiCondensed Bold Italic", 700, (1 << 0) | (1 << 5), (1 << 0) | (1 << 1)),
    ("12pt Italic", 400, (1 << 0), (1 << 1)),
]

@pytest.mark.parametrize(
    STYLE_HEADERS,
    STYLE_TABLE
)
def test_fix_weight_class(static_font, style, weight_class, fs_selection, mac_style):
    name = static_font["name"]
    name.setName(style, 2, 3, 1, 0x409)
    name.setName(style, 17, 3, 1, 0x409)
    fix_weight_class(static_font)
    assert static_font["OS/2"].usWeightClass == weight_class


def test_unknown_weight_class(static_font):
    name = static_font["name"]
    name.setName("Foobar", 2, 3, 1, 0x409)
    name.setName("Foobar", 17, 3, 1, 0x409)
    from gftools.fix import WEIGHT_NAMES

    with pytest.raises(ValueError, match="Cannot determine usWeightClass"):
        fix_weight_class(static_font)


@pytest.mark.parametrize(
    STYLE_HEADERS,
    STYLE_TABLE
)
def test_fs_selection(static_font, style, weight_class, fs_selection, mac_style):
    # disable fsSelection bits above 6
    for i in range(7, 12):
        static_font["OS/2"].fsSelection &= ~(1 << i)
    name = static_font["name"]
    name.setName(style, 2, 3, 1, 0x409)
    name.setName(style, 17, 3, 1, 0x409)
    fix_fs_selection(static_font)
    assert static_font["OS/2"].fsSelection == fs_selection


@pytest.mark.parametrize(
    STYLE_HEADERS,
    STYLE_TABLE
)
def test_fix_mac_style(static_font, style, weight_class, fs_selection, mac_style):
    name = static_font["name"]
    name.setName(style, 2, 3, 1, 0x409)
    name.setName(style, 17, 3, 1, 0x409)
    fix_mac_style(static_font)
    assert static_font["head"].macStyle == mac_style


STYLENAME_HEADERS = "family_name, style, id1, id2, id16, id17"
STYLENAME_TABLE = [
    # Roman
    ("Test Family", "Hairline", "Test Family Hairline", "Regular", "Test Family", "Hairline"),
    ("Test Family", "Thin", "Test Family Thin", "Regular", "Test Family", "Thin"),
    ("Test Family", "ExtraLight", "Test Family ExtraLight", "Regular", "Test Family", "ExtraLight"),
    ("Test Family", "Light", "Test Family Light", "Regular", "Test Family", "Light"),
    ("Test Family", "Regular", "Test Family", "Regular", "", ""),
    ("Test Family", "Medium", "Test Family Medium", "Regular", "Test Family", "Medium"),
    ("Test Family", "SemiBold", "Test Family SemiBold", "Regular", "Test Family", "SemiBold"),
    ("Test Family", "Bold", "Test Family", "Bold", "", ""),
    ("Test Family", "ExtraBold", "Test Family ExtraBold", "Regular", "Test Family", "ExtraBold"),
    ("Test Family", "Black", "Test Family Black", "Regular", "Test Family", "Black"),
    ("Test Family", "ExtraBlack", "Test Family ExtraBlack", "Regular", "Test Family", "ExtraBlack"),
    # Italics
    ("Test Family", "Hairline Italic", "Test Family Hairline", "Italic", "Test Family", "Hairline Italic"),
    ("Test Family", "Thin Italic", "Test Family Thin", "Italic", "Test Family", "Thin Italic"),
    ("Test Family", "ExtraLight Italic", "Test Family ExtraLight", "Italic", "Test Family", "ExtraLight Italic"),
    ("Test Family", "Light Italic", "Test Family Light", "Italic", "Test Family", "Light Italic"),
    ("Test Family", "Italic", "Test Family", "Italic", "", ""),
    ("Test Family", "Medium Italic", "Test Family Medium", "Italic", "Test Family", "Medium Italic"),
    ("Test Family", "SemiBold Italic", "Test Family SemiBold", "Italic", "Test Family", "SemiBold Italic"),
    ("Test Family", "Bold Italic", "Test Family", "Bold Italic", "", ""),
    ("Test Family", "ExtraBold Italic", "Test Family ExtraBold", "Italic", "Test Family", "ExtraBold Italic"),
    ("Test Family", "Black Italic", "Test Family Black", "Italic", "Test Family", "Black Italic"),
    ("Test Family", "ExtraBlack Italic", "Test Family ExtraBlack", "Italic", "Test Family", "ExtraBlack Italic"),
]
@pytest.mark.parametrize(
    STYLENAME_HEADERS,
    STYLENAME_TABLE
)
def test_update_nametable(static_font, family_name, style, id1, id2, id16, id17):
    update_nametable(static_font, family_name, style)
    nametable = static_font["name"]
    assert nametable.getName(1, 3, 1, 0x409).toUnicode() == id1
    assert nametable.getName(2, 3, 1, 0x409).toUnicode() == id2
    if id16 and id17:
        assert nametable.getName(16, 3, 1, 0x409).toUnicode() == id16
        assert nametable.getName(17, 3, 1, 0x409).toUnicode() == id17
    else:
        assert nametable.getName(16, 3, 1, 0x409) == None
        assert nametable.getName(17, 3, 1, 0x409) == None


# TODO test fix_nametable once https://github.com/fonttools/fonttools/pull/2078 is merged


def _get_fvar_instance_names(var_font):
    inst_names = []
    for inst in var_font['fvar'].instances:
        inst_name = var_font['name'].getName(inst.subfamilyNameID, 3, 1, 0x409)
        inst_names.append(inst_name.toUnicode())
    return inst_names


def test_fix_fvar_instances(var_font):
    roman_instances = [
        "ExtraLight",
        "Light",
        "Regular",
        "Medium",
        "SemiBold",
        "Bold",
        "ExtraBold",
        "Black"
    ]
    italic_instances = [
        "ExtraLight Italic",
        "Light Italic",
        "Italic",
        "Medium Italic",
        "SemiBold Italic",
        "Bold Italic",
        "ExtraBold Italic",
        "Black Italic",
    ]
    var_font["fvar"].instances = []

    fix_fvar_instances(var_font)
    inst_names = _get_fvar_instance_names(var_font)
    assert inst_names == roman_instances


    # Let's rename the font style so the font becomes an Italic variant
    var_font2 = deepcopy(var_font)
    var_font2["name"].setName("Italic", 2, 3, 1, 0x409)
    var_font2["name"].setName("Italic", 17, 3, 1, 0x409)

    fix_fvar_instances(var_font2)
    inst_names = _get_fvar_instance_names(var_font2)
    assert inst_names == italic_instances


    # Let's mock an ital axis so the font has both ital and wght axes
    new_fvar = deepcopy(var_font["fvar"])
    new_fvar.axes[1].axisTag = "ital"
    new_fvar.axes[1].minValue = 0
    new_fvar.axes[1].maxValue = 1
    new_fvar.axes[1].defaultValue = 0

    var_font3 = deepcopy(var_font)
    var_font3['fvar'] = new_fvar
    fix_fvar_instances(var_font3)

    inst_names = _get_fvar_instance_names(var_font3)
    assert inst_names == roman_instances + italic_instances


def _check_vertical_metrics(fonts):
    ref_font = fonts[0]
    y_min = min(f["head"].yMin for f in fonts)
    y_max = max(f["head"].yMax for f in fonts)
    for font in fonts:
        # Check fsSelection bit 7 (USE_TYPO_METRICS) is enabled
        assert font["OS/2"].fsSelection & (1 << 7) > 0

        # Check metrics are consistent across family
        assert font["OS/2"].usWinAscent == ref_font["OS/2"].usWinAscent
        assert font["OS/2"].usWinDescent == ref_font["OS/2"].usWinDescent
        assert font["OS/2"].sTypoAscender == ref_font["OS/2"].sTypoAscender
        assert font["OS/2"].sTypoDescender == ref_font["OS/2"].sTypoDescender
        assert font["OS/2"].sTypoLineGap == ref_font["OS/2"].sTypoLineGap
        assert font["hhea"].ascent == ref_font["hhea"].ascent
        assert font["hhea"].descent == ref_font["hhea"].descent
        assert font["hhea"].lineGap == ref_font["hhea"].lineGap

        # Check typo and hhea match
        assert font["OS/2"].sTypoAscender == font["hhea"].ascent
        assert font["OS/2"].sTypoDescender == ref_font["hhea"].descent
        assert font["OS/2"].sTypoLineGap == ref_font["hhea"].lineGap

        # Check win matches family_bounds
        assert font["OS/2"].usWinAscent == y_max
        assert font["OS/2"].usWinDescent == abs(y_min)


def test_fix_vertical_metrics_family_consistency(static_fonts):
    _check_vertical_metrics(static_fonts)
    static_fonts[0]["OS/2"].sTypoLineGap = 1000
    static_fonts[0]["OS/2"].usWinAscent = 4000

    fix_vertical_metrics(static_fonts)
    _check_vertical_metrics(static_fonts)


def test_fix_vertical_metrics_win_values(static_fonts):
    _check_vertical_metrics(static_fonts)
    for font in static_fonts:
        font["OS/2"].usWinAscent = font["OS/2"].usWinDescent = 0
        assert font["OS/2"].usWinAscent == 0 and font["OS/2"].usWinDescent == 0

    fix_vertical_metrics(static_fonts)
    _check_vertical_metrics(static_fonts)


def test_fix_vertical_metrics_typo_and_hhea_match(static_fonts):
    _check_vertical_metrics(static_fonts)
    for font in static_fonts:
        font["hhea"].ascent = 5000
        font["OS/2"].sTypoAscender == 1000
        assert font["hhea"].ascent != font["OS/2"].sTypoAscender

    fix_vertical_metrics(static_fonts)
    _check_vertical_metrics(static_fonts)


def test_fix_vertical_metrics_typo_metrics_enabled(static_fonts):
    _check_vertical_metrics(static_fonts)

    # family currently has fsSelection bit 7 enabled, unset it and change
    # the win Metrics to Typo values
    for font in static_fonts:
        font["OS/2"].fsSelection &= ~(1 << 7)
        font["OS/2"].usWinAscent = 500
        font["OS/2"].usWinDescent = 300

    fix_vertical_metrics(static_fonts)
    # Since fsSelection bit 7 is now enabled, in order for the metrics to visually
    # match the unfixed metrics, the typo values should now be the same as the
    # unfixed win values.
    for font in static_fonts:
        assert font["OS/2"].sTypoAscender == 500
        assert font["OS/2"].sTypoDescender == -300
        assert font["OS/2"].sTypoLineGap == 0
    _check_vertical_metrics(static_fonts)
