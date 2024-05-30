from gftools.scripts.fontsetter import setter, getter
import pytest
from fontTools.ttLib import TTFont
import os


TEST_FONT = TTFont(os.path.join("data", "test", "Inconsolata[wdth,wght].ttf"))


@pytest.mark.parametrize(
    """obj,path,val,res""",
    [
        ([10], [0], 100, [100]),
        ([10, [10]], [1, 0], 100, [10, [100]]),
        ([(0, [1, (2,)]), [1, 0], 100, (0, [100, (2,)])]),
        ([[0, (0, (0,))], [1, 1, 0], 100, [0, (0, (100,))]]),
        ({"A": {"B": [0, [10]]}}, ["A", "B", 1], [100], {"A": {"B": [0, [100]]}}),
        ([0x1], [0], "|= 0x2", [0x3]),
    ],
)
def test_setter(obj, path, val, res):
    setter(obj, path, val)
    assert obj == res


@pytest.mark.parametrize(
    """obj,path,val""",
    [
        # simple atttribs
        (TEST_FONT, ["OS/2", "fsSelection"], 64),
        (TEST_FONT, ["hhea", "ascender"], 1000),
        # attrib then dict
        (TEST_FONT, ["hmtx", "metrics", "A"], (10, 10)),
        # attrib then attrib
        (TEST_FONT, ["OS/2", "panose", "bSerifStyle"], 10),
    ],
)
def test_setter_on_fonts(obj, path, val):
    setter(obj, path, val)
    assert getter(obj, path) == val
