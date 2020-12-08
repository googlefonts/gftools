import pytest
from glob import glob
from fontTools.ttLib import TTFont
import tempfile
import os
from gftools.html import *
import re


TEST_DATA = os.path.join("data", "test")


@pytest.fixture
def SimpleTemplate():
    class SimpleTemplate(HtmlTemplater):
        def __init__(self, out, template_dir):
            super().__init__(out=out, template_dir=template_dir)
    return SimpleTemplate


@pytest.fixture
def static_fonts():
    return [TTFont(f) for f in glob(os.path.join("data", "test", "mavenpro", "*.ttf"))]


@pytest.fixture
def var_font():
    return TTFont(os.path.join(TEST_DATA, "Inconsolata[wdth,wght].ttf"))


def _string_to_file(string, dst):
    with open(dst, "w") as doc:
        doc.write(string)
    return dst


def _file_to_string(fp):
    with open(fp) as f:
        return f.read()


def test_templating_basic(SimpleTemplate):

    with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as template_dir:
        template_out = os.path.join(template_dir, "index.html")
        _string_to_file("<b>{{ text }}</b>", template_out)

        templater = SimpleTemplate(out=project_dir, template_dir=template_dir)
        templater.text = "Hello World"
        templater.build_pages(["index.html"])
        result = _file_to_string(templater.documents["index"])
        assert result == "<b>Hello World</b>"


def test_templating_with_multiple_variables(SimpleTemplate):
    with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as template_dir:
        template_out = os.path.join(template_dir, "contact.html")
        _string_to_file("<b>{{ text }}</b><p>{{ url }}</p>", template_out)

        templater = SimpleTemplate(out=project_dir, template_dir=template_dir)
        templater.text = "Hello you"
        templater.url = "https://www.google.com"
        templater.build_pages(["contact.html"])
        result = _file_to_string(templater.documents["contact"])
        assert result == "<b>Hello you</b><p>https://www.google.com</p>"


def test_templating_populating_multiple_pages(SimpleTemplate):
    with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as template_dir:
        template_out = os.path.join(template_dir, "index.html")
        _string_to_file("<b>{{ text }}</b>", template_out)
        template1_out = os.path.join(template_dir, "contact.html")
        _string_to_file("<b>{{ text }}</b><p>{{ url }}</p>", template1_out)

        templater = SimpleTemplate(out=project_dir, template_dir=template_dir)
        templater.text = "Hello World"
        templater.url = "https://www.google.com"
        templater.build_pages(["index.html", "contact.html"])

        assert len(templater.documents) == 2
        
        index_result = _file_to_string(templater.documents["index"])
        assert index_result == "<b>Hello World</b>"

        contact_result = _file_to_string(templater.documents["contact"])
        assert contact_result == "<b>Hello World</b><p>https://www.google.com</p>"


def test_CSSElement_used_as_fontface():
    font_face = CSSElement(
        selector="@font-face",
        font_family="Roboto",
        font_weight=400,
    )
    assert font_face.render() == "@font-face { font-family: Roboto; font-weight: 400; }"


def test_CSSEement_used_as_class():
    class_ = CSSElement(
        selector=".bold",
        font_family="Roboto",
        font_weight=700
    )
    assert class_.render() == ".bold { font-family: Roboto; font-weight: 700; }"


def test_CSSElement_private_attribs():
    class_with_private_variables = CSSElement(
        selector=".normal",
        _style="Foobar",
        font_weight=400
    )
    assert "Foobar" not in class_with_private_variables.render()


def _test_waterfall(waterfall_result, html):
    # Check pangram strings have been added.
    assert "quick wafting zephyrs vex bold jim." in waterfall_result

    font_faces = re.findall(r"@font-face", waterfall_result)
    assert len(font_faces) == len(html.css_font_faces)

    font_styles = re.findall(r".[A-z-]{1,50} \{ font-family", waterfall_result)
    assert len(font_styles) == len(html.css_font_classes)


def test_HtmlProof_with_static_fonts(static_fonts):
    with tempfile.TemporaryDirectory() as project_dir:
        html = HtmlProof(
            out=project_dir,
            fonts=static_fonts
        )
        # Each font must have an @font-face and font_class
        assert len(html.fonts) == len(html.css_font_faces) == len(html.css_font_classes)
        html.build_pages(["waterfall.html"])

        waterfall_result = _file_to_string(html.documents["waterfall"])
        _test_waterfall(waterfall_result, html)


def test_HtmlProof_with_vf(var_font):
    with tempfile.TemporaryDirectory() as project_dir:
        html = HtmlProof(
            out=project_dir,
            fonts=[var_font]
        )
        assert len(html.fonts) == len(html.css_font_faces)
        # VFs can contain multiple styles in a single font
        assert len(html.css_font_faces) != len(html.css_font_classes)
        html.build_pages(["waterfall.html"])

        waterfall_result = _file_to_string(html.documents["waterfall"])
        _test_waterfall(waterfall_result, html)

