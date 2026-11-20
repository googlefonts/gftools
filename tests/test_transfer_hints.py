import os

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import ttProgram

from gftools.scripts.transfer_hints import TABLES, load, transfer

TEST_DATA = os.path.join(os.path.dirname(__file__), "..", "data", "test")
HINTED = os.path.join(TEST_DATA, "Montserrat-Regular.ttf")


def unhinted(path):
    font = TTFont(path, recalcBBoxes=False)
    for tag in TABLES:
        if tag in font:
            del font[tag]
    for name in font.getGlyphOrder():
        glyph = font["glyf"][name]
        if hasattr(glyph, "program"):
            glyph.program = ttProgram.Program()
            glyph.program.fromBytecode(b"")
    return font


def instructed_simple(font, accept=lambda glyph: True):
    for name in font.getGlyphOrder():
        glyph = font["glyf"][name]
        program = getattr(glyph, "program", None)
        if (
            program is not None
            and program.getBytecode()
            and not glyph.isComposite()
            and glyph.numberOfContours > 0
            and accept(glyph)
        ):
            return name
    raise AssertionError("no such glyph in the test font")


def assert_hinted_like(out, release):
    for tag in TABLES:
        if tag in release:
            assert out.getTableData(tag) == release.getTableData(tag), tag
    for name in release.getGlyphOrder():
        a, b = release["glyf"][name], out["glyf"][name]
        if getattr(a, "program", None) is not None:
            assert a.program.getBytecode() == b.program.getBytecode(), name
            assert list(a.getCoordinates(release["glyf"])[0]) == list(
                b.getCoordinates(out["glyf"])[0]
            ), name


def test_round_trip(tmp_path):
    release = TTFont(HINTED)
    font = unhinted(HINTED)
    assert transfer(TTFont(HINTED), font) == {}
    font.save(tmp_path / "out.ttf")
    assert_hinted_like(TTFont(tmp_path / "out.ttf"), release)


def test_refuses_other_points():
    font = unhinted(HINTED)
    name = instructed_simple(TTFont(HINTED))
    glyph = font["glyf"][name]
    x, y = glyph.coordinates[0]
    glyph.coordinates[0] = (x + 1, y)
    refused = transfer(TTFont(HINTED), font)
    assert name in refused
    assert "fpgm" not in font  # nothing written


def midpoint_index(glyph):
    start = 0
    for end in glyph.endPtsOfContours:
        n = end - start + 1
        for k in range(n):
            i, p, q = start + k, start + (k - 1) % n, start + (k + 1) % n
            (x, y), (px, py), (qx, qy) = (
                glyph.coordinates[i],
                glyph.coordinates[p],
                glyph.coordinates[q],
            )
            if (
                glyph.flags[i] & 1
                and not glyph.flags[p] & 1
                and not glyph.flags[q] & 1
                and px + qx == 2 * x
                and py + qy == 2 * y
            ):
                return i
        start = end + 1
    return None


def drop_point(glyph, index):
    keep = [i for i in range(len(glyph.coordinates)) if i != index]
    glyph.coordinates = type(glyph.coordinates)([glyph.coordinates[i] for i in keep])
    glyph.flags = type(glyph.flags)([glyph.flags[i] for i in keep])
    glyph.endPtsOfContours = [
        e - (1 if index <= e else 0) for e in glyph.endPtsOfContours
    ]


def test_takes_the_release_points_back(tmp_path):
    # a compiler drops an implied on-curve point, and starts a contour elsewhere
    release = TTFont(HINTED)
    font = unhinted(HINTED)
    implied = instructed_simple(release, lambda g: midpoint_index(g) is not None)
    drop_point(font["glyf"][implied], midpoint_index(font["glyf"][implied]))
    rotated = instructed_simple(
        release,
        lambda g: g.endPtsOfContours[0] > 2 and g is not release["glyf"][implied],
    )
    glyph = font["glyf"][rotated]
    end = glyph.endPtsOfContours[0]
    order = list(range(1, end + 1)) + [0] + list(range(end + 1, len(glyph.coordinates)))
    glyph.coordinates = type(glyph.coordinates)([glyph.coordinates[i] for i in order])
    glyph.flags = type(glyph.flags)([glyph.flags[i] for i in order])
    assert transfer(TTFont(HINTED), font) == {}
    font.save(tmp_path / "out.ttf")
    assert_hinted_like(TTFont(tmp_path / "out.ttf"), release)


def test_ttx_source(tmp_path):
    ttx = tmp_path / "hints.ttx"
    TTFont(HINTED).saveXML(
        ttx,
        tables=["GlyphOrder", "head", "maxp", "hmtx", "glyf"]
        + [t for t in TABLES if t in TTFont(HINTED)],
    )
    font = unhinted(HINTED)
    assert transfer(load(str(ttx)), font) == {}
    font.save(tmp_path / "out.ttf")
    assert_hinted_like(TTFont(tmp_path / "out.ttf"), TTFont(HINTED))
