import tempfile
import pytest
import shutil
import os
import subprocess
from pathlib import Path

from gftools.builder import GFBuilder
from gftools.builder.fontc import FontcArgs


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
        # Testing VF split
        (
            os.path.join(TEST_DIR, "split_italic"),
            [
                os.path.join("variable", "TestFamily[wght].ttf"),
                os.path.join("variable", "TestFamily-Italic[wght].ttf"),
            ],
        ),
        # Statics declared with the 'instances' key are cut from the
        # variable font instead of being built from the sources. The
        # 'out' key places the static relative to the repo root.
        (
            os.path.join(TEST_DIR, "gen_static_instances"),
            [
                os.path.join("variable", "TestFamily[wght].ttf"),
                os.path.join("custom", "TestFamily-Regular.ttf"),
                os.path.join("ttf", "TestFamily-Black.ttf"),
                os.path.join("webfonts", "TestFamily-Regular.woff2"),
                os.path.join("webfonts", "TestFamily-Black.woff2"),
            ],
        ),
        (
            # Test source switching and glyphs2ds being able to deal with
            # sources to be generated. The source file contains a single style,
            # which would usually prompt fontmake to special case the output
            # Designspace file name. This tests that gftools retains control
            # over the output file name by testing that the pipeline finishes.
            os.path.join(TEST_DIR, "switch_sources"),
            [
                "test_family.ttf",
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


def test_source_dir_with_space(tmp_path):
    # Instance UFOs are written next to the source, so a space in the source's
    # directory must survive fontmake's --instance-dir argument.
    src_dir = tmp_path / "Source Files"
    src_dir.mkdir()
    shutil.copyfile(
        os.path.join(TEST_DIR, "basic_family_glyphs_0", "TestFamily.glyphs"),
        src_dir / "TestFamily.glyphs",
    )
    config = tmp_path / "config.yaml"
    config.write_text(
        "sources:\n"
        "  - Source Files/TestFamily.glyphs\n"
        "outputDir: fonts\n"
        "buildVariable: false\n"
        "buildOTF: false\n"
        "buildWebfont: false\n"
        "autohintTTF: false\n"
    )
    subprocess.run(["gftools", "builder", str(config)], check=True)
    for style in ["Black", "Regular", "Thin"]:
        font_path = tmp_path / "fonts" / "ttf" / f"TestFamily-{style}.ttf"
        assert font_path.exists(), f"{font_path} is missing"


def test_bad_configs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = {"Sources": ["foo.glyphs"]}
    with pytest.raises(ValueError):
        GFBuilder(config)


def test_instances_vf_selection(tmp_path, monkeypatch):
    # Instances are cut from the roman VF by default, from the italic VF
    # if their style name contains Italic, and from the VF named by the
    # 'in' key if given.
    shutil.copyfile(
        os.path.join(TEST_DIR, "split_italic", "TestFamily.glyphs"),
        tmp_path / "TestFamily.glyphs",
    )
    monkeypatch.chdir(tmp_path)
    config = {
        "sources": ["TestFamily.glyphs"],
        "buildWebfont": False,
        "instances": [
            {"familyName": "Test Family", "styleName": "Regular"},
            {"familyName": "Test Family", "styleName": "Italic"},
            {
                "familyName": "Test Family",
                "styleName": "Bold Italic",
                "coordinates": {"wght": 700},
                "in": "TestFamily[wght].ttf",
            },
        ],
    }
    recipe = GFBuilder(config).recipe
    sources = {
        os.path.basename(target): os.path.basename(steps[0]["source"])
        for target, steps in recipe.items()
        if target.endswith(".ttf") and "variable" not in target
    }
    assert sources == {
        "TestFamily-Regular.ttf": "TestFamily[wght].ttf",
        "TestFamily-Italic.ttf": "TestFamily-Italic[wght].ttf",
        "TestFamily-BoldItalic.ttf": "TestFamily[wght].ttf",
    }

    config["instances"] = [
        {"familyName": "Test Family", "styleName": "Regular", "in": "Missing.ttf"}
    ]
    with pytest.raises(ValueError, match="no variable font target named"):
        GFBuilder(config)


def test_clean_removes_instance_ufos_next_to_source(tmp_path, monkeypatch):
    # Instance UFOs are written next to the source, not into the config's
    # directory, so cleanUp must remove them there; but not while another
    # builder's .ninja file says it may still be using them.
    src_dir = tmp_path / "Source"
    src_dir.mkdir()
    shutil.copyfile(
        os.path.join(TEST_DIR, "basic_family_glyphs_0", "TestFamily.glyphs"),
        src_dir / "TestFamily.glyphs",
    )
    monkeypatch.chdir(tmp_path)
    config = {
        "sources": ["Source/TestFamily.glyphs"],
        "buildVariable": False,
        "buildWebfont": False,
        "cleanUp": True,
    }
    builder = GFBuilder(config)
    builder.config_to_objects()
    builder.build_graph()
    builder.walk_graph()
    instance_dir = src_dir / "instance_ufos"
    instance_dir.mkdir()

    other_ninja = tmp_path / "build-other.ninja"
    other_ninja.touch()
    builder.clean()
    assert instance_dir.exists()

    other_ninja.unlink()
    builder.clean()
    assert not instance_dir.exists()


def test_ufoz_is_a_ufo_source(tmp_path):
    # A ".ufoz" (zipped UFO) must be recognised as a buildable UFO source; before
    # this it was not is_font_source and File.family_name crashed.
    import ufoLib2

    from gftools.builder.file import File

    ufoz = tmp_path / "MyFont.ufoz"
    font = ufoLib2.Font()
    font.info.familyName = "My Font"
    font.newGlyph("a")
    font.save(ufoz, structure="zip")

    f = File(str(ufoz))
    assert f.is_ufo
    assert f.is_font_source
    assert not f.is_variable  # a single zipped UFO is a static master
    assert f.family_name == "My Font"


def test_glyphs_without_custom_parameters_is_static(tmp_path):
    # A single-master .glyphs file need not have a font-level customParameters list;
    # is_variable must not require one.
    from gftools.builder.file import File

    glyphs = tmp_path / "MyFont.glyphs"
    glyphs.write_text(
        '{\n.formatVersion = 3;\nfamilyName = "My Font";\n'
        "fontMaster = (\n{\nid = m01;\nname = Regular;\n}\n);\n"
        "glyphs = (\n);\nunitsPerEm = 1000;\nversionMajor = 1;\nversionMinor = 0;\n}\n"
    )
    assert not File(str(glyphs)).is_variable


def test_glyphs2_without_axes_parameter(tmp_path, monkeypatch):
    # A Glyphs 2 file need not have an "Axes" custom parameter; glyphsLib then
    # gives it the default Weight and Width axes, and the VF is named after those.
    glyphs = tmp_path / "MyFont.glyphs"
    glyphs.write_text(
        '{\nfamilyName = "My Font";\n'
        "fontMaster = (\n{\nid = m01;\nweightValue = 100;\n},\n"
        "{\nid = m02;\nweightValue = 900;\n}\n);\n"
        "glyphs = (\n);\nunitsPerEm = 1000;\nversionMajor = 1;\nversionMinor = 0;\n}\n"
    )
    monkeypatch.chdir(tmp_path)
    config = {"sources": ["MyFont.glyphs"], "buildStatic": False, "buildWebfont": False}
    recipe = GFBuilder(config).recipe
    vfs = [os.path.basename(target) for target in recipe if "variable" in target]
    assert vfs == ["MyFont[wdth,wght].ttf"]


def test_production_names_key():
    # productionNames (default true) replaced the negative noProductionNames key
    import strictyaml

    from gftools.builder.schema import GOOGLEFONTS_SCHEMA

    strictyaml.load(
        "sources:\n  - A.glyphs\nproductionNames: false\n", GOOGLEFONTS_SCHEMA
    )
    with pytest.raises(strictyaml.YAMLValidationError):
        strictyaml.load(
            "sources:\n  - A.glyphs\nnoProductionNames: true\n", GOOGLEFONTS_SCHEMA
        )


def _static_recipe(
    tmp_path, monkeypatch, source, text, fontc=True, strict=False, **config
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / source).write_text(text)
    config = {
        "sources": [source],
        "buildVariable": False,
        "buildOTF": False,
        "buildWebfont": False,
        "buildSmallCap": False,
        **config,
    }
    fontc_args = FontcArgs(None)
    fontc_args.strict = strict
    if fontc:
        # as --experimental-fontc does, without registering the path globally
        fontc_args.fontc_bin_path = Path("fontc")
    recipe = GFBuilder(config, fontc_args=fontc_args).recipe
    return {
        os.path.basename(target): steps[1:]
        for target, steps in recipe.items()
        if target.endswith(".ttf")
    }


def _how_instances_are_built(recipe):
    """For each static target, how its instance is taken from the source:
    "--export <name>" when fontc builds it, or "instantiateUfo" when fontmake
    cuts it first."""
    built = {}
    for target, steps in recipe.items():
        build = next(s for s in steps if s["operation"] == "buildTTF")
        cut = any(s["operation"] == "instantiateUfo" for s in steps)
        assert cut != ("instance" in build), steps
        built[target] = "instantiateUfo" if cut else f"--export {build['instance']}"
    return built


def test_fontc_builds_static_instances_with_export(tmp_path, monkeypatch):
    text = open(
        os.path.join(TEST_DIR, "basic_family_glyphs_0", "TestFamily.glyphs")
    ).read()
    recipe = _static_recipe(
        tmp_path,
        monkeypatch,
        "TestFamily.glyphs",
        text,
        glyphData=["GlyphData.xml"],
    )
    # fontc doesn't interpolate, so fontmake cuts Regular, between the masters
    assert _how_instances_are_built(recipe) == {
        "TestFamily-Thin.ttf": "--export Test Family Thin",
        "TestFamily-Regular.ttf": "instantiateUfo",
        "TestFamily-Black.ttf": "--export Test Family Black",
    }
    assert "--glyph-data GlyphData.xml" in recipe["TestFamily-Thin.ttf"][0]["args"]
    # unless strict, so that fontc fails on it
    recipe = _static_recipe(
        tmp_path, monkeypatch, "TestFamily.glyphs", text, strict=True
    )
    assert _how_instances_are_built(recipe)["TestFamily-Regular.ttf"] == (
        "--export Test Family Regular"
    )
    # without fontc, fontmake cuts the instances as before
    recipe = _static_recipe(
        tmp_path, monkeypatch, "TestFamily.glyphs", text, fontc=False
    )
    assert set(_how_instances_are_built(recipe).values()) == {"instantiateUfo"}


@pytest.mark.parametrize(
    "black_glyphs, black",
    [
        (["a", "b"], "--export My Font Black"),
        # fontc doesn't interpolate the glyphs the instance's source lacks
        (["a"], "instantiateUfo"),
    ],
)
def test_fontc_builds_designspace_instances_on_a_source(
    tmp_path, monkeypatch, black_glyphs, black
):
    import ufoLib2

    for name, glyphs in [("Thin", ["a", "b"]), ("Black", black_glyphs)]:
        font = ufoLib2.Font()
        for glyph in glyphs:
            font.newGlyph(glyph)
        font.save(tmp_path / f"{name}.ufo", overwrite=True)
    sources = "".join(
        f'<source filename="{name}.ufo" familyname="My Font" stylename="{name}">'
        f'<location><dimension name="Weight" xvalue="{weight}"/></location></source>'
        for name, weight in [("Thin", 100), ("Black", 900)]
    )
    instances = "".join(
        f'<instance filename="instance_ufos/MyFont-{name}.ufo" familyname="My Font" '
        f'stylename="{name}"><location><dimension name="Weight" xvalue="{weight}"/>'
        "</location></instance>"
        for name, weight in [("Thin", 100), ("Regular", 400), ("Black", 900)]
    )
    text = f"""<?xml version='1.0' encoding='UTF-8'?>
<designspace format="5.0">
  <axes><axis tag="wght" name="Weight" minimum="100" maximum="900" default="100"/></axes>
  <sources>{sources}</sources>
  <instances>{instances}</instances>
</designspace>
"""
    recipe = _static_recipe(tmp_path, monkeypatch, "MyFont.designspace", text)
    assert _how_instances_are_built(recipe) == {
        "MyFont-Thin.ttf": "--export My Font Thin",
        "MyFont-Regular.ttf": "instantiateUfo",
        "MyFont-Black.ttf": black,
    }


def test_fontc_export_name_is_one_quoted_argument():
    from gftools.builder.operations.fontc.fontcBuildTTF import FontcBuildTTF
    from gftools.utils import shell_quote

    op = FontcBuildTTF(
        original={"args": "--no-production-names", "instance": "My Font's $Bold"}
    )
    variables = op.variables
    assert "instance" not in variables
    assert variables["args"] == "--no-production-names"
    # quoted as one argument for the platform's shell, with the $ doubled for
    # ninja, which undoes it before the shell sees the command
    assert variables["instance_args"] == "--export " + shell_quote("My Font's $$Bold")
