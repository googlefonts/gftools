"""Ninja file writer for orchestrating font builds"""
from ninja.ninja_syntax import Writer
import ninja
import glyphsLib
from glyphsLib.builder.builders import UFOBuilder
import sys
import ufoLib2
import yaml
import os
import shutil
from gftools.builder import GFBuilder
from fontTools.designspaceLib import (
    DesignSpaceDocument,
    SourceDescriptor,
    InstanceDescriptor,
)
from pathlib import Path

UNSUPPORTED = ["stylespaceFile", "statFormat4", "ttfaUseScript", "vttSources"]


class NinjaBuilder(GFBuilder):
    def __init__(self, **kwargs):
        self.old_cwd = os.getcwd()
        super().__init__(**kwargs)

    def build(self):
        # In some cases we want to fall back to GFBuilder
        for unsupported_key in UNSUPPORTED:
            if self.config.get(unsupported_key):
                self.logger.error(
                    "%s configuration parameter not supported by ninja builder, "
                    "falling back to classic GFBuilder" % unsupported_key
                )
                os.chdir(self.old_cwd)
                raise NotImplementedError()

        self.w = Writer(open("build.ninja", "w"))
        self.temporaries = []
        self.setup_rules()
        self.get_designspaces()

        if self.config["buildVariable"]:
            self.build_variable()
            # transfer vf vtt hints now in case static fonts are instantiated
            if "vttSources" in self.config:
                self.build_vtt(self.config["vfDir"])
        if self.config["buildStatic"]:
            self.build_static()
            if "vttSources" in self.config:
                self.build_vtt(self.config["ttDir"])
        self.w.close()

        ninja_args = []
        if self.config["logLevel"] == "DEBUG":
            ninja_args = ["-v", "-j", "1"]

        errcode = ninja._program("ninja", ninja_args)

        # Tidy up stamp files
        for temporary in self.temporaries:
            if os.path.exists(temporary):
                os.remove(temporary)

        # Clean up temp build files
        search_directory = os.getcwd()
        target_names = ["build.ninja", ".ninja_log", "instance_ufo", "master_ufo"]
        for root, dirs, files in os.walk(search_directory, topdown=False):
            for file in files:
                if file in target_names:
                    file_path = os.path.join(root, file)
                    os.remove(file_path)
                    print(f"Removed file: {file_path}")
            for dir_name in dirs:
                if dir_name in target_names:
                    dir_path = os.path.join(root, dir_name)
                    shutil.rmtree(dir_path)
                    print(f"Removed directory: {dir_path}")

        print("Done building fonts!")

        if errcode:
            sys.exit(errcode)

    def setup_rules(self):
        self.w.comment("Rules")
        if self.config["logLevel"] == "DEBUG":
            args = {"pool": "console"}
        else:
            args = {}
        self.w.newline()
        self.w.comment("Convert glyphs file to UFO")
        self.w.rule(
            "glyphs2ufo", "fontmake -o ufo --instance-dir instance_ufo -g $in", **args
        )

        if self.config["buildVariable"]:
            self.w.comment("Build a variable font from Designspace")
            self.w.rule(
                "variable", "fontmake -o variable -m $in $fontmake_args", **args
            )

        self.w.comment("Build a set of instance UFOs from Designspace")
        self.w.rule("instanceufo", "fontmake -i -o ufo -m $in $fontmake_args", **args)

        self.w.comment("Build a TTF file from a UFO")
        self.w.rule(
            "buildttf",
            "fontmake -o ttf -u $in $fontmake_args --output-path $out",
            **args,
        )

        self.w.comment("Build an OTF file from a UFO")
        self.w.rule(
            "buildotf",
            "fontmake -o otf -u $in $fontmake_args --output-path $out",
            **args,
        )

        self.w.comment("Add a STAT table to a set of variable fonts")
        self.w.rule(
            "genstat",
            "gftools-gen-stat --inplace $other_args -- $in  && touch $stampfile",
            **args,
        )

        self.w.comment("Run the font fixer in-place and touch a stamp file")
        self.w.rule(
            "fix",
            "gftools-fix-font -o $in $fixargs $in && touch $in.fixstamp",
            **args,
        )

        self.w.comment("Run the ttfautohint in-place and touch a stamp file")
        self.w.rule(
            "autohint",
            "gftools-autohint $in && touch $in.autohintstamp",
            **args,
        )

        self.w.comment("Run otfautohint in-place and touch a stamp file")
        self.w.rule(
            "autohint-otf",
            "otfautohint $in && touch $in.autohintstamp",
            **args,
        )

        self.w.comment("Create a web font")
        self.w.rule("webfont", f"fonttools ttLib.woff2 compress -o $out $in", **args)

        self.w.newline()

    def get_designspaces(self):
        self.designspaces = []
        for source in self.config["sources"]:
            if source.endswith(".glyphs") or source.endswith(".glyphspackage"):
                builder = UFOBuilder(
                    glyphsLib.load(source), instance_dir="../instance_ufo"
                )
                # This is a sneaky way of skipping the hard work of
                # converting all the glyphs and stuff, and just gettting
                # a minimal designspace
                builder.to_ufo_groups = (
                    builder.to_ufo_kerning
                ) = builder.to_ufo_layers = lambda: True

                designspace = builder.designspace
                designspace_path = os.path.join("master_ufo", designspace.filename)
                os.makedirs(os.path.dirname(designspace_path), exist_ok=True)
                designspace.write(designspace_path)
                self.w.comment("Convert glyphs source to designspace")
                designspace_and_ufos = [designspace_path] + list(
                    set(
                        [
                            os.path.join("master_ufo", m.filename)
                            for m in designspace.sources
                        ]
                    )
                )
                self.w.build(designspace_and_ufos, "glyphs2ufo", source)
            elif source.endswith(".ufo"):
                # Wrap this in a basic designspace
                designspace_path = source.replace(".ufo", ".designspace")
                ufo = ufoLib2.Font.open(source)

                designspace = DesignSpaceDocument()
                source_descriptor = SourceDescriptor()
                source_descriptor.path = source

                instance = InstanceDescriptor()
                instance.styleName = ufo.info.styleName
                instance.familyName = ufo.info.familyName
                instance.path = os.path.join(
                    "instance_ttf",
                    ufo.info.familyName + "-" + ufo.info.styleName + ".ufo",
                ).replace(" ", "")

                designspace.addSource(source_descriptor)
                designspace.addInstance(instance)
                designspace.write(designspace_path)
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
            my_args.append("--output-dir " + args["output_dir"])
        if "output_path" in args:
            my_args.append("--output-path " + args["output_path"])
        if not self.config.get("removeOutlineOverlaps", True):
            my_args.append("--keep-overlaps")
        if not self.config.get("reverseOutlineDirection", True):
            my_args.append("--keep-direction")
        return " ".join(my_args)

    def build_variable(self):
        targets = []
        self.w.newline()
        self.w.comment("VARIABLE FONTS")
        self.w.newline()
        for (designspace_path, designspace) in self.designspaces:
            axis_tags = sorted([ax.tag for ax in designspace.axes])
            axis_tags = ",".join(axis_tags)
            target = os.path.join(
                self.config["vfDir"],
                Path(designspace_path).stem + "[%s].ttf" % axis_tags,
            )
            self.w.build(
                target,
                "variable",
                designspace_path,
                variables={
                    "fontmake_args": self.fontmake_args({"output_path": target})
                },
            )
            targets.append(target)
        self.w.newline()
        stampfile = self.gen_stat(axis_tags, targets)
        # We post process each variable font after generating the STAT tables
        # because these tables are needed in order to fix the name tables.
        self.w.comment("Variable font post-processing")
        for t in targets:
            self.post_process_variable(t, implicit=stampfile)

    def gen_stat(self, axis_tags, targets):
        self.w.comment("Generate STAT tables")
        if "axisOrder" not in self.config:
            self.config["axisOrder"] = axis_tags.split(",")
            # Janky "is-italic" test. To strengthen this up we should look inside
            # the source files and check their stylenames.
            if any("italic" in x[0].lower() for x in self.designspaces):
                self.config["axisOrder"].append("ital")
        other_args = ""
        stampfile = targets[0] + ".statstamp"
        if "stat" in self.config:
            statfile = targets[0] + ".stat.yaml"
            os.makedirs(os.path.dirname(statfile), exist_ok=True)
            open(statfile, "w").write(yaml.dump(self.config["stat"]))
            other_args = f"--src {statfile}"
        if "stylespaceFile" in self.config or "statFormat4" in self.config:
            raise ValueError(
                "Stylespace files / statFormat4 not supported in Ninja mode"
            )
            # Because gftools-gen-stat doesn't seem to support it?
        self.temporaries.append(stampfile)
        self.w.build(
            stampfile,
            "genstat",
            targets,
            variables={
                "other_args": other_args,
                "stampfile": stampfile,
            },
        )
        self.w.newline()
        return stampfile

    def post_process(self, file, implicit=None):
        variables = {}
        if self.config["includeSourceFixes"]:
            variables = {"fixargs": "--include-source-fixes"}
        self.temporaries.append(file + ".fixstamp")
        self.w.build(
            file + ".fixstamp", "fix", file, implicit=implicit, variables=variables
        )

    def _instance_ufo_filenames(self, path, designspace):
        instance_filenames = []
        for instance in designspace.instances:
            fn = instance.filename
            ufo = Path(path).parent / fn
            instance_filenames.append(ufo)
        return instance_filenames

    def build_static(self):
        # Let's make our interpolated UFOs.
        self.w.newline()
        self.w.comment("STATIC FONTS")
        self.w.newline()
        for (path, designspace) in self.designspaces:
            self.w.comment(f"  Interpolate UFOs for {os.path.basename(path)}")
            instances = self._instance_ufo_filenames(path, designspace)
            if not instances:
                continue

            self.w.build(
                [str(i) for i in instances],
                "instanceufo",
                path,
            )
            self.w.newline()

        return GFBuilder.build_static(self)

    def instantiate_static_fonts(self, directory, postprocessor):
        pass

    def build_a_static_format(self, format, directory, postprocessor):
        self.w.comment(f"Build {format} format")
        self.w.newline()
        if format == "ttf":
            target_dir = self.config["ttDir"]
        else:
            target_dir = self.config["otDir"]
        targets = []
        for (path, designspace) in self.designspaces:
            self.w.comment(f" {path}")
            for ufo in self._instance_ufo_filenames(path, designspace):
                target = str(Path(target_dir) / ufo.with_suffix(f".{format}").name)
                self.w.build(
                    target,
                    "build" + format,
                    str(ufo),
                    variables={
                        "fontmake_args": self.fontmake_args({"output_path": target})
                    },
                )
                targets.append(target)
        self.w.newline()
        self.w.comment(f"Post-processing {format}s")
        for t in targets:
            postprocessor(t)
        self.w.newline()

    def post_process_static_ttf(self, filename):
        if self.config["autohintTTF"]:
            if self.config["ttfaUseScript"]:
                raise NotImplementedError("ttaUseScript not supported in ninja mode")
            self.w.build(filename + ".autohintstamp", "autohint", filename)
            self.temporaries.append(filename + ".autohintstamp")
            self.post_process(filename, implicit=filename + ".autohintstamp")
        else:
            self.post_process(filename)
        if self.config["buildWebfont"]:
            webfont_filename = filename.replace(".ttf", ".woff2").replace(
                self.config["ttDir"], self.config["woffDir"]
            )
            self.w.build(
                webfont_filename, "webfont", filename, implicit=filename + ".fixstamp"
            )

    def post_process_static_otf(self, filename):
        if self.config["autohintOTF"]:
            self.w.build(filename + ".autohintstamp", "autohint-otf", filename)
            self.temporaries.append(filename + ".autohintstamp")
            self.post_process(filename, implicit=filename + ".autohintstamp")
        else:
            self.post_process(filename)

    def post_process_variable(self, filename, implicit=None):
        self.post_process(filename, implicit=implicit)
        if self.config["buildWebfont"]:
            webfont_filename = filename.replace(".ttf", ".woff2").replace(
                self.config["vfDir"], self.config["woffDir"]
            )
            self.w.build(
                webfont_filename, "webfont", filename, implicit=filename + ".fixstamp"
            )

    def build_vtt(self, font_dir):
        # This should be an external gftool
        raise NotImplementedError


if __name__ == "__main__":
    NinjaBuilder(sys.argv[1]).build()
