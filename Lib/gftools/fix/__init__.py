"""
Functions to fix fonts so they conform to the Google Fonts
specification:
https://github.com/googlefonts/gf-docs/tree/main/Spec
"""
from fontTools.misc.fixedTools import otRound
from fontTools.ttLib import TTFont, newTable, getTableModule
from fontTools.ttLib.tables import ttProgram
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable
from fontTools.ttLib.tables._f_v_a_r import NamedInstance
from gftools.util.google_fonts import _KNOWN_WEIGHTS
from gftools.utils import (
    download_family_from_Google_Fonts,
    Google_Fonts_has_family,
    font_stylename,
    font_familyname,
    family_bounding_box,
    get_unencoded_glyphs,
    normalize_unicode_marks,
    partition_cmap,
    typo_metrics_enabled,
    validate_family,
    unique_name,
)
from gftools.axisreg import axis_registry
from gftools.util.styles import (get_stylename, is_regular, is_bold, is_italic)
from gftools.stat import gen_stat_tables

from os.path import basename, splitext
from copy import deepcopy
import logging
from glyphsLib import GSFont
from defcon import Font


log = logging.getLogger(__name__)


# The _KNOWN_WEIGHT_VALUES constant is used internally by the GF Engineering
# team so we cannot update ourselves. TODO (Marc F) unify this one day
WEIGHT_NAMES = _KNOWN_WEIGHTS
del WEIGHT_NAMES[""]
WEIGHT_NAMES["Hairline"] = 1
WEIGHT_NAMES["ExtraBlack"] = 1000
WEIGHT_VALUES = {v: k for k, v in WEIGHT_NAMES.items()}


UNWANTED_TABLES = frozenset(
    [
        "FFTM",
        "TTFA",
        "TSI0",
        "TSI1",
        "TSI2",
        "TSI3",
        "TSI5",
        "prop",
        "MVAR",
        "Debg",
    ]
)


class BaseFix:

    def __init__(self, font):
        self.font = font
        self.format = self._get_format()
        self.family_name, self.style_name = self._get_family_name()
    
    def _get_format(self):
        if isinstance(self.font, TTFont):
            return "sfnt"
        elif isinstance(self.font, GSFont):
            return "glyphs"
        elif isinstance(self.font, Font):
            return "ufo"
        else:
            raise NotImplementedError(f"Current font format isn't supported")
    
    def fix_ttf(self):
        self.skip_msg()
    
    def fix_ufo(self):
        self.skip_msg()
    
    def fix_glyphs(self):
        self.skip_msg()
    
    def skip_msg(self):
        log.info(f"Skipping {self.__class__} since a fix doesn't exist for {self.format}")
    
    def fix(self):
        if self.format == "sfnt":
            self.fix_ttf()
        elif self.format == "glyphs":
            self.fix_glyphs()
        elif self.format == "ufo":
            self.fix_ufo()

    def _get_family_name(self):
        if self.format == "glyphs":
            return self.font.familyName, self.font.styleName
        elif self.format == "ufo":
            return self.font.info.familyName, self.font.info.styleName
        elif self.format == "sfnt":
            return font_familyname(self.font), font_stylename(self.font)


class FixFSType(BaseFix):
    """
    Font Embedding (fsType)

    Set to 0 (Installable embedding)
    """

    def fix_ttf(self):
        self.font['OS/2'].fsType = 0
    
    def fix_ufo(self):
        self.font.info.openTypeOS2Type = 0
    
    def fix_glyphs(self):
        self.font.customParameters["fsType"] = []


class FixStyleLinking(BaseFix):

    def fix_ttf(self):
        self._fix_ttf_fs_selection()
        self._fix_ttf_mac_style()
    
    def _fix_ttf_fs_selection(self):
        stylename = font_stylename(self.font)
        tokens = set(stylename.split())
        old_selection = fs_selection = ttFont["OS/2"].fsSelection

        # turn off all bits except for bit 7 (USE_TYPO_METRICS)
        fs_selection &= 1 << 7

        if "Italic" in tokens:
            fs_selection |= 1 << 0
        if "Bold" in tokens:
            fs_selection |= 1 << 5
        # enable Regular bit for all other styles
        if not tokens & set(["Bold", "Italic"]):
            fs_selection |= 1 << 6
        ttFont["OS/2"].fsSelection = fs_selection
        return old_selection != fs_selection

    def _fix_ttf_mac_style(ttFont):
        """Fix the head table's macStyle so it conforms to GF's supported
        styles table:
        https://github.com/googlefonts/gf-docs/tree/main/Spec#supported-styles

        Args:
            ttFont: a TTFont instance
        """
        stylename = font_stylename(ttFont)
        tokens = set(stylename.split())
        mac_style = 0
        if "Italic" in tokens:
            mac_style |= 1 << 1
        if "Bold" in tokens:
            mac_style |= 1 << 0
        ttFont["head"].macStyle = mac_style

    def fix_glyphs(self):
            # fix instance names to pass gf spec
        for instance in self.font.instances:
            if 'Italic' in instance.name:
                instance.isItalic = True
                if instance.weight != 'Bold' and instance.weight != 'Regular':
                    instance.linkStyle = instance.weight
                else:
                    instance.linkStyle = ''
            else:
                instance.linkStyle = ''
    
    def fix_ufo(self):
        # Can infer these values if we set the Style Map Family Name
        # and Style Map Style name correctly
        family_name = self.font.info.familyName
        style_name = self.font.info.styleName
        if style_name in set(["Regular", "Italic", "Bold", "Bold Italic"]):
            # delete any map names since they are not needed
            self.font.info.styleMapFamilyName = None
            self.font.info.styleMapStyleName = None
        else:
            family = f"{family_name} {style_name}".replace("Italic", "").strip()
            self.font.info.styleMapFamilyName = family
            style = "regular" if "Italic" not in style_name else "italic"
            self.font.info.styleMapStyleName = style


def fix_family2(fonts):
    fixing_classes = [v for k,v in globals().items() if k.startswith("Fix") if k != "BaseFix"]
    for clazz in fixing_classes:
        fixer = clazz(font)
        try:
            fixer.fix()
        except NotImplementedError:
            print("Skipping")


class FixTables(BaseFix):

    def fix_ttf(self, tables=None):
        """Remove unwanted tables from a font. The unwanted tables must belong
        to the UNWANTED_TABLES set.
        """
        tables_to_remove = UNWANTED_TABLES if not tables else frozenset(tables)
        font_tables = frozenset(self.font.keys())

        tables_not_in_font = tables_to_remove - font_tables
        if tables_not_in_font:
            log.warning(
                f"Cannot remove tables '{list(tables_not_in_font)}' since they are "
                f"not in the font."
            )

        required_tables = tables_to_remove - UNWANTED_TABLES
        if required_tables:
            log.warning(
                f"Cannot remove tables '{list(required_tables)}' since they are required"
            )

        tables_to_remove = UNWANTED_TABLES & font_tables & tables_to_remove
        if not tables_to_remove:
            return
        log.info(f"Removing tables '{list(tables_to_remove)}' from font")
        for tbl in tables_to_remove:
            del self.font[tbl]


class FixHinting(BaseFix):

    def fix_ttf(self):
        # TODO determine whether font is ttfa or vtt
        if "fpgm" not in self.font:
            self._fix_ttf_unhinted()
        else:
            self._fix_ttf_hinted()
    
    def _fix_ttf_unhinted(self):
        gasp = newTable("gasp")
        # Set GASP so all sizes are smooth
        gasp.gaspRange = {0xFFFF: 15}

        program = ttProgram.Program()
        assembly = ["PUSHW[]", "511", "SCANCTRL[]", "PUSHB[]", "4", "SCANTYPE[]"]
        program.fromAssembly(assembly)

        prep = newTable("prep")
        prep.program = program

        self.font["gasp"] = gasp
        self.font["prep"] = prep
    
    def _fix_ttf_hinted(self):
        # We may want to throw in a custom gasp table here
        old = self.font["head"].flags
        self.font["head"].flags |= 1 << 3
        return self.font["head"].flags != old

    def fix_ufo(self):
        # idk if there's hinting in ufo2ft yet
        # this pr, https://github.com/googlefonts/ufo2ft/pull/335 was reverted
        # dama just store their vtt instructions in the ufo's data dir
        # let's just treat ufos as unhinted for the time being
        self.font.info.openTypeGaspRangeRecords = [
            {'rangeGaspBehavior': [0, 1, 2, 3], 'rangeMaxPPEM': 65535}
        ]
    
    def fix_glyphs(self):
        # Glyphsapp's gasp panel is broken
        pass


class FixWeightClass(BaseFix):

    def fix_ttf(self):
        stylename = font_stylename(self.font)
        tokens = stylename.split()
        self.font['OS/2'].usWeightClass = self._get_weight_class(tokens)
    
    def fix_glyphs(self):
        for instance in self.font.instances:
            tokens = instance.name.split()
            instance.weightClass = self._get_weight_class(tokens)
    
    def fix_ufo(self):
        tokens = self.font.info.styleName.split()
        self.font.info.openTypeOS2WeightClass = self._get_weight_class(tokens)
    
    def _get_weight_class(self, tokens):
        # Order WEIGHT_NAMES so longest names are first
        for style in sorted(WEIGHT_NAMES, key=lambda k: len(k), reverse=True):
            if style in tokens:
                return WEIGHT_NAMES[style]

        if "Italic" in tokens:
            return 400
        raise ValueError(
            f"Cannot determine usWeightClass because font style, '{stylename}' "
            f"doesn't have a weight token which is in our known "
            f"weights, '{WEIGHT_NAMES.keys()}'"
        )


class FixInstances(BaseFix):

    def fix_ttf(self):
        """Replace a variable font's fvar instances with a set of new instances
        that conform to the Google Fonts instance spec:
        https://github.com/googlefonts/gf-docs/tree/main/Spec#fvar-instances

        Args:
            self.font: a self.font instance
        """
        if "fvar" not in self.font:
            return

        fvar = self.font["fvar"]
        default_axis_vals = {a.axisTag: a.defaultValue for a in fvar.axes}

        stylename = font_stylename(self.font)
        is_italic = "Italic" in stylename
        is_roman_and_italic = any(a for a in ("slnt", "ital") if a in default_axis_vals)

        wght_axis = next((a for a in fvar.axes if a.axisTag == "wght"), None)
        wght_min = int(wght_axis.minValue)
        wght_max = int(wght_axis.maxValue)

        nametable = self.font["name"]

        def gen_instances(is_italic):
            results = []
            for wght_val in range(wght_min, wght_max + 100, 100):
                name = (
                    WEIGHT_VALUES[wght_val]
                    if not is_italic
                    else f"{WEIGHT_VALUES[wght_val]} Italic".strip()
                )
                name = name.replace("Regular Italic", "Italic")

                coordinates = deepcopy(default_axis_vals)
                coordinates["wght"] = wght_val

                inst = NamedInstance()
                inst.subfamilyNameID = nametable.addName(name)
                inst.coordinates = coordinates
                results.append(inst)
            return results

        instances = []
        if is_roman_and_italic:
            for bool_ in (False, True):
                instances += gen_instances(is_italic=bool_)
        elif is_italic:
            instances += gen_instances(is_italic=True)
        else:
            instances += gen_instances(is_italic=False)
        fvar.instances = instances
    
    def fix_glyphs(self):
        # Strip out instances which are not Thin-Black or Thin Italic-Black Italic.
        # We cannot generate these from scratch because we cannot infer how designer units
        # will translate
        names = set(WEIGHT_VALUES.values())
        names |= set(f"{n} Italic".replace("Regular Italic", "Italic").strip() for n in names)
        self.font.instances = [i for i in self.font.instances if i.name in names] 
    
    def fix_designspace(self):
        # do the same as glyphsapp also update basefix to load designspaces
        pass


def update_nametable(ttFont, family_name=None, style_name=None):
    """Update a static font's name table. The updated name table will conform
    to the Google Fonts support styles table:
    https://github.com/googlefonts/gf-docs/tree/main/Spec#supported-styles

    If a style_name includes tokens other than wght and ital, these tokens
    will be appended to the family name e.g

    Input:
    family_name="MyFont"
    style_name="SemiCondensed SemiBold"

    Output:
    familyName (nameID 1) = "MyFont SemiCondensed SemiBold
    subFamilyName (nameID 2) = "Regular"
    typo familyName (nameID 16) = "MyFont SemiCondensed"
    typo subFamilyName (nameID 17) = "SemiBold"

    Google Fonts has used this model for several years e.g
    https://fonts.google.com/?query=cabin

    Args:
        ttFont:
        family_name: New family name
        style_name: New style name
    """
    if "fvar" in ttFont:
        raise ValueError("Cannot update the nametable for a variable font")
    nametable = ttFont["name"]

    # Remove nametable records which are not Win US English
    # TODO this is too greedy. We should preserve multilingual
    # names in the future. Please note, this has always been an issue.
    platforms = set()
    for rec in nametable.names:
        platforms.add((rec.platformID, rec.platEncID, rec.langID))
    platforms_to_remove = platforms ^ set([(3, 1, 0x409)])
    if platforms_to_remove:
        log.warning(
            f"Removing records which are not Win US English, {list(platforms_to_remove)}"
        )
        for platformID, platEncID, langID in platforms_to_remove:
            nametable.removeNames(
                platformID=platformID, platEncID=platEncID, langID=langID
            )

    # Remove any name records which contain linebreaks
    contains_linebreaks = []
    for r in nametable.names:
        for char in ("\n", "\r"):
            if char in r.toUnicode():
                contains_linebreaks.append(r.nameID)
    for nameID in contains_linebreaks:
        nametable.removeNames(nameID)

    if not family_name:
        family_name = font_familyname(ttFont)

    if not style_name:
        style_name = font_stylename(ttFont)

    ribbi = ("Regular", "Bold", "Italic", "Bold Italic")
    tokens = family_name.split() + style_name.split()

    nameids = {
        1: " ".join(t for t in tokens if t not in ribbi),
        2: " ".join(t for t in tokens if t in ribbi) or "Regular",
        16: " ".join(t for t in tokens if t not in list(WEIGHT_NAMES) + ['Italic']),
        17: " ".join(t for t in tokens if t in list(WEIGHT_NAMES) + ['Italic']) or "Regular"
    }
    # Remove typo name if they match since they're redundant
    if nameids[16] == nameids[1]:
        del nameids[16]
    if nameids[17] == nameids[2]:
        del nameids[17]

    family_name = nameids.get(16) or nameids.get(1)
    style_name = nameids.get(17) or nameids.get(2)

    # create NameIDs 3, 4, 6
    nameids[4] = f"{family_name} {style_name}"
    nameids[6] = f"{family_name.replace(' ', '')}-{style_name.replace(' ', '')}"
    nameids[3] = unique_name(ttFont, nameids)

    # Pass through all records and replace occurences of the old family name
    # with the new family name
    current_family_name = font_familyname(ttFont)
    for record in nametable.names:
        string = record.toUnicode()
        if current_family_name in string:
            nametable.setName(
                string.replace(current_family_name, family_name),
                record.nameID,
                record.platformID,
                record.platEncID,
                record.langID,
            )

    # Remove previous typographic names
    for nameID in (16, 17):
        nametable.removeNames(nameID=nameID)

    # Update nametable with new names
    for nameID, string in nameids.items():
        nametable.setName(string, nameID, 3, 1, 0x409)


def fix_nametable(ttFont):
    """Fix a static font's name table so it conforms to the Google Fonts
    supported styles table:
    https://github.com/googlefonts/gf-docs/tree/main/Spec#supported-styles

    Args:
        ttFont: a TTFont instance
    """
    if "fvar" in ttFont:
        from fontTools.varLib.instancer.names import updateNameTable
        dflt_axes = {a.axisTag: a.defaultValue for a in ttFont['fvar'].axes}
        updateNameTable(ttFont, dflt_axes)
        return
    family_name = font_familyname(ttFont)
    style_name = font_stylename(ttFont)
    update_nametable(ttFont, family_name, style_name)


def rename_font(font, new_name):
    nametable = font["name"]
    current_name = font_familyname(font)
    if not current_name:
        raise Exception(
            "Name table does not contain nameID 1 or nameID 16. "
            "This tool does not work on webfonts."
        )
    log.info("Updating font name records")
    for record in nametable.names:
        record_string = record.toUnicode()

        no_space = current_name.replace(" ", "")
        hyphenated = current_name.replace(" ", "-")
        if " " not in record_string:
            new_string = record_string.replace(no_space, new_name.replace(" ", ""))
        else:
            new_string = record_string.replace(current_name, new_name)

        if new_string is not record_string:
            record_info = (
                record.nameID,
                record.platformID,
                record.platEncID,
                record.langID
            )
            log.info(
                "Updating {}: '{}' to '{}'".format(
                    record_info,
                    record_string,
                    new_string,
                )
            )
            record.string = new_string


def fix_filename(ttFont):
    ext = splitext(ttFont.reader.file.name)[1]
    family_name = font_familyname(ttFont)
    style_name = font_stylename(ttFont)

    if "fvar" in ttFont:
        axes = ",".join([a.axisTag for a in ttFont['fvar'].axes])
        if "Italic" in style_name:
            return f"{family_name}-Italic[{axes}]{ext}".replace(" ", "")
        return f"{family_name}[{axes}]{ext}".replace(" ", "")
    return f"{family_name}-{style_name}{ext}".replace(" ", "")


def inherit_vertical_metrics(ttFonts, family_name=None):
    """Inherit the vertical metrics from the same family which is
    hosted on Google Fonts.

    Args:
        ttFonts: a list of TTFont instances which belong to a family
        family_name: Optional string which allows users to specify a
            different family to inherit from e.g "Maven Pro".
    """
    family_name = font_familyname(ttFonts[0]) if not family_name else family_name

    gf_fonts = list(map(TTFont, download_family_from_Google_Fonts(family_name)))
    gf_fonts = {font_stylename(f): f for f in gf_fonts}
    # TODO (Marc F) use Regular font instead. If VF use font which has Regular
    # instance
    gf_fallback = list(gf_fonts.values())[0]

    fonts = {font_stylename(f): f for f in ttFonts}
    for style, font in fonts.items():
        if style in gf_fonts:
            src_font = gf_fonts[style]
        else:
            src_font = gf_fallback
        copy_vertical_metrics(src_font, font)

        if typo_metrics_enabled(src_font):
            font["OS/2"].fsSelection |= 1 << 7


class FixInheritVerticalMetrics(BaseFix):
    # TODO Adjust by upm vals

    def __init__(self, font):
        super().__init__(font=font)
        self.on_googlefonts = Google_Fonts_has_family(self.family_name)
        if not self.on_googlefonts:
            log.warning(f"Family is not on Google Fonts")
            return
        gf_family = download_family_from_Google_Fonts(self.family_name)
        self.gf_ttFonts = [TTFont(f) for f in gf_family]
        self.gf_font = self.match_font()
    
    def match_font(self):
        for gf_ttFont in self.gf_ttFonts:
            gf_styles = self._styles_in_ttFont(gf_ttFont)

            if self.format == "sfnt":
                styles = self._styles_in_ttFont(self.font)
            elif self.format == "ufo":
                styles = set([self.font.info.styleName])
            elif self.format == "glyphs":
                styles = set(i.name for i in self.font.instances)
            
            matching = styles & gf_styles
            if matching:
                return gf_ttFont
        # TODO return Regular instead
        log.warning(f"{self.style_name} isn't on Google Fonts. Using first font instead")
        return self.gf_ttFonts[0]
    
    def _styles_in_ttFont(self, ttFont):
        name_tbl = ttFont['name']
        if "fvar" in ttFont:
            res = set()
            for inst in ttFont['fvar'].instances:
                res.add(
                    name_tbl.getName(inst.subfamilyNameID, 3, 1, 0x409).toUnicode()
                )
            return res
        return set([font_stylename(ttFont)])

    def fix_ttf(self):
        self.font['OS/2'].usWinAscent = self.gf_font['OS/2'].usWinAscent
        self.font['OS/2'].usWinDescent = self.gf_font['OS/2'].usWinDescent
        self.font['OS/2'].sTypoAscender = self.gf_font['OS/2'].sTypoAscender
        self.font['OS/2'].sTypoDescender = self.gf_font['OS/2'].sTypoDescender
        self.font['OS/2'].sTypoLineGap = self.gf_font['OS/2'].sTypoLineGap
        self.font['hhea'].ascender = self.gf_font['hhea'].ascender
        self.font['hhea'].descender = self.gf_font['hhea'].descender
        self.font['hhea'].lineGap = self.gf_font['hhea'].lineGap
    
    def fix_ufo(self):
        import pdb
        pdb.set_trace()
        self.font.info.openTypeOS2WinAscent = self.gf_font['OS/2'].usWinAscent
        self.font.info.openTypeOS2WinDescent = self.gf_font['OS/2'].usWinDescent
        self.font.info.openTypeOS2TypoAscender = self.gf_font['OS/2'].sTypoAscender
        self.font.info.openTypeOS2TypoDescender = self.gf_font['OS/2'].sTypoDescender
        self.font.info.openTypeOS2TypoLineGap = self.gf_font['OS/2'].sTypoLineGap
        self.font.info.openTypeHheaAscender = self.gf_font['hhea'].ascender
        self.font.info.openTypeHheaDescender = self.gf_font['hhea'].descender
        self.font.info.openTypeHheaLineGap = self.gf_font['hhea'].lineGap
    
    def fix_glyphs(self):
        for master in self.font.masters:
            master.winAscent = self.gf_font['OS/2'].usWinAscent
            master.winDescent = self.gf_font['OS/2'].usWinDescent
            master.typoAscender = self.gf_font['OS/2'].sTypoAscender
            master.typoDescender = self.gf_font['OS/2'].sTypoDescender
            master.typoLineGap = self.gf_font['OS/2'].sTypoLineGap
            master.hheaAscender = self.gf_font["hhea"].ascender
            master.hheaDescender = self.gf_font['hhea'].descender
            master.hheaLineGap = self.gf_font['hhea'].lineGap


def fix_vertical_metrics(ttFonts):
    """Fix a family's vertical metrics based on:
    https://github.com/googlefonts/gf-docs/tree/main/VerticalMetrics

    Args:
        ttFonts: a list of TTFont instances which belong to a family
    """
    src_font = next((f for f in ttFonts if font_stylename(f) == "Regular"), ttFonts[0])

    # TODO (Marc F) CJK Fonts?

    # If OS/2.fsSelection bit 7 isn't enabled, enable it and set the typo metrics
    # to the previous win metrics.
    if not typo_metrics_enabled(src_font):
        src_font["OS/2"].fsSelection |= 1 << 7  # enable USE_TYPO_METRICS
        src_font["OS/2"].sTypoAscender = src_font["OS/2"].usWinAscent
        src_font["OS/2"].sTypoDescender = -src_font["OS/2"].usWinDescent
        src_font["OS/2"].sTypoLineGap = 0

    # Set the hhea metrics so they are the same as the typo
    src_font["hhea"].ascent = src_font["OS/2"].sTypoAscender
    src_font["hhea"].descent = src_font["OS/2"].sTypoDescender
    src_font["hhea"].lineGap = src_font["OS/2"].sTypoLineGap

    # Set the win Ascent and win Descent to match the family's bounding box
    win_desc, win_asc = family_bounding_box(ttFonts)
    src_font["OS/2"].usWinAscent = win_asc
    src_font["OS/2"].usWinDescent = abs(win_desc)

    # Set all fonts vertical metrics so they match the src_font
    for ttFont in ttFonts:
        ttFont["OS/2"].fsSelection |= 1 << 7
        copy_vertical_metrics(src_font, ttFont)


def copy_vertical_metrics(src_font, dst_font):
    for table, key in [
        ("OS/2", "usWinAscent"),
        ("OS/2", "usWinDescent"),
        ("OS/2", "sTypoAscender"),
        ("OS/2", "sTypoDescender"),
        ("OS/2", "sTypoLineGap"),
        ("hhea", "ascent"),
        ("hhea", "descent"),
        ("hhea", "lineGap"),
    ]:
        val = getattr(src_font[table], key)
        setattr(dst_font[table], key, val)


class FixItalicAngle(BaseFix):
    # TODO (Marc F) implement for italic fonts
    def fix_ttf(self):
        style_name = font_stylename(self.font)
        if "Italic" not in style_name and self.font["post"].italicAngle != 0:
            self.font["post"].italicAngle = 0
    
    def fix_glyphs(self):
        for master in self.font.masters:
            if "Italc" not in master.name and master.italicAngle != 0:
                master.italicAngle = 0


def fix_ascii_fontmetadata(font):
    """Fixes TTF 'name' table strings to be ascii only"""
    for name in font['name'].names:
        title = name.string.decode(name.getEncoding())
        title = normalize_unicode_marks(title)
        name.string = title.encode(name.getEncoding())


def convert_cmap_subtables_to_v4(font):
  """Converts all cmap subtables to format 4.

  Returns a list of tuples (format, platformID, platEncID) of the tables
  which needed conversion."""
  cmap = font['cmap']
  outtables = []
  converted = []
  for table in cmap.tables:
    if table.format != 4:
      converted.append((table.format, table.platformID, table.platEncID))
    newtable = CmapSubtable.newSubtable(4)
    newtable.platformID = table.platformID
    newtable.platEncID = table.platEncID
    newtable.language = table.language
    newtable.cmap = table.cmap
    outtables.append(newtable)
  font['cmap'].tables = outtables
  return converted


def drop_nonpid0_cmap(font, report=True):
  keep, drop = partition_cmap(font, lambda table: table.platformID == 0, report)
  return drop


def drop_mac_cmap(font, report=True):
  keep, drop = partition_cmap(font, lambda table: table.platformID != 1 or table.platEncID != 0, report)
  return drop

def fix_pua(font):
    unencoded_glyphs = get_unencoded_glyphs(font)
    if not unencoded_glyphs:
        return

    ucs2cmap = None
    cmap = font["cmap"]

    # Check if an UCS-2 cmap exists
    for ucs2cmapid in ((3, 1), (0, 3), (3, 0)):
        ucs2cmap = cmap.getcmap(ucs2cmapid[0], ucs2cmapid[1])
        if ucs2cmap:
            break
    # Create UCS-4 cmap and copy the contents of UCS-2 cmap
    # unless UCS 4 cmap already exists
    ucs4cmap = cmap.getcmap(3, 10)
    if not ucs4cmap:
        cmapModule = getTableModule('cmap')
        ucs4cmap = cmapModule.cmap_format_12(12)
        ucs4cmap.platformID = 3
        ucs4cmap.platEncID = 10
        ucs4cmap.language = 0
        if ucs2cmap:
            ucs4cmap.cmap = deepcopy(ucs2cmap.cmap)
        cmap.tables.append(ucs4cmap)
    # Map all glyphs to UCS-4 cmap Supplementary PUA-A codepoints
    # by 0xF0000 + glyphID
    ucs4cmap = cmap.getcmap(3, 10)
    for glyphID, glyph in enumerate(font.getGlyphOrder()):
        if glyph in unencoded_glyphs:
            ucs4cmap.cmap[0xF0000 + glyphID] = glyph
    font['cmap'] = cmap
    return True


def fix_isFixedPitch(ttfont):

    same_width = set()
    glyph_metrics = ttfont['hmtx'].metrics
    messages = []
    changed = False
    for character in [chr(c) for c in range(65, 91)]:
        same_width.add(glyph_metrics[character][0])

    if len(same_width) == 1:
        if ttfont['post'].isFixedPitch == 1:
            messages.append("Skipping isFixedPitch is set correctly")
        else:
            messages.append("Font is monospace. Updating isFixedPitch to 0")
            ttfont['post'].isFixedPitch = 1
            changed = True

        familyType = ttfont['OS/2'].panose.bFamilyType
        if familyType == 2:
            expected = 9
        elif familyType == 3 or familyType == 5:
            expected = 3
        elif familyType == 0:
            messages.append("Font is monospace but panose fields seems to be not set."
                  " Setting values to defaults (FamilyType = 2, Proportion = 9).")
            ttfont['OS/2'].panose.bFamilyType = 2
            ttfont['OS/2'].panose.bProportion = 9
            changed = True
            expected = None
        else:
            expected = None

        if expected:
            if ttfont['OS/2'].panose.bProportion == expected:
                messages.append("Skipping OS/2.panose.bProportion is set correctly")
            else:
                messages.append(("Font is monospace."
                       " Since OS/2.panose.bFamilyType is {}"
                       " we're updating OS/2.panose.bProportion"
                       " to {}").format(familyType, expected))
                ttfont['OS/2'].panose.bProportion = expected
                changed = True

        widths = [m[0] for m in ttfont['hmtx'].metrics.values() if m[0] > 0]
        width_max = max(widths)
        if ttfont['hhea'].advanceWidthMax == width_max:
            messages.append("Skipping hhea.advanceWidthMax is set correctly")
        else:
            messsages.append("Font is monospace. Updating hhea.advanceWidthMax to %i" %
                  width_max)
            ttfont['hhea'].advanceWidthMax = width_max
            changed = True

        avg_width = otRound(sum(widths) / len(widths))
        if avg_width == ttfont['OS/2'].xAvgCharWidth:
            messages.append("Skipping OS/2.xAvgCharWidth is set correctly")
        else:
            messages.append("Font is monospace. Updating OS/2.xAvgCharWidth to %i" %
                  avg_width)
            ttfont['OS/2'].xAvgCharWidth = avg_width
            changed = True
    else:
        if ttfont['post'].isFixedPitch != 0 or ttfont['OS/2'].panose.bProportion != 0:
            changed = True
        ttfont['post'].isFixedPitch = 0
        ttfont['OS/2'].panose.bProportion = 0
    return changed, messages


def drop_superfluous_mac_names(ttfont):
    """Drop superfluous Mac nameIDs.

    The following nameIDS are kept:
    1: Font Family name,
    2: Font Family Subfamily name,
    3: Unique font identifier,
    4: Full font name,
    5: Version string,
    6: Postscript name,
    16: Typographic family name,
    17: Typographic Subfamily name
    18: Compatible full (Macintosh only),
    20: PostScript CID,
    21: WWS Family Name,
    22: WWS Subfamily Name,
    25: Variations PostScript Name Prefix.

    We keep these IDs in order for certain application to still function
    such as Word 2011. IDs 1-6 are very common, > 16 are edge cases.

    https://www.microsoft.com/typography/otspec/name.htm"""
    keep_ids = [1, 2, 3, 4, 5, 6, 16, 17, 18, 20, 21, 22, 25]
    changed = False
    for n in range(255):
        if n not in keep_ids:
            name = ttfont['name'].getName(n, 1, 0, 0)
            if name:
                changed = True
                ttfont['name'].names.remove(name)
    return changed


def drop_mac_names(ttfont):
    """Drop all mac names"""
    changed = False
    for n in range(255):
        name = ttfont['name'].getName(n, 1, 0, 0)
        if name:
            ttfont['name'].names.remove(name)
            changed = True
    return changed


def fix_font(font, include_source_fixes=False, new_family_name=None):
    if new_family_name:
        rename_font(font, new_family_name)
    font["OS/2"].version = 4

    if "fpgm" in font:
        fix_hinted_font(font)
    else:
        fix_unhinted_font(font)

    if "fvar" in font:
        remove_tables(font, ["MVAR"])

    if include_source_fixes:
        log.warning(
            "include-source-fixes is enabled. Please consider fixing the "
            "source files instead."
        )
        remove_tables(font)
        fix_nametable(font)
        fix_fs_type(font)
        fix_fs_selection(font)
        fix_mac_style(font)
        fix_weight_class(font)
        fix_italic_angle(font)

        if "fvar" in font:
            fix_fvar_instances(font)


def fix_family(fonts, include_source_fixes=False, new_family_name=None):
    """Fix all fonts in a family"""
    validate_family(fonts)

    for font in fonts:
        fix_font(
            font,
            include_source_fixes=include_source_fixes,
            new_family_name=new_family_name
        )
    family_name = font_familyname(fonts[0])
    if include_source_fixes:
        try:
            if Google_Fonts_has_family(family_name):
                inherit_vertical_metrics(fonts)
            else:
                log.warning(
                    f"{family_name} is not on Google Fonts. Skipping "
                    "regression fixes"
                )
        except FileNotFoundError:
            log.warning(
                f"Google Fonts api key not found so we can't regression "
                "fix fonts. See Repo readme to add keys."
            )
        fix_vertical_metrics(fonts)
        if all(["fvar" in f for f in fonts]):
            gen_stat_tables(fonts, ["opsz", "wdth", "wght", "ital", "slnt"])


class FontFixer():
    def __init__(self, path, report=True, verbose=False, **kwargs):
        self.font = TTFont(path)
        self.path = path
        self.font_filename = basename(path)
        self.saveit = False
        self.report = report
        self.verbose = verbose
        self.messages = []
        self.args = kwargs
        self.fixes = []
        if "fixes" in kwargs:
            self.fixes = kwargs["fixes"]

    def __del__(self):
        if self.report:
            print("\n".join(self.messages))
        if self.saveit:
            if self.verbose:
                print('Saving %s to %s.fix' % (self.font_filename, self.path))
            self.font.save(self.path + ".fix")
        elif self.verbose:
            print('There were no changes needed on %s!' % self.font_filename)

    def show(self):
        pass

    def fix(self):
        for f in self.fixes:
            rv = f(self.font)
            if isinstance(rv, tuple) and len(rv) == 2:
                changed, messages = rv
                self.messages.extend(messages)
            else:
                changed = rv
            if changed:
                self.saveit = True


class GaspFixer(FontFixer):

    def fix(self, value=15):
        try:
            table = self.font.get('gasp')
            table.gaspRange[65535] = value
            self.saveit = True
        except:
            print(('ER: {}: no table gasp... '
                  'Creating new table. ').format(self.path))
            table = ttLib.newTable('gasp')
            table.gaspRange = {65535: value}
            self.font['gasp'] = table
            self.saveit = True

    def show(self):
        try:
            self.font.get('gasp')
        except:
            print('ER: {}: no table gasp'.format(self.path))
            return

        try:
            print(self.font.get('gasp').gaspRange[65535])
        except IndexError:
            print('ER: {}: no index 65535'.format(self.path))

