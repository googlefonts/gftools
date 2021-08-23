import pytest
import os
from glob import glob
from gftools.meta import gen_meta_table
from fontTools.ttLib import TTFont


TEST_DATA = os.path.join("data", "test")


def test_meta_where_none_present():
    a_font = TTFont(os.path.join(TEST_DATA, "Inconsolata[wdth,wght].ttf"))
    assert "meta" not in a_font
    gen_meta_table(a_font, {
        "slng": ["en-Latn", "tur-Hang-IT", "tur", "Latn"],
        "dlng": ["en-Latn-AZ"]
    })
    assert a_font["meta"].data == {
        "slng": "Latn, en-Latn, tur-Hang-IT",
        "dlng": "en-Latn-AZ"
    }

def test_meta_where_one_present():
    a_font = TTFont(os.path.join(TEST_DATA, "Inconsolata[wdth,wght].ttf"))
    assert "meta" not in a_font
    gen_meta_table(a_font, {
        "slng": ["en-Latn", "tur-Hang-IT", "tur"],
        "dlng": ["en-Latn-AZ"]
    })
    assert "meta" in a_font
    gen_meta_table(a_font, {
        "slng": ["es-Arab-RS-spanglis"],
    })

    assert a_font["meta"].data == {
        "slng": "en-Latn, es-Arab-RS-spanglis, tur-Hang-IT",
        "dlng": "en-Latn-AZ"
    }
