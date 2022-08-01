"""Config-driven font project builder.

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
"""

from fontmake.font_project import FontProject
from fontTools import designspaceLib
from fontTools.otlLib.builder import buildStatTable
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.woff2 import main as woff2_main
from gftools.builder.schema import schema
from gftools.builder.autohint import autohint
from gftools.fix import fix_font
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
import difflib
import glyphsLib
from defcon import Font
import logging
import os
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
            if "vttSources" in self.config:
                self.build_vtt(self.config['vfDir'])
        if self.config["buildStatic"]:
            self.build_static()
            if "vttSources" in self.config:
                self.build_vtt(self.config['ttDir'])
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
            self.config["buildVariable"] = True
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
        if "decomposeTransformedComponents" not in self.config:
            self.config["decomposeTransformedComponents"] = True

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

        self.gen_stat(ttFonts)
        # We post process each variable font after generating the STAT tables
        # because these tables are needed in order to fix the name tables.
        for ttFont in ttFonts:
            self.post_process(ttFont.reader.file.name)
            self.outputs.add(ttFont.reader.file.name)

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

        if source.endswith(".glyphs"):
            FontProject().run_from_glyphs(source, **args)
        elif source.endswith(".designspace"):
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
            self.build_a_static_format("otf", self.config["otDir"], self.post_process)
        if self.config["buildWebfont"]:
            self.mkdir(self.config["woffDir"], clean=True)
        if self.config["buildTTF"]:
            if "instances" in self.config:
                self.instantiate_static_fonts(
                    self.config["ttDir"], self.post_process_ttf
                )
            else:
                self.build_a_static_format(
                    "ttf", self.config["ttDir"], self.post_process_ttf
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
            if not source.endswith("ufo"):
                args["interpolate"] = True
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
        font = TTFont(filename)
        fix_font(
            font,
            include_source_fixes=self.config["includeSourceFixes"],
            fvar_instance_axis_dflts=self.config["fvarInstanceAxisDflts"]
        )
        font.save(filename)

    def post_process_ttf(self, filename):
        if self.config["autohintTTF"]:
            self.logger.debug("Autohinting")
            autohint(filename, filename, add_script=self.config["ttfaUseScript"])
        self.post_process(filename)
        if self.config["buildWebfont"]:
            self.logger.debug("Building webfont")
            woff2_main(["compress", filename])
            self.move_webfont(filename)

    def build_vtt(self, font_dir):
        for font, vtt_source in self.config['vttSources'].items():
            if font not in os.listdir(font_dir):
                continue
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
            font.save(font.reader.file.name)

    def move_webfont(self, filename):
        wf_filename = filename.replace(".ttf", ".woff2")
        os.rename(
            wf_filename,
            wf_filename.replace(self.config["ttDir"], self.config["woffDir"]),
        )


if __name__ == "__main__":
    GFBuilder(sys.argv[1]).build()
