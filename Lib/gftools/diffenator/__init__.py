"""
Diffenator is primarily a visual differ. Its main job is to stop users reporting visual issues to google/fonts.

What should be checked:

- Essential tables e.g OS/2, hhea attribs (Simon seemed keen on this so discuss implementation of this in the context of what I've found here)
- Clusters (glyphs which form a hb cluster), missing, new modified (GSUB)
- Kerning (Gpos)
- Marks (Gpos)


Output:
- A single html page. No images, just pure html and js.
"""
from difflib import HtmlDiff
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from ufo2ft.postProcessor import PostProcessor
import freetype as ft
from dataclasses import dataclass
from gftools.diffenator.glyphs import GlyphCombinator
import numpy as np
from collections import defaultdict
from gftools.diffenator.scale import scale_font
from jinja2 import Environment, FileSystemLoader, pass_environment
from gftools import html
import os
import shutil
from gftools.diffenator import jfont
from pkg_resources import resource_filename
import logging
import pprint


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

FT_BITS = ft.raw.FT_LOAD_NO_HINTING | ft.raw.FT_LOAD_RENDER


# todo add more
OPTIONAL_FEATURES = set(["case, ""dnom", "frac", "numr", "ordn", "zero", "locl", "ccmp", "liga"])


class Renderable:
    @pass_environment
    def render(self, jinja):
        classname = self.__class__.__name__
        template = jinja.get_template(os.path.join("diffenator", classname+".partial.html"))
        return template.render(self.__dict__)


# Use dataclass instead of namedtuple. Override __eq__ method.
@dataclass
class Buffer(Renderable):
    # A buffer should in theory cover all GSUB lookup types
    name: str
    characters: str  # characters used to assemble buffer e.g कि == [क] + [ ि]
    indexes: list[int]  # glyph indexes
    features: tuple[str] = None
    script: tuple[str] = None
    lang: tuple[str] = None
    contextual: bool = False

    def __eq__(self, other):
        return (self.characters, self.features, self.script, self.lang,) == (
            other.characters,
            other.features,
            other.script,
            other.lang,
        )

    def __hash__(self):
        return hash((self.characters, self.features, self.script, self.lang))

    def to_image(self, font):
        font.ftFont.load_glyph(self.indexes[0], FT_BITS)
        return font.ftFont.glyph.bitmap.buffer


@dataclass
class BufferDiff(Renderable):
    buffer_a: Buffer
    buffer_b: Buffer
    diff: float


@dataclass
class Kern:
    # Covers GPOS lookup types:
    # 1: SinglePos (just leave right as None)
    # 2: PairPos
    # TODO what about type 3? we may have to borrow Gulzar or a cursive attachment font for this
    left: tuple[Buffer]
    right: tuple[Buffer]
    value_x: int
    value_y: int

    def __eq__(self, other):
        return (self.left, self.right) == (other.left, other.right)


@dataclass
class Mark:
    # Covers GPOS lookup types
    # 4: Mark to Base
    # 5: Mark to Lig??? (Don't think so yet)
    # 6: Mark to Mark (first mark can just be a base)
    base: tuple[Buffer]
    mark: tuple[Buffer]
    base_x: int
    base_y: int
    mark_x: int
    mark_y: int

    def __eq__(self, other):
        return (self.base, self.mark) == (other.base, other.mark)

    def __hash__(self):
        return hash((self.base, self.mark))


class DFont:
    def __init__(
        self, path: str, font_size: int = 1000, lazy=False
    ):  # <- use types!
        self.path = path
        self.ttFont: TTFont = TTFont(self.path, recalcTimestamp=False)
        self.ftFont: ft.Face = ft.Face(self.path)
        self.jFont = jfont.TTJ(self.ttFont)
        self.glyph_combinator = GlyphCombinator(self.ttFont)

        self.font_size: int = font_size
        self.set_font_size(self.font_size)
        # use sets since we get boolean operations and users don't care about order
        self.glyphs = {}
        self.kerns: set[Kern] = set()
        self.marks: set[Mark] = set()
        # TODO what about the easy tables OS/2, hhea etc?
        self.build()
    
    def is_variable(self):
        return "fvar" in self.ttFont

    def set_font_size(self, size: int):
        self.font_size = size
        self.ftFont.set_char_size(self.font_size)

    def set_variations(self, coords: dict[str, float]):
        # freetype-py's api uses a tuple/list
        ft_coords = [
            a.defaultValue if a.axisTag not in coords else coords[a.axisTag]
            for a in self.ttFont["fvar"].axes
        ]
        self.ftFont.set_var_design_coords(ft_coords)
        self.variation = coords
        self.ttFont = instantiateVariableFont(self.ttFont, coords)

    def set_variations_from_font(self, font: any):
        # Parse static font into a variations dict
        # TODO improve this
        coords = {"wght": font.ttFont["OS/2"].usWeightClass, "wdth": font.ttFont["OS/2"].usWidthClass}
        self.set_variations(coords)

    def set_glyph_names_from_font(self, font: any):
        glyphs_rev = {v: k for k, v in self.glyphs.items()}
        other_glyphs_rev = {v: k for k, v in font.glyphs.items()}
        shared = set(glyphs_rev) & set(other_glyphs_rev)
        mapping = {glyphs_rev[i]: other_glyphs_rev[i] for i in shared}
        logger.debug(f"{self} renaming glyphs {pprint.pformat(mapping)}")
        PostProcessor.rename_glyphs(self.ttFont, mapping)
        glyphs = self.ttFont.getGlyphNames()

    # populate glyphs, kerns, marks etc
    def build(self):
        self.build_glyphs()

    def build_glyphs(self):
        logger.info(f"{self}: building glyphs")
        optional_features = OPTIONAL_FEATURES & set(self.glyph_combinator.ff.features.keys())
        for script, langs in self.glyph_combinator.languageSystems.items():
            for lang in langs:
                for feat in ["", "case"]:
                    self.glyph_combinator.get_combinations({"liga": True, "kern": True, feat: True}, script, lang)
                    for name, chars in self.glyph_combinator.glyphs.items():
                        gids = [self.glyph_combinator.reverse_gids[n] for n in name.split("-")]
                        if name in self.glyphs:
                            continue
                        buffer = Buffer(
                            name=name,
                            characters=chars,
                            indexes=gids,
                            features=feat, # fix this
                            script=script,
                            lang=lang,
                            contextual=True if "-" in name else False,

                        )
                        self.glyphs[name] = buffer
    
    def __repr__(self):
        return f"<DFont: {self.path}>"


# Key feature of diffenator is to compare a static font against a VF instance.
# We need to retain this
def match_fonts(old_font: DFont, new_font: DFont, variations: dict = None):
    logger.info(f"Matching {os.path.basename(old_font.path)} to {os.path.basename(new_font.path)}")
    if old_font.is_variable() and new_font.is_variable():
        # todo allow user to specify coords
        return old_font, new_font
    elif not old_font.is_variable() and new_font.is_variable():
        new_font.set_variations_from_font(old_font)
    elif old_font.is_variable() and not new_font.is_variable():
        old_font.set_variations_from_font(new_font)
    return old_font, new_font


class DiffFonts:
    def __init__(
        self, old_font: DFont, new_font: DFont, scale_upm=True, rename_glyphs=True
    ):
        self.diff = defaultdict(dict)
        # self.diff = {
        #     "OS/2": {"Modified": [...]},
        #     ...
        #     "glyphs": {"New": [GlyphCluster]}
        # }
        self.old_font = old_font
        self.new_font = new_font
        # diffing fonts with different upms was in V1 so we should retain it.
        # previous implementation was rather messy. It is much easier to scale
        # the whole font
        if scale_upm:
            ratio = new_font.ttFont["head"].unitsPerEm / old_font.ttFont["head"].unitsPerEm
            if ratio != 1.0:
                self.old_font.ttFont = scale_font(self.old_font.ttFont, ratio)
        
        # renaming was another key feature we need to retain
        if rename_glyphs:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".ttf") as modded_old_font:
                # see https://github.com/googlefonts/ufo2ft/issues/485 for this mess
                self.old_font.ttFont.save(modded_old_font.name)
                self.old_font.ttFont = TTFont(modded_old_font.name)
                self.old_font.set_glyph_names_from_font(self.new_font)
                self.old_font.ttFont.save(modded_old_font.name)
                self.old_font = DFont(modded_old_font.name)

        self.tables = jfont.Diff(self.old_font.jFont, self.new_font.jFont)
        # todo this seems bolted on
        old_fea = self.old_font.glyph_combinator.ff.asFea()
        new_fea = self.new_font.glyph_combinator.ff.asFea()
        if old_fea != new_fea:
            self.features = HtmlDiff(wrapcolumn=80).make_file(
                old_fea.split("\n"),
                new_fea.split("\n"),
            )


    def build(self):
        # TODO could make this dynamic use something like dir() to get funcs then call em
        modified_glyphs = self.modified_glyphs()
        if modified_glyphs:
            self.diff["glyphs"]["modified"] = modified_glyphs
        
        missing_glyphs = self.subtract(
            set(self.old_font.glyphs.values()),
            set(self.new_font.glyphs.values()),
        )
        if missing_glyphs:
            self.diff["glyphs"]["missing"] = missing_glyphs
        
        new_glyphs = self.subtract(
            set(self.new_font.glyphs.values()),
            set(self.old_font.glyphs.values()),
        )
        if new_glyphs:
            self.diff["glyphs"]["new"] = new_glyphs

    def subtract(self, items_a, items_b):
        return items_a - items_b

    def same(self, items_a, items_b):
        return items_a & items_b

    # tiny amount is included so we skip details no one can see
    def modified_glyphs(self, threshold=0.985):
        glyphs_a = {v: k for k, v in self.old_font.glyphs.items()}
        glyphs_b = {v: k for k, v in self.new_font.glyphs.items()}
        shared_glyphs = set(glyphs_a.keys()) & set(glyphs_b.keys())
        res = []
        for glyph_a in shared_glyphs:
            # This looks weird, but it gets us a buffer with the right
            # indices for the other font, in case the new font has different
            # glyph indices for equivalent characters.
            glyph_b = self.new_font.glyphs[glyphs_b[glyph_a]]
            img_a = glyph_a.to_image(self.old_font)
            img_b = glyph_b.to_image(self.new_font)
            diff = img_diff(img_a, img_b)
            if diff <= threshold and diff > 0:
                res.append(BufferDiff(glyph_a, glyph_b, diff))
        res.sort(key=lambda k: k.diff)
        return res

    def modified_marks(self):
        pass

    def modified_kerns(self):
        pass


class Reporter:
    def __init__(self, diff: DiffFonts, pt_size=32):
        self.diff = diff
        self.pt_size = pt_size
        self.template_dir = resource_filename("gftools", "templates")
        self.jinja = Environment(
            loader=FileSystemLoader(self.template_dir),
        )

    def save(self, fp: str, old_font: str, new_font: str):
        # create a dir which contains the html doc and fonts for easy distro
        if os.path.exists(fp):
            shutil.rmtree(fp)
        os.mkdir(fp)

        old_font_fp = os.path.join(fp, "before.ttf")
        new_font_fp = os.path.join(fp, "after.ttf")
        shutil.copyfile(old_font, old_font_fp)
        shutil.copyfile(new_font, new_font_fp)
        
        # TODO set more properties if VF
        old_css_font_face = html.CSSElement(
            "@font-face",
            font_family="before",
            src=f"url(before.ttf)",
        )
        old_css_font_class = html.CSSElement(
            "before",
            font_family="before",
        )

        new_css_font_face = html.CSSElement(
            "@font-face",
            font_family="after",
            src=f"url(after.ttf)",
        )
        new_css_font_class = html.CSSElement(
            "after",
            font_family="after",
        )

        template = self.jinja.get_template(os.path.join("diffenator", "report.html"))
        doc = template.render(
            include_ui=True,
            pt_size=self.pt_size,
            diff=self.diff,
            css_font_faces_before=[old_css_font_face],
            css_font_faces_after=[new_css_font_face],
            css_font_classes_before=[old_css_font_class],
            css_font_classes_after=[new_css_font_class],
        )
        report_out = os.path.join(fp, "report.html")
        with open(report_out, "w") as f:
            logger.info(f"Saving {report_out}")
            f.write(doc)


def img_diff(img1, img2):
    """
    Compare normalised arrays.
    """
    img1, img2 = np.array(img1), np.array(img2)

    img1_norm = img1 / np.sqrt(np.sum(img1 ** 2))
    img2_norm = img2 / np.sqrt(np.sum(img2 ** 2))

    img1_norm = np.resize(img1_norm, max(img1_norm.size, img2_norm.size))
    img2_norm = np.resize(img2_norm, max(img1_norm.size, img2_norm.size))
    return np.sum(img1_norm * img2_norm)
