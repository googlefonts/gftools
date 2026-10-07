import logging
import os
import re
from collections import OrderedDict

import pytest
from fontTools.designspaceLib import AxisDescriptor, AxisMappingDescriptor
from fontTools.ttLib import TTFont
from fontTools.varLib import _add_avar

from gftools.builder.operations.avar2ToAvar1 import Avar2ToAvar1
from gftools.scripts.avar2_to_avar1 import (
    _crossings,
    _grid_knots,
    _parse_grid_spec,
    main,
)

CWD = os.path.dirname(__file__)
TEST_FONT = os.path.join(CWD, "..", "data", "test", "Inconsolata[wdth,wght].ttf")

# Normalized knots of a two-sided axis, as _clean_knots produces them.
KNOTS = [-1.0, -0.6, -0.2, 0.0, 0.3, 0.7, 1.0]


def test_parse_grid_spec():
    assert _parse_grid_spec("opsz:3, wdth:5,wght") == {
        "opsz": 3,
        "wdth": 5,
        "wght": None,
    }
    with pytest.raises(ValueError, match="bad master count"):
        _parse_grid_spec("wdth:x")
    # a slash list is a list of user positions; counts and bare tags still work beside it
    assert _parse_grid_spec("wght:300/400/700,opsz:14/21,wdth:3,ROND") == {
        "wght": [300.0, 400.0, 700.0],
        "opsz": [14.0, 21.0],
        "wdth": 3,
        "ROND": None,
    }
    with pytest.raises(ValueError, match="bad position list"):
        _parse_grid_spec("wght:300/x")


def test_crossings():
    # path from -0.4 to 0.6 crosses 0 at t=0.4 and 0.3 at t=0.7; endpoints and
    # breakpoints outside the span do not count
    assert _crossings(-0.4, 0.6, [0.0, 0.3, 0.6, 1.0]) == pytest.approx([0.4, 0.7])
    assert _crossings(0.5, 0.5, [0.0]) == []
    assert _crossings(0.2, 0.8, [0.0]) == []


def test_grid_knots_no_count_keeps_every_knot_and_cuts():
    assert _grid_knots(KNOTS, None) == KNOTS
    assert _grid_knots([-1.0, 0.0, 1.0], None, cuts=1) == [-1.0, -0.5, 0.0, 0.5, 1.0]


def test_grid_knots_fewer_than_font_picks_from_font_knots():
    # Default and extremes always, then the font's own knots spread evenly.
    assert _grid_knots(KNOTS, 3) == [-1.0, 0.0, 1.0]
    chosen = _grid_knots(KNOTS, 5)
    assert len(chosen) == 5
    assert {-1.0, 0.0, 1.0} <= set(chosen) <= set(KNOTS)
    assert _grid_knots(KNOTS, len(KNOTS)) == KNOTS


def test_grid_knots_more_than_font_bisects_largest_gaps():
    chosen = _grid_knots(KNOTS, 10)
    assert len(chosen) == 10
    assert set(KNOTS) <= set(chosen)
    assert chosen == sorted(chosen)
    # The two widest intervals (-1..-0.6 and 0.3..0.7) are split first.
    assert {-0.8, 0.5} <= set(chosen)


def test_grid_knots_one_sided_axis_and_too_small_count():
    assert _grid_knots([0.0, 0.5, 1.0], 2) == [0.0, 1.0]
    with pytest.raises(ValueError, match="below the 3 knots"):
        _grid_knots(KNOTS, 2)


@pytest.mark.parametrize(
    "grid,expected",
    [
        ({"opsz": 3, "wdth": 5, "wght": 9}, "--grid opsz:3,wdth:5,wght:9"),
        ({"opsz": 3, "wght": None}, "--grid opsz:3,wght"),
        (
            {"wght": [300, 400, 700], "opsz": [14, 21]},
            "--grid wght:300/400/700,opsz:14/21",
        ),
        (["wdth", "wght"], "--grid wdth,wght"),
        ("wdth:3,wght:4", "--grid wdth:3,wght:4"),
        (None, ""),
    ],
)
def test_builder_operation_grid(grid, expected):
    original = {"operation": "avar2ToAvar1"}
    if grid is not None:
        original["grid"] = grid
    op = Avar2ToAvar1(original=original)
    assert op.validate()
    assert op.variables["grid"] == expected


def test_builder_operation_rejects_bad_grid():
    with pytest.raises(ValueError, match="must be an integer"):
        Avar2ToAvar1(original={"grid": {"wght": "lots"}}).validate()
    with pytest.raises(ValueError, match="grid must be"):
        Avar2ToAvar1(original={"grid": 3}).validate()


@pytest.fixture
def avar2_font(tmp_path):
    """Inconsolata with a cross-axis avar2 mapping added, so the flattener
    has something to resample."""
    font = TTFont(TEST_FONT)
    axes = OrderedDict()
    for fvar_axis in font["fvar"].axes:
        axis = AxisDescriptor()
        axis.tag = axis.name = fvar_axis.axisTag
        axis.minimum = fvar_axis.minValue
        axis.default = fvar_axis.defaultValue
        axis.maximum = fvar_axis.maxValue
        axes[axis.tag] = axis
    mappings = [
        AxisMappingDescriptor(inputLocation=i, outputLocation=o)
        for i, o in [
            ({"wght": 900, "wdth": 100}, {"wght": 900, "wdth": 90}),
            ({"wght": 900, "wdth": 50}, {"wght": 900, "wdth": 60}),
            ({"wght": 200, "wdth": 200}, {"wght": 250, "wdth": 200}),
        ]
    ]
    del font["avar"]
    _add_avar(font, axes, mappings, list(axes))
    assert font["avar"].majorVersion == 2
    path = tmp_path / "Inconsolata-avar2.ttf"
    font.save(path)
    return path


def test_grid_counts_end_to_end(avar2_font, tmp_path, caplog):
    out = tmp_path / "out.ttf"
    with caplog.at_level(logging.INFO, logger="gftools.avar2_to_avar1"):
        main(
            [
                str(avar2_font),
                "--grid",
                "wdth:3,wght:4",
                "--no-verify",
                "-o",
                str(out),
            ]
        )
    assert "--grid wdth:3 x wght:4 = 12 grid masters" in caplog.text
    result = TTFont(out)
    # No avar1 mapping was given, so varLib writes no avar at all.
    assert "avar" not in result or result["avar"].majorVersion == 1
    assert [a.axisTag for a in result["fvar"].axes] == ["wght", "wdth"]


@pytest.fixture
def crossing_font(tmp_path):
    """Inconsolata with mappings that take wdth above its default at wght 200
    and below it at wght 300, so wdth crosses its default part-way between
    those two input knots, where nothing marks it."""
    font = TTFont(TEST_FONT)
    axes = OrderedDict()
    for fvar_axis in font["fvar"].axes:
        axis = AxisDescriptor()
        axis.tag = axis.name = fvar_axis.axisTag
        axis.minimum = fvar_axis.minValue
        axis.default = fvar_axis.defaultValue
        axis.maximum = fvar_axis.maxValue
        axes[axis.tag] = axis
    mappings = [
        AxisMappingDescriptor(inputLocation=i, outputLocation=o)
        for i, o in [
            ({"wght": 200, "wdth": 100}, {"wght": 200, "wdth": 150}),
            ({"wght": 300, "wdth": 100}, {"wght": 300, "wdth": 60}),
        ]
    ]
    del font["avar"]
    _add_avar(font, axes, mappings, list(axes))
    path = tmp_path / "Inconsolata-crossing.ttf"
    font.save(path)
    return path


def _tuples_at(font, tag, peak):
    return [
        v
        for vs in font["gvar"].variations.values()
        for v in vs
        if tag in v.axes and abs(v.axes[tag][1] - peak) < 1e-6
    ]


def test_refine_crossings_end_to_end(crossing_font, tmp_path, caplog):
    out = tmp_path / "out.ttf"
    with caplog.at_level(logging.INFO, logger="gftools.avar2_to_avar1"):
        main(
            [
                str(crossing_font),
                "--grid",
                "wdth,wght",
                "--refine-crossings",
                "--no-verify",
                "-o",
                str(out),
            ]
        )
    # the grid is unchanged; the one crossing sits on the wght edge between
    # 200 and 300 at wdth 100, where wdth crosses its default
    assert "wdth:3 x wght:4 = 12 grid masters" in caplog.text
    assert "Building variable font from 12 masters" in caplog.text
    assert "1 crossings to refine" in caplog.text
    assert "wdth crosses 0 moving wght between wght=200 and wght=300" in caplog.text
    # wdth is at its default there, so two guards (wdth 50 and 200) follow
    assert "Refining at 1 locations (2 guards)" in caplog.text
    result = TTFont(out)
    # the local master's tent runs from the 200 knot through the crossing
    # to the 300 knot (wght 200..400 is normalized -1..0, 300 is -0.5)
    peaks = {
        round(v.axes["wght"][1], 4)
        for vs in result["gvar"].variations.values()
        for v in vs
        if "wght" in v.axes
    }
    (peak,) = [p for p in peaks if -1 < p < -0.5]
    for tv in _tuples_at(result, "wght", peak):
        assert tv.axes["wght"] == pytest.approx((-1.0, peak, -0.5))
        assert "wdth" not in tv.axes or tv.axes["wdth"][1] != 0
    assert "HVAR" in result
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="gftools.avar2_to_avar1"):
        main([str(crossing_font), "--grid", "wdth,wght", "--no-verify", "-o", str(out)])
    assert "Refining" not in caplog.text


def test_refine_at_end_to_end(avar2_font, tmp_path, caplog):
    out = tmp_path / "out.ttf"
    with caplog.at_level(logging.INFO, logger="gftools.avar2_to_avar1"):
        main(
            [
                str(avar2_font),
                "--grid",
                "wdth:3,wght:3",
                "--refine-at",
                "wght=650,wdth=150",
                "--no-refine-guards",
                "-o",
                str(out),
            ]
        )
    assert "Refining at 1 locations (0 guards)" in caplog.text
    # exact at the refined location afterwards, up to integer rounding
    # (which compounds through nested composites)
    match = re.search(
        r"master at wght=650, wdth=150: worst error ([\d.]+) -> ([\d.]+) units",
        caplog.text,
    )
    assert match, caplog.text
    before, after = float(match.group(1)), float(match.group(2))
    assert before > 20 and after < 3
    result = TTFont(out)
    # wght 650 is normalized 0.5 (default 400, max 900); wdth 150 is 0.5
    tuples = _tuples_at(result, "wght", 0.5)
    assert tuples
    for tv in tuples:
        assert tv.axes["wght"] == pytest.approx((0.0, 0.5, 1.0))
        assert tv.axes["wdth"] == pytest.approx((0.0, 0.5, 1.0))


def test_refine_at_rejects_unknown_axis(avar2_font, tmp_path):
    with pytest.raises(ValueError, match="not varying in the output font"):
        main([str(avar2_font), "--refine-at", "opsz=9", "-o", str(tmp_path / "o.ttf")])


def test_refine_crossings_needs_grid(avar2_font, tmp_path):
    with pytest.raises(ValueError, match="needs --grid"):
        main([str(avar2_font), "--refine-crossings", "-o", str(tmp_path / "o.ttf")])


def test_grid_positions_end_to_end(avar2_font, tmp_path, caplog):
    out = tmp_path / "out.ttf"
    # Inconsolata: wdth 50..100..200, wght 200..400..900. Explicit positions
    # become the grid; the default and extremes are added when left out.
    with caplog.at_level(logging.INFO, logger="gftools.avar2_to_avar1"):
        main(
            [
                str(avar2_font),
                "--grid",
                "wdth:50/100/200,wght:300/700",
                "--no-verify",
                "-o",
                str(out),
            ]
        )
    assert "--grid wght: adding 200, 400, 900" in caplog.text
    assert "--grid wdth:3 x wght:5 = 15 grid masters" in caplog.text
    result = TTFont(out)
    peaks = {
        round(v.axes["wght"][1], 3)
        for vs in result["gvar"].variations.values()
        for v in vs
        if "wght" in v.axes
    }
    # wght 300 is normalized -0.5, 700 is +0.6 (default 400, max 900)
    assert {-0.5, 0.6} <= peaks


def test_builder_operation_refine():
    op = Avar2ToAvar1(
        original={
            "operation": "avar2ToAvar1",
            "refine": [{"wght": 352, "wdth": 25, "opsz": 9}, {"wght": 370}],
            "refine_crossings": True,
        }
    )
    assert op.validate()
    assert (
        op.variables["refine"]
        == "--refine-at wght=352,wdth=25,opsz=9 --refine-at wght=370 --refine-crossings"
    )
    assert (
        Avar2ToAvar1(original={"operation": "avar2ToAvar1"}).variables["refine"] == ""
    )
    with pytest.raises(ValueError, match="must map axis tags to numbers"):
        Avar2ToAvar1(original={"refine": [{"wght": "heavy"}]}).validate()
