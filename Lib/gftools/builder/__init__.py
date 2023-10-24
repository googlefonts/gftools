"""
gftools-builder: Config-driven font project builder
===================================================

This utility wraps fontmake and a number of post-processing fixes to
build variable, static OTF, static TTF and webfonts from Glyphs,
Designspace/UFO or UFO sources.

It should be instantiated with a configuration file, typically ``config.yaml``,
which looks like this::

    sources:
      - Texturina.glyphs
      - Texturina-Italic.glyphs
    axisOrder:
      - opsz
      - wght
    outputDir: "../fonts"
    familyName: Texturina
    version: 1.005
    stat:
      - name: Width
        tag: wdth
        values:
        - name: UltraCondensed
          value: 50
          ...
      - name: Weight
        tag: wght
        values:
        - name: Hairline
          rangeMinValue: 1
          nominalValue: 1
          rangeMaxValue: 50
        ...
    statFormat4:
      - name: Green
        location:
          wght: 300
          wdth: 200
      - name: Blue
        location:
          wght: 400
          wdth: 200
    ...
    instances:
      Texturina[wght].ttf:
      - coordinates:
          wght: 400
      - coordinates:
          wght: 500
      - familyName: "Texturina Exotic"
        styleName: "Medium"
        coordinates:
          wght: 500
        ...
      Texturina-Italic[wght].ttf:
      - coordinates:
          wght: 700
        ...
    vttSources:
      Texturina[wght].ttf: vtt-roman.ttx
      Texturina-Italic[wght].ttf: vtt-italic.ttx
    ...

To build a font family from the command line, use:

    gftools builder path/to/config.yaml

The config file may contain the following keys. The ``sources`` key is
required, all others have sensible defaults:

* ``sources``: Required. An array of Glyphs, UFO or designspace source files.
* ``logLevel``: Debugging log level. Defaults to ``INFO``.
* ``stylespaceFile``: A statmake ``.stylespace`` file.
* ``stat``: A STAT table configuration. This may be either a list of axes and
  values as demonstrated above, or a dictionary mapping each variable font to a
  per-source list. If neither ``stylespaceFile`` or ``stat`` are provided, a
  STAT table is generated automatically using ``gftools.stat``.
* ``instances``: A list of static font TTF instances to generate from each variable
  font as demonstrated above. If this argument isn't provided, static TTFs will
  be generated for each instance that is specified in the source files.
* ``buildVariable``: Build variable fonts. Defaults to true.
* ``buildStatic``: Build static fonts (OTF or TTF depending on ``$buildOTF``
  and ``$buildTTF`). Defaults to true.
* ``buildOTF``: Build OTF fonts. Defaults to true.
* ``buildTTF``: Build TTF fonts. Defaults to true.
* ``buildWebfont``: Build WOFF2 fonts. Defaults to ``$buildStatic``.
* ``outputDir``: Where to put the fonts. Defaults to ``../fonts/``
* ``vfDir``: Where to put variable fonts. Defaults to ``$outputDir/variable``.
* ``ttDir``: Where to put TrueType static fonts. Defaults to ``$outputDir/ttf``.
* ``otDir``: Where to put CFF static fonts. Defaults to ``$outputDir/otf``.
* ``woffDir``: Where to put WOFF2 static fonts. Defaults to ``$outputDir/webfonts``.
* ``cleanUp``: Whether or not to remove temporary files. Defaults to ``true``.
* ``autohintTTF``: Whether or not to autohint TTF files. Defaults to ``true``.
* ``ttfaUseScript``: Whether or not to detect a font's primary script and add a ``-D<script>`` flag to ttfautohint. Defaults to ``false``.
* ``vttSources``: To patch a manual VTT hinting program (ttx format) to font binaries.
* ``axisOrder``: STAT table axis order. Defaults to fvar order.
* ``familyName``: Family name for variable fonts. Defaults to family name of first source file.
* ``flattenComponents``: Whether to flatten components on export. Defaults to ``true``.
* ``decomposeTransformedComponents``: Whether to decompose transformed components on export. Defaults to ``true``.
* ``googleFonts``: Whether this font is destined for release on Google Fonts. Used by GitHub Actions. Defaults to ``false``.
* ``category``: If this font is destined for release on Google Fonts, a list of the categories it should be catalogued under. Used by GitHub Actions. Must be set if ``googleFonts`` is set.
* ``fvarInstanceAxisDflts``: Mapping to set every fvar instance's non-wght axis
  value e.g if a font has a wdth and wght axis, we can set the wdth to be 100 for
  every fvar instance. Defaults to ``None``
* ``expandFeaturesToInstances``: Resolve all includes in the sources' features, so that generated instances can be compiled without errors. Defaults to ``true``.
* ``reverseOutlineDirection``: Reverse the outline direction when compiling TTFs (no effect for OTFs). Defaults to fontmake's default.
* ``removeOutlineOverlaps``: Remove overlaps when compiling fonts. Defaults to fontmake's default.
* ``interpolate``: Enable fontmake --interpolate flag. Defaults to ``false``.
* ``checkCompatibility``: Enable fontmake Multiple Master compatibility checking. Defaults to ``true``.
* ``useMutatorMath``: Use MutatorMath to generate instances (supports extrapolation and anisotropic locations). Defaults to ``false``.
* ``glyphData``: An array of custom GlyphData XML files for with glyph info (production name, script, category, subCategory, etc.). Used only for Glyphs sources.
"""

from fontmake.font_project import FontProject
from fontTools import designspaceLib
from fontTools.otlLib.builder import buildStatTable
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.woff2 import main as woff2_main
from fontv.libfv import FontVersion
from gftools.builder.schema import schema
from gftools.builder.autohint import autohint
from gftools.fix import fix_font, fix_hinted_font
from gftools.stat import gen_stat_tables, gen_stat_tables_from_config
from gftools.utils import font_is_italic, font_familyname, font_stylename
from gftools.instancer import gen_static_font
from strictyaml import load, YAMLError
from strictyaml.exceptions import YAMLValidationError
from ufo2ft import CFFOptimization
from ufo2ft.filters.flattenComponents import FlattenComponentsFilter
from ufo2ft.filters.decomposeTransformedComponents import DecomposeTransformedComponentsFilter
from vttLib.transfer import merge_from_file as merge_vtt_hinting
from vttLib import compile_instructions as compile_vtt_hinting
from afdko.otfautohint.__main__ import main as otfautohint
import difflib
import gftools
import glyphsLib
from defcon import Font
import argparse
import logging
import os
import platform
import re
import shutil
import statmake.classes
import statmake.lib
import sys
import tempfile


class GFBuilder:
    schema = schema

    def __init__(self, configfile=None, config=None):
        if configfile:
            self.config = self.load_config(configfile)
            if os.path.dirname(configfile):
                os.chdir(os.path.dirname(configfile))
        else:
            self.config = config
        self.logger = logging.getLogger("GFBuilder")
        self.outputs = set()  # A list of files we created
        self.fill_config_defaults()

    def load_config(self, configfile):
        with open(configfile) as f:
            unprocessed_yaml = f.read()
        try:
            return load(unprocessed_yaml, self.schema).data
        except YAMLValidationError as e:
            if "unexpected key not in schema" in e.problem:
                bad_key = str(e.problem)
                raise YAMLError(
                    f"\nA key in the configuration file, typically ``config.yaml``, is likely misspelled."
                    f"\nError caused by: {bad_key}"
                )
            else:
                raise ValueError(
                    "The yaml config file isn't structured properly. Please refer to: "
                    "https://github.com/googlefonts/gftools/blob/main/Lib/gftools/builder/__init__.py#L7"
                )

    def build(self):
        loglevel = getattr(logging, self.config["logLevel"].upper())
        logging.basicConfig(level=loglevel)
        self.logger.setLevel(loglevel)
        # Shut up irrelevant loggers
        if loglevel != logging.DEBUG:
            for irrelevant in [
                "glyphsLib.classes",
                "glyphsLib.builder.components",
                "ufo2ft",
                "ufo2ft.filters",
                "ufo2ft.postProcessor",
                "fontTools.varLib",
                "fontTools.feaLib.parser",
                "cu2qu.ufo",
                "glyphsLib.builder.builders.UFOBuilder",
            ]:
                logging.getLogger(irrelevant).setLevel(logging.ERROR)

        # Store the current files/dirs listed in the source dir. Using
        # self.config['cleanUp'] will delete the auxiliary dirs/files which
        # are created whilst building so we need know the original
        # dir state in order to do this.
        source_files = os.listdir()

        if self.config["buildVariable"]:
            self.build_variable()
            # transfer vf vtt hints now in case static fonts are instantiated
        if self.config["buildStatic"]:
            self.build_static()
        # All done
        self.logger.info(
            "Building %s completed. All done!" % (
                ", ".join([
                    b.lstrip("build").lower()
                    for b in ["buildVariable", "buildStatic", "buildWebfont"]
                    if self.config[b]
                ])
            )
        )
        if self.config["cleanUp"]:
            files_added_during_build = set(os.listdir()) - set(source_files)
            if not files_added_during_build:
                return
            self.logger.info(
                f"Removing auxiliary dirs/files {files_added_during_build}"
            )
            for file_ in files_added_during_build:
                self.rm(file_)

    def get_family_name(self):
        """Ensure that all source files have the same family name"""
        names = set()
        for fp in self.config["sources"]:
            if fp.endswith("glyphs"):
                src = glyphsLib.GSFont(fp)
                names.add(src.familyName)
            elif fp.endswith("ufo"):
                src = Font(fp)
                names.add(src.info.familyName)
            elif fp.endswith("designspace"):
                ds = designspaceLib.DesignSpaceDocument.fromfile(self.config["sources"][0])
                names.add(ds.sources[0].familyName)
            else:
                raise ValueError(f"{fp} not a supported source file!")

        if len(names) > 1:
            raise ValueError(
                f"Inconsistent family names in sources {names}. Set familyName in config instead"
            )
        return list(names)[0]

    def determine_variability(self):
        is_variable = []
        for fp in self.config["sources"]:
            if fp.endswith(("glyphs", "glyphspackage")):
                src = glyphsLib.GSFont(fp)
                is_variable.append(len(src.masters) > 1)
            elif fp.endswith("ufo"):
                is_variable.append(False)
            elif fp.endswith("designspace"):
                ds = designspaceLib.DesignSpaceDocument.fromfile(self.config["sources"][0])
                is_variable.append(len(ds.sources) > 1)
        # This needs to be consistent...
        if any(variability != is_variable[0] for variability in is_variable[1:]):
            raise ValueError("Some sources were multi-master and some were not. Specify buildVariable manually.")
        return is_variable[0]

    def fill_config_defaults(self):
        if "familyName" not in self.config:
            self.logger.info("Deriving family name (this takes a while)")
            self.config["familyName"] = self.get_family_name()
        if "outputDir" not in self.config:
            self.config["outputDir"] = "../fonts"
        if "vfDir" not in self.config:
            self.config["vfDir"] = self.config["outputDir"] + "/variable"
        if "ttDir" not in self.config:
            self.config["ttDir"] = self.config["outputDir"] + "/ttf"
        if "otDir" not in self.config:
            self.config["otDir"] = self.config["outputDir"] + "/otf"
        if "woffDir" not in self.config:
            self.config["woffDir"] = self.config["outputDir"] + "/webfonts"

        if "buildVariable" not in self.config:
            self.config["buildVariable"] = self.determine_variability()
        if "buildStatic" not in self.config:
            self.config["buildStatic"] = True
        if "buildOTF" not in self.config:
            self.config["buildOTF"] = True
        if "buildTTF" not in self.config:
            self.config["buildTTF"] = True
        if "buildWebfont" not in self.config:
            self.config["buildWebfont"] = self.config["buildStatic"]
        if "autohintTTF" not in self.config:
            self.config["autohintTTF"] = True
        if "autohintOTF" not in self.config:
            self.config["autohintOTF"] = True
        if "ttfaUseScript" not in self.config:
            self.config["ttfaUseScript"] = False
        if "logLevel" not in self.config:
            self.config["logLevel"] = "INFO"
        if "cleanUp" not in self.config:
            self.config["cleanUp"] = True
        if "includeSourceFixes" not in self.config:
            self.config["includeSourceFixes"] = False
        if "fvarInstanceAxisDflts" not in self.config:
            self.config["fvarInstanceAxisDflts"] = None
        if "flattenComponents" not in self.config:
            self.config["flattenComponents"] = True
        if "addGftoolsVersion" not in self.config:
            self.config["addGftoolsVersion"] = True
        if "decomposeTransformedComponents" not in self.config:
            self.config["decomposeTransformedComponents"] = True
        if "interpolate" not in self.config:
            self.config["interpolate"] = False
        if "useMutatorMath" not in self.config:
            self.config["useMutatorMath"] = False
        if "checkCompatibility" not in self.config:
            self.config["checkCompatibility"] = True

    def build_variable(self):
        self.mkdir(self.config["vfDir"], clean=True)
        ttFonts = []
        for source in self.config["sources"]:
            args = {"output": ["variable"], "family_name": self.config["familyName"]}
            if not source.endswith(".designspace") and not source.endswith("glyphs"):
                continue
            self.logger.info("Creating variable fonts from %s" % source)
            sourcebase = os.path.splitext(os.path.basename(source))[0]
            args["output_path"] = os.path.join(
                self.config["vfDir"], sourcebase + "-VF.ttf",
            )
            output_files = self.run_fontmake(source, args)
            newname = self.rename_variable(output_files[0])
            ttFont = TTFont(newname)
            ttFonts.append(ttFont)

        if not ttFonts:
            return

        for ttFont in ttFonts:
            self.post_process_variable(ttFont.reader.file.name)
            self.outputs.add(ttFont.reader.file.name)

        ttFonts = [TTFont(f.reader.file.name) for f in ttFonts]
        self.gen_stat(ttFonts)

    def run_fontmake(self, source, args):
        if "output_dir" in args:
            original_output_dir = args["output_dir"]
            tmpdir = tempfile.TemporaryDirectory()
            args["output_dir"] = tmpdir.name

        filters = args.get("filters", [])
        if (
            self.config["flattenComponents"] or
            self.config["decomposeTransformedComponents"]
        ):
            if self.config["flattenComponents"]:
                filters.append(
                    FlattenComponentsFilter()
                )

            if self.config["decomposeTransformedComponents"]:
                filters.append(
                    DecomposeTransformedComponentsFilter()
                )
        # ... will run the filters in the ufo's lib,
        # https://github.com/googlefonts/fontmake/issues/872
        args["filters"] = [...] + filters

        # The following arguments must be determined dynamically.
        if source.endswith((".glyphs", ".designspace", ".glyphspackage")):
            args["expand_features_to_instances"] = self.config.get(
                "expandFeaturesToInstances", True
            )
        # XXX: This will blow up if output formats are mixing TTFs/OTFs.
        is_ttf = args["output"][0] in {"ttf", "ttf-interpolatable", "variable"}
        if "reverseOutlineDirection" in self.config and is_ttf:
            args["reverse_direction"] = self.config["reverseOutlineDirection"]
        if "removeOutlineOverlaps" in self.config:
            args["remove_overlaps"] = self.config["removeOutlineOverlaps"]


        if source.endswith(".glyphs") or source.endswith(".glyphspackage"):
            args["check_compatibility"] = self.config["checkCompatibility"]
            if "glyphData" in self.config:
                args["glyph_data"] = self.config["glyphData"]
            FontProject().run_from_glyphs(source, **args)
        elif source.endswith(".designspace"):
            args["check_compatibility"] = self.config["checkCompatibility"]
            FontProject().run_from_designspace(source, **args)
        elif source.endswith(".ufo"):
            FontProject().run_from_ufos([source], **args)
        else:
            raise ValueError("Can't build from unknown source file: %s" % source)
        if "output_path" in args:
            return [args["output_path"]]
        else:
            # Move it to where it should be...
            file_names = os.listdir(args["output_dir"])
            for file_name in file_names:
                shutil.move(
                    os.path.join(args["output_dir"], file_name), original_output_dir
                )
            tmpdir.cleanup()
            args["output_dir"] = original_output_dir
            return [os.path.join(original_output_dir, x) for x in file_names]

    def rename_variable(self, fontfile):
        font = TTFont(fontfile)
        assert "fvar" in font
        axis_tags = sorted([ax.axisTag for ax in font["fvar"].axes])
        axis_tags = ",".join(axis_tags)
        newname = fontfile.replace("-VF.ttf", "[%s].ttf" % axis_tags)
        os.rename(fontfile, newname)
        return newname

    def gen_stat(self, varfonts):
        if "axisOrder" not in self.config:
            self.config["axisOrder"] = [ax.axisTag for ax in varfonts[0]["fvar"].axes]
        if len(varfonts) > 1 and "ital" not in self.config["axisOrder"]:
            # *Are* any italic? Presumably, but test
            if any(font_is_italic(f) for f in varfonts):
                self.config["axisOrder"].append("ital")

        locations = self.config.get("statFormat4", None)
        if locations and 'stat' not in self.config:
            raise ValueError(
                "Cannot add statFormat 4 axisValues since no stat table has been declared."
            )
        if "stylespaceFile" in self.config and self.config["stylespaceFile"]:
            self.gen_stat_stylespace(self.config["stylespaceFile"], varfonts)
        elif "stat" in self.config:
            gen_stat_tables_from_config(self.config["stat"], varfonts, locations=locations)
        else:
            gen_stat_tables(varfonts)

        for ttFont in varfonts:
            ttFont.save(ttFont.reader.file.name)

    def gen_stat_stylespace(self, stylespaceFile, varfonts):
        import warnings
        warnings.warn(".stylespace files are supported for compatibility but"
            "you are encouraged to specify your STAT table axes in the config file")
        stylespace = statmake.classes.Stylespace.from_file(stylespaceFile)
        for ttFont in varfonts:
            if "ital" in self.config["axisOrder"]:
                if font_is_italic(ttFont):
                    additional_locations = {"Italic": 1}
                else:
                    additional_locations = {"Italic": 0}
            else:
                additional_locations = {}
            statmake.lib.apply_stylespace_to_variable_font(
                stylespace, ttFont, additional_locations
            )

    def build_static(self):
        if self.config["buildOTF"]:
            self.build_a_static_format("otf", self.config["otDir"], self.post_process_static_otf)
        if self.config["buildTTF"]:
            if "instances" in self.config:
                self.instantiate_static_fonts(
                    self.config["ttDir"], self.post_process_static_ttf
                )
            else:
                self.build_a_static_format(
                    "ttf", self.config["ttDir"], self.post_process_static_ttf
                )

    def instantiate_static_fonts(self, directory, postprocessor):
        self.mkdir(directory, clean=True)
        for font in self.config["instances"]:
            varfont_path = os.path.join(self.config['vfDir'], font)
            varfont = TTFont(varfont_path)
            for font, instances in self.config["instances"].items():
                for inst in instances:
                    if 'familyName' in inst:
                        family_name = inst['familyName']
                    else:
                        family_name = self.config['familyName']
                    if "styleName" in inst:
                        style_name = inst['styleName']
                    else:
                        style_name = None

                    static_font = gen_static_font(
                        varfont,
                        axes=inst["coordinates"],
                        family_name=family_name,
                        style_name=style_name,
                    )
                    family_name = font_familyname(static_font)
                    style_name = font_stylename(static_font)
                    dst = os.path.join(
                        directory, f"{family_name}-{style_name}.ttf".replace(" ", "")
                    )
                    static_font.save(dst)
                    postprocessor(dst)
                    self.outputs.add(dst)

    def build_a_static_format(self, format, directory, postprocessor):
        self.mkdir(directory, clean=True)
        for source in self.config["sources"]:
            args = {
                "output": [format],
                "output_dir": directory,
                "optimize_cff": CFFOptimization.SUBROUTINIZE,
            }
            if self.config["buildVariable"] or self.config["interpolate"]:
                args["interpolate"] = True
            if self.config["useMutatorMath"]:
                args["use_mutatormath"] = True
            self.logger.info("Creating static fonts from %s" % source)
            for fontfile in self.run_fontmake(source, args):
                self.logger.info("Created static font %s" % fontfile)
                postprocessor(fontfile)
                self.outputs.add(fontfile)

    def rm(self, fp):
        if os.path.isdir(fp):
            shutil.rmtree(fp, ignore_errors=True)
        elif os.path.isfile(fp):
            os.remove(fp)

    def mkdir(self, directory, clean=False):
        if clean:
            self.rm(directory)
        os.makedirs(directory)

    def post_process(self, filename):
        self.logger.info("Postprocessing font %s" % filename)
        self.set_version(filename)
        font = TTFont(filename)
        font = fix_font(
            font,
            include_source_fixes=self.config["includeSourceFixes"],
            fvar_instance_axis_dflts=self.config["fvarInstanceAxisDflts"]
        )
        font.save(filename)

    def post_process_ttf(self, filename):
        self.logger.debug("Deprecated method .post_process_ttf called, update code to use .post_process_static_ttf")
        self.post_process_static_ttf(filename)

    def post_process_static_otf(self, filename):
        if self.config["autohintOTF"]:
            self.logger.debug("Autohinting")
            otfautohint([filename])
        self.post_process(filename)

    def post_process_static_ttf(self, filename):
        if self.config["autohintTTF"]:
            self.logger.debug("Autohinting")
            autohint(filename, filename, add_script=self.config["ttfaUseScript"])
        if "vttSources" in self.config:
            self.build_vtt(self.config['ttDir'], filename)
        self.post_process(filename)
        self.build_webfont(filename)

    def post_process_variable(self, filename):
        # We don't currently emit variable OTFs, but if we ever do,
        # this will suddenly work!
        if self.config["autohintOTF"] and "glyf" not in TTFont(filename):
            self.logger.debug("Autohinting")
            otfautohint([filename])
        if "vttSources" in self.config:
            self.build_vtt(self.config['vfDir'], filename)
        self.post_process(filename)
        self.build_webfont(filename)

    def build_webfont(self, filename):
        if self.config["buildWebfont"]:
            self.logger.debug("Building webfont")
            woff2_main(["compress", filename])
            self.move_webfont(filename)

    def set_version(self, filename):
        if "version" not in self.config and not self.config["addGftoolsVersion"]:
            return
        fv = FontVersion(filename)
        if "version" in self.config:
            fv.set_version_number(self.config["version"])
        if self.config["addGftoolsVersion"]:
            fv.version_string_parts.append(f"gftools[{gftools.__version__}]")
        fv.write_version_string()


    def build_vtt(self, font_dir, font):
        font = os.path.basename(font)
        if font not in self.config["vttSources"]:
            return
        vtt_source = self.config['vttSources'][font]
        if font not in os.listdir(font_dir):
            return
        self.logger.debug(f"Compiling hint file {vtt_source} into {font}")
        font_path = os.path.join(font_dir, font)
        font = TTFont(font_path)
        merge_vtt_hinting(font, vtt_source, keep_cvar=True)
        compile_vtt_hinting(font, ship=True)

        # Add a gasp table which is optimised for VTT hinting
        # https://googlefonts.github.io/how-to-hint-variable-fonts/
        gasp_tbl = newTable("gasp")
        gasp_tbl.gaspRange = {8: 10, 65535: 15}
        gasp_tbl.version = 1
        font['gasp'] = gasp_tbl
        fix_hinted_font(font)
        font.save(font.reader.file.name)

    def move_webfont(self, filename):
        woff_dir = self.config["woffDir"]
        ttf_dir = self.config["ttDir"]
        var_dir = self.config["vfDir"]

        if not os.path.exists(self.config["woffDir"]):
            self.mkdir(self.config["woffDir"])

        src = filename.replace(".ttf", ".woff2")
        dst = src
        for p in (woff_dir, ttf_dir, var_dir):
            dst = dst.replace(p, woff_dir)

        shutil.move(src, dst)


def main(args=None):
    parser = argparse.ArgumentParser(
        description=("Build a font family"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="#"*79 + "\n" + __doc__,
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Show extra debugging information",
    )
    parser.add_argument("--family-name", help="Font family name")
    parser.add_argument(
        "--no-autohint",
        action="store_true",
        default=False,
        help="Don't run ttfautohint on static TTFs",
    )
    parser.add_argument("--stylespace", help="Path to a statmake stylespace file")

    parser.add_argument(
        "--no-clean-up",
        action="store_true",
        default=False,
        help="Do not remove temporary files (instance_ufos/)")

    parser.add_argument("file", nargs="+", help="YAML build config file *or* source files")

    parser.add_argument("--dump-config", type=str, help="Config file to generate")

    args = parser.parse_args(args)

    builder_class = GFBuilder

    try:
        if platform.system() != "Windows":
            from gftools.builder._ninja import NinjaBuilder

            builder_class = NinjaBuilder
    except ImportError as e:
        pass

    if len(args.file) == 1 and (
        args.file[0].endswith(".yaml") or args.file[0].endswith(".yml")
    ):
        builder_args = dict(configfile=args.file[0])
    else:
        config={"sources": args.file}
        if args.stylespace:
            config["stylespaceFile"] = args.stylespace
        if args.family_name:
            config["familyName"] = args.family_name
        builder_args = dict(config=config)

    builder = builder_class(**builder_args)

    if args.no_autohint:
        builder.config["autohintTTF"] = False
        builder.config["autohintOTF"] = False

    if args.no_clean_up:
        builder.config["cleanUp"] = False

    if args.debug:
        builder.config["logLevel"] = "DEBUG"

    if args.dump_config:
        import sys
        import yaml

        with open(args.dump_config, "w") as fp:
            config= {k: v for (k, v) in builder.config.items() if v is not None}
            fp.write(yaml.dump(config, Dumper=yaml.SafeDumper))
        sys.exit()

    try:
        builder.build()
    except NotImplementedError:
        builder = GFBuilder(**builder_args)
        builder.build()

if __name__ == "__main__":
    main()
