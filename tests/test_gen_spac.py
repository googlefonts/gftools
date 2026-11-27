import os

import pytest
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

from gftools.scripts.gen_spac import add_spacing_axis

CWD = os.path.dirname(__file__)
TEST_FONT = os.path.join(CWD, "..", "data", "test", "MavenPro[wght].ttf")


@pytest.fixture
def spaced_font(tmp_path):
    font = TTFont(TEST_FONT)
    add_spacing_axis(font, -50, 100)
    # Round-trip through disk so gvar is compiled and parsed like a real build.
    path = tmp_path / "spaced.ttf"
    font.save(path)
    return TTFont(path)


@pytest.mark.parametrize(
    "glyph_name",
    [
        "A",  # simple glyph with contours
        "Aacute",  # composite glyph, no outline coordinates of its own
        "space",  # empty glyph with existing gvar tuples
        "uni00A0",  # empty glyph
        "NULL",  # empty glyph with no gvar tuples at all
    ],
)
def test_spac_axis_changes_every_glyph_advance(spaced_font, glyph_name):
    assert "SPAC" in {a.axisTag for a in spaced_font["fvar"].axes}
    default_advance = spaced_font["hmtx"][glyph_name][0]

    at_max = instantiateVariableFont(
        spaced_font, {"wght": None, "SPAC": 100}, inplace=False
    )
    at_min = instantiateVariableFont(
        spaced_font, {"wght": None, "SPAC": -50}, inplace=False
    )
    # The amount is added to both side bearings, so the advance moves by twice it.
    assert at_max["hmtx"][glyph_name][0] == default_advance + 200
    # An advance cannot go below zero, so zero-width glyphs stay at zero.
    assert at_min["hmtx"][glyph_name][0] == max(0, default_advance - 100)


def test_spac_axis_in_STAT(spaced_font):
    stat = spaced_font["STAT"].table
    name = spaced_font["name"]
    axes = [a.AxisTag for a in stat.DesignAxisRecord.Axis]
    assert axes == [a.axisTag for a in spaced_font["fvar"].axes]
    assert stat.DesignAxisCount == len(axes)
    spac_index = axes.index("SPAC")
    spac_values = [
        v for v in stat.AxisValueArray.AxisValue if v.AxisIndex == spac_index
    ]
    assert len(spac_values) == 1
    (value,) = spac_values
    assert value.Format == 1
    assert value.Value == 0.0
    assert name.getDebugName(value.ValueNameID) == "Default"
    assert stat.AxisValueCount == len(stat.AxisValueArray.AxisValue)
