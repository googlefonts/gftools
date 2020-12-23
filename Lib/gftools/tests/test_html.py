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


def test_templating_basic(SimpleTemplate):
    with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as template_dir:
        template_out = os.path.join(template_dir, "index.html")
        _string_to_file("<b>{{ text }}</b>", template_out)

        templater = SimpleTemplate(out=project_dir, template_dir=template_dir)
        templater.text = "Hello World"
        templater.build_pages(["index.html"])
        result = _file_to_string(templater.documents["index.html"].path)
        assert result == "<b>Hello World</b>"


def test_templating_with_multiple_variables(SimpleTemplate):
    with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as template_dir:
        template_out = os.path.join(template_dir, "contact.html")
        _string_to_file("<b>{{ text }}</b><p>{{ url }}</p>", template_out)

        templater = SimpleTemplate(out=project_dir, template_dir=template_dir)
        templater.text = "Hello you"
        templater.url = "https://www.google.com"
        templater.build_pages(["contact.html"])
        result = _file_to_string(templater.documents["contact.html"].path)
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
        
        index_result = _file_to_string(templater.documents["index.html"].path)
        assert index_result == "<b>Hello World</b>"

        contact_result = _file_to_string(templater.documents["contact.html"].path)
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


def test_css_font_weight(var_ttfont):
    var_ttfont["OS/2"].usWeightClass = 400
    assert css_font_weight(var_ttfont) == 400

    var_ttfont["OS/2"].usWeightClass = 250
    assert css_font_weight(var_ttfont) == 100


def _select_class(string, classes):
    return next((s for s in classes if string in s.selector), None)


def _select_font_face(string, classes):
    return next((s for s in classes if string in s.font_family), None)


def test_font_classes_from_static(static_ttfonts):
    css_classes = css_font_classes(static_ttfonts)
    assert len(css_classes) == len(static_ttfonts)

    regular = _select_class("Maven-Pro-Regular", css_classes)
    black = _select_class("Maven-Pro-Black", css_classes)

    assert regular.render() == (
        "Maven-Pro-Regular { font-family: Maven-Pro-Regular; font-weight: 400; "
        "font-style: normal; font-stretch: 100%; }"
    )
    assert black.render() == (
        "Maven-Pro-Black { font-family: Maven-Pro-Black; font-weight: 900; "
        "font-style: normal; font-stretch: 100%; }"
    )


def test_font_classes_from_vf(var_ttfont):
    css_classes = css_font_classes([var_ttfont])
    assert len(css_classes) == len(var_ttfont['fvar'].instances)

    semiexpanded_medium = _select_class("Inconsolata-SemiExpanded-Medium", css_classes)
    assert semiexpanded_medium.render() == (
        "Inconsolata-SemiExpanded-Medium { font-family: Inconsolata-Regular; "
        "font-weight: 500; font-style: normal; font-stretch: 112%; }"
    )
    extracondensed_black = _select_class("Inconsolata-ExtraCondensed-Black", css_classes)
    assert extracondensed_black.render() == (
        "Inconsolata-ExtraCondensed-Black { font-family: Inconsolata-Regular; "
        "font-weight: 900; font-style: normal; font-stretch: 62%; }"
    )


def test_font_faces_from_static(static_ttfonts):
    font_faces = css_font_faces(static_ttfonts)
    assert len(font_faces) == len(static_ttfonts)

    medium = _select_font_face("Maven-Pro-Medium", font_faces)
    assert medium.render() == (
        "@font-face { src: url(data/test/mavenpro/MavenPro-Medium.ttf); "
        "font-family: Maven-Pro-Medium; font-weight: 500; font-stretch: 100%; "
        "font-style: normal; }"
    )

    bold = _select_font_face("Maven-Pro-Bold", font_faces)
    assert bold.render() == (
        "@font-face { src: url(data/test/mavenpro/MavenPro-Bold.ttf); "
        "font-family: Maven-Pro-Bold; font-weight: 700; font-stretch: 100%; "
        "font-style: normal; }"
    )


def test_font_faces_from_vf(var_ttfont):
    font_faces = css_font_faces([var_ttfont])
    font_faces[0].render == (
        "@font-face { src: url(data/test/Inconsolata[wdth,wght].ttf); "
        "font-family: Inconsolata; font-weight: 200 900; font-stretch: 50% 200%; "
        "font-style: normal; }"
    )


def _font_faces_and_font_classes_linked(font_faces, css_classes):
    # font classes and font-faces are linked via the font-family property
    font_face_names = set(f.font_family for f in font_faces)
    css_class_names = set(c.font_family for c in css_classes)
    assert font_face_names == css_class_names


def test_font_faces_match_font_classes_static(static_ttfonts):
    font_faces = css_font_faces(static_ttfonts)
    css_classes = css_font_classes(static_ttfonts)
    _font_faces_and_font_classes_linked(font_faces, css_classes)


def test_font_faces_match_font_classes_vf(var_ttfont):
    font_faces = css_font_faces([var_ttfont])
    css_classes = css_font_classes([var_ttfont])
    _font_faces_and_font_classes_linked(font_faces, css_classes)


def _test_waterfall(waterfall_result, html):
    # Check pangram strings have been added.
    assert "quick wafting zephyrs vex bold jim." in waterfall_result

    font_faces = re.findall(r"@font-face", waterfall_result)
    assert len(font_faces) == len(html.css_font_faces)

    font_styles = re.findall(r".[A-z-]{1,50} \{ font-family", waterfall_result)
    assert len(font_styles) == len(html.css_font_classes)


def _test_text(text_result, html):
    assert "Resolution" in text_result


def test_HtmlProof_with_static_fonts(static_fonts):
    with tempfile.TemporaryDirectory() as project_dir:
        html = HtmlProof(
            out=project_dir,
            fonts=static_fonts
        )
        # Each font must have an @font-face and font_class
        assert len(html.fonts) == len(html.css_font_faces) == len(html.css_font_classes)
        html.build_pages(["waterfall.html", "text.html"])

        waterfall_result = _file_to_string(html.documents["waterfall.html"].path)
        _test_waterfall(waterfall_result, html)

        text_result = _file_to_string(html.documents["text.html"].path)
        _test_text(text_result, html)


def test_HtmlProof_with_vf(var_font):
    with tempfile.TemporaryDirectory() as project_dir:
        html = HtmlProof(
            out=project_dir,
            fonts=[var_font]
        )
        assert len(html.fonts) == len(html.css_font_faces)
        # VFs can contain multiple styles in a single font
        assert len(html.css_font_faces) < len(html.css_font_classes)
        html.build_pages(["waterfall.html"])

        waterfall_result = _file_to_string(html.documents["waterfall.html"].path)
        _test_waterfall(waterfall_result, html)


def test_HtmlDiff_match_css_classes_different_families(static_fonts, var_font):
    with tempfile.TemporaryDirectory() as project_dir:
        with pytest.raises(ValueError, match="No matching fonts found"):
            html = HtmlDiff(static_fonts, [var_font], project_dir)


def _check_css_classes_match(classes_before, classes_after):
    # Check css classes have same order
    before_properties = [
        (s.font_weight, s.font_stretch, s.font_style)
        for s in classes_before
    ]
    after_properties = [
        (s.font_weight, s.font_stretch, s.font_style)
        for s in classes_after
    ]
    assert before_properties == after_properties


def test_HtmlDiff_match_css_classes_different_styles(static_ttfonts):
    from gftools.fix import update_nametable
    family_before = static_ttfonts
    family_after = deepcopy(static_ttfonts)

    reg_after = next((f for f in family_after if "Regular.ttf" in f.reader.file.name), None)
    update_nametable(reg_after, style_name="Foobar")

    bold_after = next((f for f in family_after if "Bold.ttf" in f.reader.file.name), None)
    update_nametable(bold_after, style_name="Foobar2")

    with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as mod_fonts:
        # save modified ttfonts to a tempdir and load them
        [f.save(os.path.join(mod_fonts, os.path.basename(f.reader.file.name))) for f in family_after]
        family_after = glob(os.path.join(mod_fonts, "*.ttf"))
        family_before = [f.reader.file.name for f in family_before]

        html = HtmlDiff(family_before, family_after, project_dir)
        # Check css classes do not contain
        for subfamily in ("Regular", "Bold", "Foobar", "Foobar2"):
            assert not any(subfamily in c._style for c in html.css_font_classes_before)
            assert not any(subfamily in c._style for c in html.css_font_classes_after)

        # Check css classes contain
        for subfamily in ("Medium", "Black"):
            assert any(subfamily in c._style for c in html.css_font_classes_before)
            assert any(subfamily in c._style for c in html.css_font_classes_after)

        _check_css_classes_match(html.css_font_classes_before, html.css_font_classes_after)


def test_HtmlDiff_match_css_classes_static_vs_vf(static_fonts, var_font2):
    # MavenPro VF has an fvar instance for each static font.
    # Every font in the static family should match an instance in Maven Pro VF
    with tempfile.TemporaryDirectory() as project_dir:
        html = HtmlDiff(static_fonts, [var_font2], project_dir)
        assert len(html.css_font_classes_before) == len(html.css_font_classes_after)
        _check_css_classes_match(html.css_font_classes_before, html.css_font_classes_after)

