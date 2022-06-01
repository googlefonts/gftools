"""Ninja file writer for orchestrating font builds"""
from ninja_syntax import Writer
import glyphsLib
import sys
import ufoLib2
import os
from gftools.builder import GFBuilder
from fontTools.designspaceLib import DesignSpaceDocument
from pathlib import Path


class NinjaBuilder(GFBuilder):
    def build(self):
        self.w = Writer(open("build.ninja", "w"))
        self.setup_rules()
        self.get_designspaces()

        if self.config["buildVariable"]:
            self.build_variable()
            # transfer vf vtt hints now in case static fonts are instantiated
            if "vttSources" in self.config:
                self.build_vtt(self.config['vfDir'])
        if self.config["buildStatic"]:
            self.build_static()
            if "vttSources" in self.config:
                self.build_vtt(self.config['ttDir'])
        self.w.close()

    def setup_rules(self):
        self.w.rule("glyphs2ufo", "fontmake -o ufo -g $in")

        if self.config["buildVariable"]:
          self.w.rule("variable", "fontmake -o variable -m $in $fontmake_args")

        self.w.rule("instanceufo", "fontmake -i -o ufo -m $in $fontmake_args")
        self.w.rule("instancettf", "fontmake -o ttf -u $in $fontmake_args")
        self.w.rule("instanceotf", "fontmake -o otf -u $in $fontmake_args")
        self.w.rule("genstat", "gftools-gen-stat.py --inplace $other_args --axis-order $axis_order -- $in ; touch genstat.stamp")
        if self.config["includeSourceFixes"]:
            fixargs = "--include-source-fixes"
        else:
            fixargs = ""
        self.w.rule("fix", f"gftools-fix-font.py -o $in {fixargs} $in; touch $in.fixstamp")
        self.w.newline()

    def get_designspaces(self):
        self.designspaces = []
        for source in self.config["sources"]:
            if source.endswith(".glyphs"):
              # Do the conversion once, so we know what the instances and filenames are
              designspace = glyphsLib.to_designspace(
                        glyphsLib.GSFont(source),
                        ufo_module=ufoLib2,
                        generate_GDEF=True,
                        store_editor_state=False,
                        minimal=True,
                    )
              designspace_path = os.path.join("master_ufo", designspace.filename)
              os.makedirs(os.path.dirname(designspace_path), exist_ok=True)
              designspace.write(designspace_path)
              self.w.build(designspace_path, "glyphs2ufo", source)
            else:
              designspace_path = source
              designspace = DesignSpaceDocument.fromfile(designspace_path)
            self.designspaces.append((designspace_path, designspace))
        self.w.newline()

    def fontmake_args(self, args):
        my_args = []
        my_args.append("--filter ...")
        if self.config["flattenComponents"]:
            my_args.append("--filter FlattenComponentsFilter")
        if self.config["decomposeTransformedComponents"]:
            my_args.append("--filter DecomposeTransformedComponentsFilter")
        if "output_dir" in args:
            my_args.append("--output-dir "+args["output_dir"])
        if "output_path" in args:
            my_args.append("--output-path "+args["output_path"])
        return " ".join(my_args)

    def build_variable(self):
        targets = []
        for (designspace_path, designspace) in self.designspaces:
            axis_tags = sorted([ax.tag for ax in designspace.axes])
            axis_tags = ",".join(axis_tags)
            target = os.path.join(self.config["vfDir"], Path(designspace_path).stem + "[%s].ttf" % axis_tags)
            self.w.build(target, "variable", designspace_path, variables={"fontmake_args": self.fontmake_args({"output_path": target})})
            targets.append(target)
        self.gen_stat(axis_tags, targets)
        # We post process each variable font after generating the STAT tables
        # because these tables are needed in order to fix the name tables.
        for t in targets:
            self.post_process(t)

    def gen_stat(self, axis_tags, targets):
        if "axisOrder" not in self.config:
            self.config["axisOrder"] = axis_tags.split(",")
            # Janky "is-italic" test. To strengthen this up we should look inside
            # the source files and check their stylenames.
            if any("italic" in x[0].lower() for x in self.designspaces):
                self.config["axisOrder"].append("ital")
        other_args = ""
        if "stat" in self.config:
            other_args = f"--src {self.config['stat']}"
        if "stylespaceFile" in self.config or "statFormat4" in self.config:
            raise ValueError("Stylespace files / statFormat4 not supported in Ninja mode")
            # Because gftools-gen-stat doesn't seem to support it?
        self.w.build("genstat.stamp", "genstat", targets, variables={"axis_order": self.config["axisOrder"], "other_args": other_args})

    def post_process(self, file):
        self.w.build(file+".fixstamp", "fix", file)

    def build_static(self):
        pass
    #     if self.config["buildOTF"]:
    #         self.build_a_static_format("otf", self.config["otDir"], self.post_process)
    #     if self.config["buildWebfont"]:
    #         self.mkdir(self.config["woffDir"], clean=True)
    #     if self.config["buildTTF"]:
    #         if "instances" in self.config:
    #             self.instantiate_static_fonts(
    #                 self.config["ttDir"], self.post_process_ttf
    #             )
    #         else:
    #             self.build_a_static_format(
    #                 "ttf", self.config["ttDir"], self.post_process_ttf
    #             )

    # def instantiate_static_fonts(self, directory, postprocessor):
    #     self.mkdir(directory, clean=True)
    #     for font in self.config["instances"]:
    #         varfont_path = os.path.join(self.config['vfDir'], font)
    #         varfont = TTFont(varfont_path)
    #         for font, instances in self.config["instances"].items():
    #             for inst in instances:
    #                 if 'familyName' in inst:
    #                     family_name = inst['familyName']
    #                 else:
    #                     family_name = self.config['familyName']
    #                 if "styleName" in inst:
    #                     style_name = inst['styleName']
    #                 else:
    #                     style_name = None

    #                 static_font = gen_static_font(
    #                     varfont,
    #                     axes=inst["coordinates"],
    #                     family_name=family_name,
    #                     style_name=style_name,
    #                 )
    #                 family_name = font_familyname(static_font)
    #                 style_name = font_stylename(static_font)
    #                 dst = os.path.join(
    #                     directory, f"{family_name}-{style_name}.ttf".replace(" ", "")
    #                 )
    #                 static_font.save(dst)
    #                 postprocessor(dst)
    #                 self.outputs.add(dst)

    # def build_a_static_format(self, format, directory, postprocessor):
    #     self.mkdir(directory, clean=True)
    #     for source in self.config["sources"]:
    #         args = {
    #             "output": [format],
    #             "output_dir": directory,
    #             "optimize_cff": CFFOptimization.SUBROUTINIZE,
    #         }
    #         if not source.endswith("ufo"):
    #             args["interpolate"] = True
    #         self.logger.info("Creating static fonts from %s" % source)
    #         for fontfile in self.run_fontmake(source, args):
    #             self.logger.info("Created static font %s" % fontfile)
    #             postprocessor(fontfile)
    #             self.outputs.add(fontfile)

    # def post_process_ttf(self, filename):
    #     if self.config["autohintTTF"]:
    #         self.logger.debug("Autohinting")
    #         autohint(filename, filename, add_script=self.config["ttfaUseScript"])
    #     self.post_process(filename)
    #     if self.config["buildWebfont"]:
    #         self.logger.debug("Building webfont")
    #         woff2_main(["compress", filename])
    #         self.move_webfont(filename)

    def build_vtt(self, font_dir):
        raise NotImplementedError
    #     for font, vtt_source in self.config['vttSources'].items():
    #         if font not in os.listdir(font_dir):
    #             continue
    #         self.logger.debug(f"Compiling hint file {vtt_source} into {font}")
    #         font_path = os.path.join(font_dir, font)
    #         font = TTFont(font_path)
    #         merge_vtt_hinting(font, vtt_source, keep_cvar=True)
    #         compile_vtt_hinting(font, ship=True)

    #         # Add a gasp table which is optimised for VTT hinting
    #         # https://googlefonts.github.io/how-to-hint-variable-fonts/
    #         gasp_tbl = newTable("gasp")
    #         gasp_tbl.gaspRange = {8: 10, 65535: 15}
    #         gasp_tbl.version = 1
    #         font['gasp'] = gasp_tbl
    #         font.save(font.reader.file.name)

    # def move_webfont(self, filename):
    #     wf_filename = filename.replace(".ttf", ".woff2")
    #     os.rename(
    #         wf_filename,
    #         wf_filename.replace(self.config["ttDir"], self.config["woffDir"]),
    #     )


if __name__ == "__main__":
    NinjaBuilder(sys.argv[1]).build()
