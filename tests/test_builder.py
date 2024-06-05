import tempfile
import pytest
import shutil
import os
import subprocess

from gftools.builder import GFBuilder


CWD = os.path.dirname(__file__)
TEST_DIR = os.path.join(CWD, "..", "data", "test", "builder")


@pytest.mark.parametrize(
    "fp,font_paths",
    [
        # Tests our basic Glyphs setup. By default, otf, ttf, variable and
        # webfonts are generated.
        (
            os.path.join(TEST_DIR, "basic_family_glyphs_0"),
            [
                os.path.join("variable", "TestFamily[wght].ttf"),
                os.path.join("ttf", "TestFamily-Black.ttf"),
                os.path.join("ttf", "TestFamily-Regular.ttf"),
                os.path.join("ttf", "TestFamily-Thin.ttf"),
                os.path.join("otf", "TestFamily-Black.otf"),
                os.path.join("otf", "TestFamily-Regular.otf"),
                os.path.join("otf", "TestFamily-Thin.otf"),
                os.path.join("webfonts", "TestFamily[wght].woff2"),
                os.path.join("webfonts", "TestFamily-Black.woff2"),
                os.path.join("webfonts", "TestFamily-Regular.woff2"),
                os.path.join("webfonts", "TestFamily-Thin.woff2"),
            ],
        ),
        # Family consists of ufos which are not MM compatible. Tests
        # https://github.com/googlefonts/gftools/pull/669
        (
            os.path.join(TEST_DIR, "check_compatibility_ufo_1"),
            [
                os.path.join("ttf", "TestFamily-Black.ttf"),
                os.path.join("ttf", "TestFamily-Thin.ttf"),
                os.path.join("otf", "TestFamily-Black.otf"),
                os.path.join("otf", "TestFamily-Thin.otf"),
                os.path.join("webfonts", "TestFamily-Black.woff2"),
                os.path.join("webfonts", "TestFamily-Thin.woff2"),
            ],
        ),
        # Testing a custom recipe provider
        (
            os.path.join(TEST_DIR, "recipeprovider_noto"),
            [
                os.path.join("TestFamily", "unhinted", "ttf", "TestFamily-Regular.ttf"),
                os.path.join(
                    "TestFamily", "googlefonts", "ttf", "TestFamily-Black.ttf"
                ),
            ],
        ),
    ],
)
def test_builder(fp, font_paths):
    with tempfile.TemporaryDirectory() as tmp_dir:
        src_dir = os.path.join(tmp_dir, "sources")
        font_dir = os.path.join(tmp_dir, "fonts")
        shutil.copytree(fp, src_dir)
        build_path = os.path.join(src_dir, "config.yaml")
        subprocess.run(["gftools", "builder", build_path])
        for font_path in font_paths:
            font_path = os.path.join(font_dir, font_path)
            assert os.path.exists(font_path), f"{font_path} is missing"


@pytest.mark.parametrize(
    "fp,font_paths",
    [
        (
            # Tests our basic Glyphs setup. By default, otf, ttf, variable and
            # webfonts are generated.
            os.path.join(TEST_DIR, "basic_family_glyphs_glyphData"),
            [
                os.path.join("variable", "TestFamily[wght].ttf"),
                os.path.join("ttf", "TestFamily-Black.ttf"),
                os.path.join("ttf", "TestFamily-Regular.ttf"),
                os.path.join("ttf", "TestFamily-Thin.ttf"),
                os.path.join("otf", "TestFamily-Black.otf"),
                os.path.join("otf", "TestFamily-Regular.otf"),
                os.path.join("otf", "TestFamily-Thin.otf"),
            ],
        ),
        # Testing a custom recipe provider
        (
            os.path.join(TEST_DIR, "recipeprovider_noto_glyphData"),
            [
                os.path.join(
                    "TestFamily", "unhinted", "variable-ttf", "TestFamily[wght].ttf"
                ),
                os.path.join("TestFamily", "unhinted", "ttf", "TestFamily-Black.ttf"),
                os.path.join("TestFamily", "unhinted", "ttf", "TestFamily-Regular.ttf"),
                os.path.join("TestFamily", "unhinted", "ttf", "TestFamily-Thin.ttf"),
                os.path.join("TestFamily", "unhinted", "otf", "TestFamily-Black.otf"),
                os.path.join("TestFamily", "unhinted", "otf", "TestFamily-Regular.otf"),
                os.path.join("TestFamily", "unhinted", "otf", "TestFamily-Thin.otf"),
                os.path.join("TestFamily", "hinted", "ttf", "TestFamily-Black.ttf"),
                os.path.join("TestFamily", "hinted", "ttf", "TestFamily-Regular.ttf"),
                os.path.join("TestFamily", "hinted", "ttf", "TestFamily-Thin.ttf"),
                os.path.join(
                    "TestFamily", "googlefonts", "variable-ttf", "TestFamily[wght].ttf"
                ),
            ],
        ),
    ],
)
def test_builder_glyphData(fp, font_paths):
    from fontTools.ttLib import TTFont

    with tempfile.TemporaryDirectory() as tmp_dir:
        src_dir = os.path.join(tmp_dir, "sources")
        font_dir = os.path.join(tmp_dir, "fonts")
        shutil.copytree(fp, src_dir)
        build_path = os.path.join(src_dir, "config.yaml")
        subprocess.run(["gftools", "builder", build_path])
        for font_path in font_paths:
            font_path = os.path.join(font_dir, font_path)
            assert os.path.exists(font_path), f"{font_path} is missing"
            ttFont = TTFont(font_path)
            assert "GDEF" in ttFont
            GDEF = ttFont["GDEF"].table
            assert GDEF.GlyphClassDef
            assert "foo" in GDEF.GlyphClassDef.classDefs
            assert GDEF.GlyphClassDef.classDefs["foo"] == 3


def test_bad_configs():
    config = {"Sources": ["foo.glyphs"]}
    with pytest.raises(ValueError):
        GFBuilder(config)
