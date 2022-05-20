import pytest
from glob import glob
from fontTools.ttLib import TTFont
import tempfile
import os
from gftools.html import *
import re
from copy import deepcopy


TEST_DATA = os.path.join("data", "test")


@pytest.fixture
def SimpleTemplate():
    class SimpleTemplate(HtmlTemplater):
        def __init__(self, out, template_dir):
            super().__init__(out=out, template_dir=template_dir)
    return SimpleTemplate


@pytest.fixture
def static_fonts():
    return [f for f in glob(os.path.join("data", "test", "mavenpro", "*.ttf"))]


@pytest.fixture
def static_ttfonts():
    return [TTFont(f) for f in glob(os.path.join("data", "test", "mavenpro", "*.ttf"))]


@pytest.fixture
def var_font():
    return os.path.join(TEST_DATA, "Inconsolata[wdth,wght].ttf")


@pytest.fixture
def var_ttfont():
    return TTFont(os.path.join(TEST_DATA, "Inconsolata[wdth,wght].ttf"))


@pytest.fixture
def var_font2():
    return os.path.join(TEST_DATA, "MavenPro[wght].ttf")


def _string_to_file(string, dst):
    with open(dst, "w") as doc:
        doc.write(string)
    return dst


def _file_to_string(fp):
    with open(fp) as f:
        return f.read()

def get_fonts(path):
    font_suffixes = {'ttf', 'otf'}
    fonts = []
    for filename in os.listdir(path):
        full_path = os.path.join(path, filename)
        suffix = filename.split('.')[-1]

        if suffix.lower() in font_suffixes:
            fonts.append(TTFont(full_path))
    return fonts

def test_html_family():
    base_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    from gftools.utils import mkdir, get_sorted_font_indices
    font_path = os.path.join(base_path, "data", "test", "mavenpro")
    static_ttfonts = get_fonts(font_path)
    sorted_indices = get_sorted_font_indices(static_ttfonts)
    
    out = os.path.join(base_path, TEST_DATA, "mavenpro", "browser_previews")
    mkdir(out)
    html = HtmlProof(
        out=out,
        fonts=[static_ttfonts[i].reader.file.name for i in sorted_indices]
    )
    html.build_pages(["family.html"], pt_size=16)