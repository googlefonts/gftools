import os

import pytest
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import ttProgram

from gftools.builder.apply_hinting import HintingMismatch, apply, extract

TEST_DATA = os.path.join(os.path.dirname(__file__), "..", "data", "test")
HINTED = os.path.join(TEST_DATA, "Montserrat-Regular.ttf")
TABLES = ("fpgm", "prep", "cvt ", "gasp", "hdmx", "LTSH", "VDMX")


def unhinted(path):
    font = TTFont(path)
    for tag in TABLES:
        if tag in font:
            del font[tag]
    for name in font.getGlyphOrder():
        glyph = font["glyf"][name]
        if hasattr(glyph, "program"):
            glyph.program = ttProgram.Program()
            glyph.program.fromBytecode(b"")
    return font


def test_extract_apply_round_trip(tmp_path):
    release = TTFont(HINTED)
    font = unhinted(HINTED)
    apply(font, extract(release))
    font.save(tmp_path / "out.ttf")
    out = TTFont(tmp_path / "out.ttf")
    for tag in TABLES:
        if tag in release:
            assert out.getTableData(tag) == release.getTableData(tag), tag
    for name in release.getGlyphOrder():
        a, b = release["glyf"][name], out["glyf"][name]
        assert getattr(a, "program", None) is None or (
            a.program.getBytecode() == b.program.getBytecode()
        ), name


def test_refuses_other_points():
    release = TTFont(HINTED)
    data = extract(release)
    font = unhinted(HINTED)
    name = next(n for n in data["glyphs"] if not font["glyf"][n].isComposite())
    font["glyf"][name].coordinates[0] = (
        font["glyf"][name].coordinates[0][0] + 1,
        font["glyf"][name].coordinates[0][1],
    )
    with pytest.raises(HintingMismatch, match=name):
        apply(font, data)


def test_restores_dropped_midpoints(tmp_path):
    # a compiler may drop an on-curve point halfway between two off-curves
    release = TTFont(HINTED)
    data = extract(release)
    font = unhinted(HINTED)
    name = next(n for n in data["midpoints"] if n in data["glyphs"])
    glyph = font["glyf"][name]
    drop = set(data["midpoints"][name]["points"])
    keep = [i for i in range(len(glyph.coordinates)) if i not in drop]
    ends = [e - sum(1 for d in drop if d <= e) for e in glyph.endPtsOfContours]
    glyph.coordinates = type(glyph.coordinates)([glyph.coordinates[i] for i in keep])
    glyph.flags = type(glyph.flags)([glyph.flags[i] for i in keep])
    glyph.endPtsOfContours = ends
    apply(font, data)
    restored = font["glyf"][name]
    assert list(restored.coordinates) == list(release["glyf"][name].coordinates)
    assert restored.program.getBytecode() == release["glyf"][name].program.getBytecode()
