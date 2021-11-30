from fontTools.ttLib import TTFont
from gftools.fix import FixWidthMeta
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


# FixFSType
def test_fix_ttf_fs_type(static_font):
    from gftools.fix import FixFSType
    static_font["OS/2"].fsType = 4
    fix = FixFSType(static_font)
    fix.fix()
    assert static_font["OS/2"].fsType == 0


def test_fix_glyphs_fs_type(glyphs_font):
    from gftools.fix import FixFSType
    glyphs_font.customParameters['fsType'] = [1]
    fix = FixFSType(glyphs_font)
    fix.fix()
    assert glyphs_font.customParameters['fsType'] == []


def test_fix_ufo_fs_type(ufo_font):
    from gftools.fix import FixFSType
    ufo_font.info.openTypeOS2Type = [1]
    fix = FixFSType(ufo_font)
    fix.fix()
    assert ufo_font.info.openTypeOS2Type == []

# FixWidthMeta
def test_fix_ttf_width_meta(static_font):
    from gftools.fix import FixWidthMeta
    for glyph in static_font['hmtx'].metrics:
        static_font['hmtx'].metrics[glyph] = (500, 500)
    fix = FixWidthMeta(static_font)
    fix.fix()
    assert static_font['post'].isFixedPitch == 1
    assert static_font['OS/2'].panose.bFamilyType == 2
    assert static_font['OS/2'].panose.bProportion == 9


def test_fix_glyphs_width_meta(glyphs_font):
    from gftools.fix import FixWidthMeta
    for glyph in glyphs_font.glyphs:
        for layer in glyph.layers:
            layer.width = 500
    fix = FixWidthMeta(glyphs_font)
    fix.fix()
    glyphs_font.customParameters['panose'] == [2, 0, 0, 9, 0, 0, 0, 0, 0, 0]


def test_fix_ufo_width_meta(ufo_font):
    from gftools.fix import FixWidthMeta
    for glyph in ufo_font:
        glyph.width = 500
    fix = FixWidthMeta(ufo_font)
    fix.fix()
    ufo_font.info.openTypeOS2Panose == [2, 0, 0, 9, 0, 0, 0, 0, 0, 0]