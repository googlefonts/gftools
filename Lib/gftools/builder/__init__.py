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

To build a font family from the command line, use:

    gftools builder path/to/config.yaml

The config file may contain the following keys. The ``sources`` key is
required, all others have sensible defaults:

* ``sources``: Required. An array of Glyphs, UFO or designspace source files.
* ``logLevel``: Debugging log level. Defaults to ``INFO``.
* ``stylespaceFile``: A statmake ``.stylespace`` file.
* ``stat``: A STAT table configuration. This may be either a list of axes and
    values as demonstrated above, or a dictionary mapping each source file to a
    per-source list. If neither ``stylespaceFile`` or ``stat`` are provided, a
    STAT table is generated automatically using ``gftools.stat``.
* ``buildVariable``: Build variable fonts. Defaults to true.
* ``buildStatic``: Build static fonts. Defaults to true.
* ``buildWebfont``: Build WOFF2 fonts. Defaults to ``$buildStatic``.
* ``outputDir``: Where to put the fonts. Defaults to ``../fonts/``
* ``vfDir``: Where to put variable fonts. Defaults to ``$outputDir/variable``.
* ``ttDir``: Where to put TrueType static fonts. Defaults to ``$outputDir/ttf``.
* ``otDir``: Where to put CFF static fonts. Defaults to ``$outputDir/otf``.
* ``woffDir``: Where to put WOFF2 static fonts. Defaults to ``$outputDir/webfonts``.
* ``cleanUp`: Whether or not to remove temporary files. Defaults to ``true``.
* ``autohintTTF`: Whether or not to autohint TTF files. Defaults to ``true``.
* ``axisOrder``: STAT table axis order. Defaults to fvar order.
* ``familyName``: Family name for variable fonts. Defaults to family name of first source file.

"""

from fontTools import designspaceLib
from fontTools.ttLib import TTFont
from fontmake.font_project import FontProject
from ufo2ft import CFFOptimization
from gftools.fix import fix_font
from gftools.stat import gen_stat_tables, gen_stat_tables_from_config
from gftools.utils import font_is_italic
from fontTools.otlLib.builder import buildStatTable
import statmake.classes
import statmake.lib
from babelfont import Babelfont
import sys
import os
import shutil
import glyphsLib
import tempfile
from fontTools.ttLib.woff2 import main as woff2_main
import logging
import yaml


class GFBuilder:
    def __init__(self, configfile=None, config=None):
        if configfile:
            self.config = yaml.load(open(configfile), Loader=yaml.SafeLoader)
            if os.path.dirname(configfile):
                os.chdir(os.path.dirname(configfile))
        else:
            self.config = config
        self.masters = {}
        self.logger = logging.getLogger("GFBuilder")
        self.fill_config_defaults()

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
                "cu2qu.ufo",
                "glyphsLib.builder.builders.UFOBuilder",
            ]:
                logging.getLogger(irrelevant).setLevel(logging.ERROR)
        if self.config["buildVariable"]:
            self.build_variable()
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

    def load_masters(self):
        if self.masters:
            return
        for src in self.config["sources"]:
            if src.endswith("glyphs"):
                gsfont = glyphsLib.GSFont(src)
                self.masters[src] = []
                for master in gsfont.masters:
                    self.masters[src].append(Babelfont.open(src, master=master.name))
            elif src.endswith("designspace"):
                continue
            else:
                self.masters[src] = [Babelfont.open(src)]

    def fill_config_defaults(self):
        if "familyName" not in self.config:
            self.logger.info("Deriving family name (this takes a while)")
            if  self.config["sources"][0].endswith("designspace"):
                designspace = designspaceLib.DesignSpaceDocument.fromfile(self.config["sources"][0])
                self.config["familyName"] = designspace.sources[0].familyName
            else:
                self.load_masters()

                familynames = set()
                for masters in self.masters.values():
                    for master in masters:
                        familynames.add(master.info.familyName)

                if len(familynames) != 1:
                    raise ValueError(
                        "Inconsistent family names in sources (%s). Set familyName in config instead"
                        % familynames
                    )
                self.config["familyName"] = list(familynames)[0]
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
        if "buildWebfont" not in self.config:
            self.config["buildWebfont"] = self.config["buildStatic"]
        if "autohintTTF" not in self.config:
            self.config["autohintTTF"] = True
        if "logLevel" not in self.config:
            self.config["logLevel"] = "INFO"
        if "cleanUp" not in self.config:
            self.config["cleanUp"] = True
        if "includeSourceFixes" not in self.config:
            self.config["includeSourceFixes"] = False

    def build_variable(self):
        self.mkdir(self.config["vfDir"], clean=True)
        args = {"output": ["variable"], "family_name": self.config["familyName"]}
        ttFonts = []
        for source in self.config["sources"]:
            if not source.endswith(".designspace") and not source.endswith("glyphs"):
                continue
            self.logger.info("Creating variable fonts from %s" % source)
            sourcebase = os.path.splitext(os.path.basename(source))[0]
            args["output_path"] = os.path.join(
                self.config["vfDir"], sourcebase + "-VF.ttf",
            )
            output_files = self.run_fontmake(source, args)
            newname = self.rename_variable(output_files[0])
            self.post_process(newname)
            ttFont = TTFont(newname)
            ttFonts.append(ttFont)
        self.gen_stat(ttFonts)

    def run_fontmake(self, source, args):
        if "output_dir" in args:
            original_output_dir = args["output_dir"]
            tmpdir = tempfile.TemporaryDirectory()
            args["output_dir"] = tmpdir.name

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
        if "axisOrder" not in self.config:
            font = TTFont(fontfile)
            self.config["axisOrder"] = [ax.axisTag for ax in font["fvar"].axes]
        axes = ",".join(self.config["axisOrder"])
        newname = fontfile.replace("-VF.ttf", "[%s].ttf" % axes)
        os.rename(fontfile, newname)
        return newname

    def gen_stat(self, varfonts):
        if len(varfonts) > 1 and "ital" not in self.config["axisOrder"]:
            # *Are* any italic? Presumably, but test
            if any(font_is_italic(f) for f in varfonts):
                self.config["axisOrder"].append("ital")

        if "stylespaceFile" in self.config and self.config["stylespaceFile"]:
            self.gen_stat_stylespace(self.config["stylespaceFile"], varfonts)
        elif "stat" in self.config:
            gen_stat_tables_from_config(self.config["stat"], varfonts)
        else:
            gen_stat_tables(varfonts, self.config["axisOrder"])

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
        self.build_a_static_format("otf", self.config["otDir"], self.post_process)
        if self.config["buildWebfont"]:
            self.mkdir(self.config["woffDir"], clean=True)
        self.build_a_static_format("ttf", self.config["ttDir"], self.post_process_ttf)
        if self.config["cleanUp"]:
            self.rmdir("instance_ufos")

    def build_a_static_format(self, format, directory, postprocessor):
        self.mkdir(directory, clean=True)
        args = {
            "output": [format],
            "output_dir": directory,
            "optimize_cff": CFFOptimization.SUBROUTINIZE,
        }
        for source in self.config["sources"]:
            if source.endswith("ufo"):
                if "interpolate" in args:
                    del args["interpolate"]
            else:
                args["interpolate"] = True
            self.logger.info("Creating static fonts from %s" % source)
            for fontfile in self.run_fontmake(source, args):
                self.logger.info("Created static font %s" % fontfile)
                postprocessor(fontfile)

    def rmdir(self, directory):
        shutil.rmtree(directory, ignore_errors=True)

    def mkdir(self, directory, clean=False):
        if clean:
            self.rmdir(directory)
        os.makedirs(directory)

    def post_process(self, filename):
        self.logger.info("Postprocessing font %s" % filename)
        font = TTFont(filename)
        fix_font(font, include_source_fixes=self.config["includeSourceFixes"])
        font.save(filename)

    def post_process_ttf(self, filename):
        if self.config["autohintTTF"]:
            self.logger.debug("Autohinting")
            self.autohint(filename)
        self.post_process(filename)
        if self.config["buildWebfont"]:
            self.logger.debug("Building webfont")
            woff2_main(["compress", filename])
            self.move_webfont(filename)

    def autohint(self, filename):
        from ttfautohint.options import parse_args as ttfautohint_parse_args
        from ttfautohint import ttfautohint

        ttfautohint(**ttfautohint_parse_args([filename, filename]))

    def move_webfont(self, filename):
        wf_filename = filename.replace(".ttf", ".woff2")
        os.rename(
            wf_filename,
            wf_filename.replace(self.config["ttDir"], self.config["woffDir"]),
        )


if __name__ == "__main__":
    GFBuilder(sys.argv[1]).build()
