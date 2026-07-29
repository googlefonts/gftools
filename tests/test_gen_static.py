from fontTools.ttLib import TTFont
import pytest
import os

from gftools.scripts.gen_static import main, instance_coordinates, parse_coordinates

TEST_DATA = os.path.join("data", "test")
VAR_FONT = os.path.join(TEST_DATA, "Inconsolata[wdth,wght].ttf")


def _name_record(ttFont, nameID):
    record = ttFont["name"].getName(nameID, 3, 1, 0x409)
    if record:
        return record.toUnicode()
    return None


def test_instance_coordinates():
    font = TTFont(VAR_FONT)
    assert instance_coordinates(font, "SemiBold") == {"wght": 600.0, "wdth": 100.0}
    with pytest.raises(ValueError, match="no fvar instance named 'Foobar'"):
        instance_coordinates(font, "Foobar")


def test_parse_coordinates():
    assert parse_coordinates(["wght=450", "wdth=75"]) == {"wght": 450.0, "wdth": 75.0}
    with pytest.raises(ValueError, match="Cannot parse coordinate 'wght'"):
        parse_coordinates(["wght"])


def test_gen_static_ribbi(tmp_path):
    out = str(tmp_path / "font-Bold.ttf")
    main([VAR_FONT, "My Family", "Bold", "-o", out])
    static_font = TTFont(out)
    assert "fvar" not in static_font
    assert _name_record(static_font, 1) == "My Family"
    assert _name_record(static_font, 2) == "Bold"
    assert static_font["OS/2"].fsSelection & (1 << 5)
    assert static_font["head"].macStyle == 1


def test_gen_static_non_ribbi(tmp_path):
    out = str(tmp_path / "font-SemiBold.ttf")
    main([VAR_FONT, "My Family", "SemiBold", "-o", out])
    static_font = TTFont(out)
    assert "fvar" not in static_font
    assert _name_record(static_font, 1) == "My Family SemiBold"
    assert _name_record(static_font, 2) == "Regular"
    assert _name_record(static_font, 16) == "My Family"
    assert _name_record(static_font, 17) == "SemiBold"


def test_gen_static_creates_output_dirs(tmp_path):
    out = str(tmp_path / "a" / "b" / "font-Regular.ttf")
    main([VAR_FONT, "My Family", "Regular", "-o", out])
    assert os.path.exists(out)


def test_gen_static_coordinates(tmp_path):
    out = str(tmp_path / "font-Regular.ttf")
    main([VAR_FONT, "My Family", "Regular", "--coordinates", "wght=450", "-o", out])
    static_font = TTFont(out)
    assert "fvar" not in static_font
    assert _name_record(static_font, 1) == "My Family"
    assert _name_record(static_font, 2) == "Regular"
