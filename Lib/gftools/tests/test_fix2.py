from attr import dataclass
from fontTools.ttLib import TTFont
from glyphsLib import GSFont
from defcon import Font
import os
import pytest


TEST_DATA = os.path.join("data", "test")


@pytest.fixture
def static_font():
    return TTFont(os.path.join(TEST_DATA, "Lora-Regular.ttf"))


@pytest.fixture
def var_font():
    return TTFont(os.path.join(TEST_DATA, "Inconsolata[wdth,wght].ttf"))


@pytest.fixture
def glyphs_font():
    return GSFont(os.path.join(TEST_DATA, "MavenPro.glyphs"))


@pytest.fixture
def ufo_font():
    return Font(os.path.join(TEST_DATA, "MavenPro-Regular.ufo"))


# Taken from https://github.com/googlefonts/gf-docs/tree/main/Spec#supported-styles
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

# SpecFSType
def test_fix_ttf_fs_type(static_font):
    from gftools.spec.font import SpecFSType
    static_font["OS/2"].fsType = 4
    spec = SpecFSType(static_font)
    spec.fix()
    assert static_font["OS/2"].fsType == 0


def test_fix_glyphs_fs_type(glyphs_font):
    from gftools.spec.font import SpecFSType
    glyphs_font.customParameters['fsType'] = [1]
    spec = SpecFSType(glyphs_font)
    spec.fix()
    assert glyphs_font.customParameters['fsType'] == []


def test_fix_ufo_fs_type(ufo_font):
    from gftools.spec.font import SpecFSType
    ufo_font.info.openTypeOS2Type = [1]
    spec = SpecFSType(ufo_font)
    spec.fix()
    assert ufo_font.info.openTypeOS2Type == []


# SpecMonospace
def test_fix_ttf_monospace(static_font):
    from gftools.spec.font import SpecMonospace
    for glyph in static_font['hmtx'].metrics:
        static_font['hmtx'].metrics[glyph] = (500, 500)
    spec = SpecMonospace(static_font)
    spec.fix()
    assert static_font['post'].isSpecedPitch == 1
    assert static_font['OS/2'].panose.bFamilyType == 2
    assert static_font['OS/2'].panose.bProportion == 9


def test_fix_glyphs_monospace(glyphs_font):
    from gftools.spec.font import SpecMonospace
    for glyph in glyphs_font.glyphs:
        for layer in glyph.layers:
            layer.width = 500
    spec = SpecMonospace(glyphs_font)
    spec.fix()
    glyphs_font.customParameters['panose'] == [2, 0, 0, 9, 0, 0, 0, 0, 0, 0]


def test_fix_ufo_monospace(ufo_font):
    from gftools.spec.font import SpecMonospace
    for glyph in ufo_font:
        glyph.width = 500
    spec = SpecMonospace(ufo_font)
    spec.fix()
    ufo_font.info.openTypeOS2Panose == [2, 0, 0, 9, 0, 0, 0, 0, 0, 0]


#SpecStyles
@pytest.mark.parametrize(
    STYLE_HEADERS,
    STYLE_TABLE
)
def test_fix_ttf_style_linking(static_font, style, weight_class, fs_selection, mac_style):
    from gftools.spec.font import SpecStyles
    name = static_font["name"]
    name.setName(style, 2, 3, 1, 0x409)
    name.setName(style, 17, 3, 1, 0x409)
    spec = SpecStyles(static_font)
    spec.fix()
    assert static_font["OS/2"].usWeightClass == weight_class
    assert static_font["OS/2"].fsSelection & fs_selection == fs_selection
    assert static_font["head"].macStyle == mac_style

@pytest.mark.parametrize(
    STYLE_HEADERS,
    STYLE_TABLE
)
def test_fix_glyphs_style_linking(glyphs_font, style, weight_class, fs_selection, mac_style):
    from gftools.spec.font import SpecStyles
    from glyphsLib import GSInstance
    inst = GSInstance()
    inst.name = style
    glyphs_font.instances = [inst]
    spec = SpecStyles(glyphs_font)
    spec.fix()
    assert inst.weightClass == weight_class
    # TODO check the other bits


@pytest.mark.parametrize(
    STYLE_HEADERS,
    STYLE_TABLE
)
def test_fix_ufo_style_linking(ufo_font, style, weight_class, fs_selection, mac_style):
    from gftools.spec.font import SpecStyles
    ufo_font.info.styleName = style
    spec = SpecStyles(ufo_font)
    spec.fix()
    assert ufo_font.info.openTypeOS2WeightClass == weight_class
    # TODO Check the other bits


def _get_fvar_instance_names(var_font):
    inst_names = []
    for inst in var_font['fvar'].instances:
        inst_name = var_font['name'].getName(inst.subfamilyNameID, 3, 1, 0x409)
        inst_names.append(inst_name.toUnicode())
    return inst_names


def test_fix_ttf_instances(var_font):
    from copy import deepcopy
    from gftools.spec.font import SpecInstances
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

    spec = SpecInstances(var_font)
    spec.fix()
    inst_names = _get_fvar_instance_names(var_font)
    assert inst_names == roman_instances

    # Let's rename the font style so the font becomes an Italic variant
    var_font2 = deepcopy(var_font)
    var_font2["name"].setName("Italic", 2, 3, 1, 0x409)
    var_font2["name"].setName("Italic", 17, 3, 1, 0x409)

    spec = SpecInstances(var_font2)
    spec.fix()
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
    spec = SpecInstances(var_font3)
    spec.fix()
    inst_names = _get_fvar_instance_names(var_font3)
    assert inst_names == roman_instances + italic_instances


def test_fix_glyphs_instances(glyphs_font):
    from gftools.spec.font import SpecInstances
    from glyphsLib import GSInstance

    reg_inst = GSInstance()
    reg_inst.name = "Regular"
    bad_inst = GSInstance()
    bad_inst.name = "FooBar"
    glyphs_font.instances = [reg_inst, bad_inst]
    spec = SpecInstances(glyphs_font)
    spec.fix()
    assert glyphs_font.instances == [reg_inst]


# SpecTables
def test_fix_ttf_tables(static_font):
    from gftools.spec.font import SpecTables
    from fontTools.ttLib import newTable

    tsi_tbl = newTable("TSI1")
    static_font["TSI1"] = tsi_tbl
    spec = SpecTables(static_font)
    spec.fix()
    assert "TSI1" not in static_font.keys()