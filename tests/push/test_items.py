import pytest
import os
from pathlib import Path

from gftools.push.items import Family, FamilyMeta, Designer, Axis, AxisFallback
from pkg_resources import resource_filename
import json


CWD = os.path.dirname(__file__)
TEST_DIR = os.path.join(CWD, "..", "..", "data", "test", "gf_fonts")
SERVER_DIR = os.path.join(CWD, "..", "..", "data", "test", "servers")
TEST_FAMILY_DIR = Path(TEST_DIR) / "ofl" / "mavenpro"
DESIGNER_DIR = Path(TEST_DIR) / "joeprince"
AXES_DIR = Path(resource_filename("axisregistry", "data"))
FAMILY_JSON = json.load(open(os.path.join(SERVER_DIR, "family.json"), encoding="utf8"))
FONTS_JSON = json.load(open(os.path.join(SERVER_DIR, "fonts.json"), encoding="utf8"))


@pytest.mark.parametrize(
    "type_, fp, gf_data, res",
    [
        (
            Family,
            TEST_FAMILY_DIR,
            next(
                f
                for f in FONTS_JSON["familyMetadataList"]
                if f["family"] == "Maven Pro"
            ),
            Family(
                name="Maven Pro",
                version="Version 2.102",
            ),
        ),
        (
            FamilyMeta,
            TEST_FAMILY_DIR,
            FAMILY_JSON,
            FamilyMeta(
                name="Maven Pro",
                designer=["Joe Prince"],
                license="ofl",
                category="SANS_SERIF",
                subsets=["latin", "latin-ext", "vietnamese"],
                stroke="SANS_SERIF",
                classifications=[],
                description="Maven Pro is a sans-serif typeface with unique "
                "curvature and flowing rhythm. Its forms make it very "
                "distinguishable and legible when in context. It blends "
                "styles of many great typefaces and is suitable for any "
                "design medium. Maven Pro’s modern design is great for "
                "the web and fits in any environment. Updated in "
                'January 2019 with a Variable Font "Weight" axis. The '
                "Maven Pro project was initiated by Joe Price, a type "
                "designer based in the USA. To contribute, see "
                "github.com/googlefonts/mavenproFont",
                primary_script=None,
                article=None,
                minisite_url=None,
            ),
        ),
        (
            Designer,
            DESIGNER_DIR,
            FAMILY_JSON["designers"][0],
            Designer(name="Joe Prince", bio=None),
        ),
        (
            Axis,
            AXES_DIR / "weight.textproto",
            next(a for a in FONTS_JSON["axisRegistry"] if a["tag"] == "wght"),
            Axis(
                tag="wght",
                display_name="Weight",
                min_value=1.0,
                default_value=400.0,
                max_value=1000.0,
                precision=0,
                fallback=[
                    AxisFallback(name="Thin", value=100.0),
                    AxisFallback(name="ExtraLight", value=200.0),
                    AxisFallback(name="Light", value=300.0),
                    AxisFallback(name="Regular", value=400.0),
                    AxisFallback(name="Medium", value=500.0),
                    AxisFallback(name="SemiBold", value=600.0),
                    AxisFallback(name="Bold", value=700.0),
                    AxisFallback(name="ExtraBold", value=800.0),
                    AxisFallback(name="Black", value=900.0),
                ],
                fallback_only=False,
                description="Adjust the style from lighter to bolder in typographic color, by varying stroke weights, spacing and kerning, and other aspects of the type. This typically changes overall width, and so may be used in conjunction with Width and Grade axes.",
            ),
        ),
    ],
)
def test_item_from_fp_and_gf_data(type_, fp, gf_data, res):
    assert type_.from_fp(fp) == type_.from_gf_json(gf_data) == res
