import copy
import logging
import os
import re
from tempfile import NamedTemporaryFile
from typing import Optional, Tuple

from glyphsLib.builder import UFOBuilder
import yaml
from fontTools.designspaceLib import DesignSpaceDocument, InstanceDescriptor
from strictyaml import load, YAMLValidationError

from gftools.builder.file import File
from gftools.builder.recipeproviders import RecipeProviderBase
from gftools.builder.schema import (
    GOOGLEFONTS_SCHEMA,
    stat_schema,
    stat_schema_by_font_name,
)
from gftools.utils import open_ufo

logger = logging.getLogger("GFBuilder")

Italic = Optional[Tuple[str, float, float]]  # tag, regular value, italic value

# Things not ported from old builder:
#  - cleanup
#  - stylespace (old, replaced by stat)
#  - axisOrder (did not actually do anything)
#  - googleFonts (only used by actions, not builder)
#  - interpolate (always on for statics now)
#  - useMutatorMath (dead in fontmake)

# Taken from gftools-builder
DEFAULTS = {
    "outputDir": "../fonts",
    "vfDir": "$outputDir/variable",
    "ttDir": "$outputDir/ttf",
    "otDir": "$outputDir/otf",
    "woffDir": "$outputDir/webfonts",
    "buildStatic": True,
    "buildOTF": True,
    "buildTTF": True,
    "buildSmallCap": True,
    "autohintTTF": True,
    "autohintOTF": False,
    "ttfaUseScript": False,
    "logLevel": "WARN",
    "cleanUp": True,
    "includeSourceFixes": False,
    "fvarInstanceAxisDflts": None,
    "flattenComponents": True,
    "addGftoolsVersion": True,
    "decomposeTransformedComponents": True,
    "interpolate": False,
    "useMutatorMath": False,
    "checkCompatibility": True,
    "overlaps": "booleanOperations",
    "splitItalic": True,
}


class GFBuilder(RecipeProviderBase):
    schema = GOOGLEFONTS_SCHEMA

    def revalidate(self):
        # Revalidate using our schema
        try:
            load(self.builder._orig_config, self.schema)
        except YAMLValidationError as e:
            raise ValueError("Invalid configuration file") from e

    def write_recipe(self):
        if "instances" in self.config:
            logger.warning(
                "'instances' no longer supported; generate a config with --generate and select the instances you want"
            )
        self.revalidate()
        self.config = {**DEFAULTS, **self.config}
        for field in ["vfDir", "ttDir", "otDir", "woffDir"]:
            self.config[field] = self.config[field].replace(
                "$outputDir", self.config["outputDir"]
            )
        self.config["buildWebfont"] = self.config.get(
            "buildWebfont", self.config.get("buildStatic", True)
        )

        if "stat" in self.config:
            self.statfile = NamedTemporaryFile(delete=False, mode="w+")
            try:
                load(yaml.dump(self.config["stat"]), stat_schema)
            except YAMLValidationError:
                load(yaml.dump(self.config["stat"]), stat_schema_by_font_name)
                if self.config.get("buildSmallCap"):
                    for font in list(self.config["stat"].keys()):
                        scfont = re.sub(r"((?:-Italic)?\[)", r"SC\1", font)
                        self.config["stat"][scfont] = self.config["stat"][font]
            yaml.dump(self.config["stat"], self.statfile)
        else:
            self.statfile = None
        # Find variable fonts
        self.recipe = {}
        self.build_all_variables()
        self.build_all_statics()
        return self.recipe

    def _has_slant_ital(self, source: File) -> Italic:
        if source.is_glyphs:
            tags = [ax.axisTag for ax in source.gsfont.axes]
        elif source.is_designspace:
            tags = [ax.tag for ax in source.designspace.axes]
        else:
            return
        if "ital" in tags:
            slanty_axis = "ital"
        elif "slnt" in tags:
            slanty_axis = "slnt"
        else:
            return
        if source.is_glyphs:
            gsfont = source.gsfont
            builder = UFOBuilder(gsfont, minimal=True)
            builder.to_designspace_axes()
            axes = builder.designspace.axes
        else:
            axes = source.designspace.axes
        wanted = [axis for axis in axes if axis.tag == slanty_axis]
        if slanty_axis == "ital":
            return (slanty_axis, wanted[0].minimum, wanted[0].maximum)
        else:
            # We expect the italic value to have negative slant, so it
            # turns out as the minimum.
            return (slanty_axis, wanted[0].maximum, wanted[0].minimum)

    def _vf_filename(
        self, source, suffix="", extension="ttf", italic_ds=None, roman=False
    ):
        """Determine the file name for a variable font."""
        sourcebase = os.path.splitext(source.basename)[0]
        if source.is_glyphs:
            tags = [ax.axisTag for ax in source.gsfont.axes]
        elif source.is_designspace:
            tags = [ax.tag for ax in source.designspace.axes]
        else:
            raise ValueError("Unknown source type")

        if italic_ds:
            if not roman:
                sourcebase += "-Italic"
            tags.remove(italic_ds[0])
        axis_tags = ",".join(sorted(tags))
        directory = self.config["vfDir"]
        if extension == "woff2":
            directory = self.config["woffDir"]
        if suffix:
            # Put any suffix before the -Italic element
            if "-Italic" in sourcebase:
                sourcebase = sourcebase.replace("-Italic", suffix + "-Italic")
            else:
                sourcebase += suffix

        return os.path.join(directory, f"{sourcebase}[{axis_tags}].{extension}")

    def _static_filename(
        self, instance: InstanceDescriptor, suffix: str = "", extension: str = "ttf"
    ):
        """Determine the file name for a static font."""
        if extension == "ttf":
            outdir = self.config["ttDir"]
        elif extension == "otf":
            outdir = self.config["otDir"]
        elif extension == "woff2":
            outdir = self.config["woffDir"]
        instancebase = os.path.splitext(os.path.basename(instance.filename))[0]
        if suffix:
            # This is horrible; insert the suffix at the end of the family
            # name, before the style name.
            familyname, path = instancebase.rsplit("-", 1)
            instancebase = familyname + suffix + "-" + path

        return os.path.join(outdir, f"{instancebase}.{extension}")

    def fontmake_args(self, source, variable=False):
        args = "--filter ... "
        if self.config.get("flattenComponents", True):
            args += " --filter FlattenComponentsFilter"
        if self.config.get("decomposeTransformedComponents", True):
            args += " --filter DecomposeTransformedComponentsFilter"

        if self.config.get("logLevel") != "WARN":
            args += " --verbose " + self.config["logLevel"]
        if self.config.get("reverseOutlineDirection", True) is False:
            args += " --keep-direction"
        if self.config.get("removeOutlineOverlaps") is False:
            args += " --keep-overlaps"
        if self.config.get("expandFeaturesToInstances"):
            args += " --expand-features-to-instances"
        if self.config.get("extraFontmakeArgs") is not None:
            args += " " + str(self.config["extraFontmakeArgs"])
        if variable:
            if self.config.get("checkCompatibility") == False:
                args += " --no-check-compatibility"
            if self.config.get("extraVariableFontmakeArgs") is not None:
                args += " " + str(self.config["extraVariableFontmakeArgs"])
            if source.is_glyphs:
                for gd in self.config.get("glyphData", []):
                    args += " --glyph-data " + gd
        else:
            if self.config.get("extraStaticFontmakeArgs") is not None:
                args += " " + str(self.config["extraStaticFontmakeArgs"])

        return args

    def fix_args(self):
        args = ""
        if self.config.get("includeSourceFixes"):
            args += " --include-source-fixes"
        if self.config.get("fvarInstanceAxisDflts"):
            args += (
                " --fvar-instance-axis-dflts '"
                + self.config["fvarInstanceAxisDflts"]
                + "'"
            )
        return args

    def build_all_variables(self):
        if not self.config.get("buildVariable", True):
            return
        for source in self.sources:
            if not source.is_variable:
                continue
            italic_ds = None
            if self.config["splitItalic"]:
                italic_ds = self._has_slant_ital(source)
            if italic_ds:
                self.build_a_variable(source, italic_ds=italic_ds, roman=True)
                self.build_a_variable(source, italic_ds=italic_ds, roman=False)
                if self.statfile:
                    self._italicize_stat_file(source, italic_ds)
            else:
                self.build_a_variable(source)
        self.build_STAT()

    def build_STAT(self):
        # Add buildStat to a variable target, it'll do for all of them

        # We've built a bunch of variables here, but we may also have
        # some woff2 we added as part of the process, so ignore them.
        all_variables = [x for x in self.recipe.keys() if x.endswith("ttf")]
        if len(all_variables) > 0:
            last_target = all_variables[-1]
            if self.statfile:
                self.statfile.close()
                args = {"args": "--src " + self.statfile.name}
            else:
                args = {}
            other_variables = list(set(all_variables) - set([last_target]))
            build_stat_step = {
                "postprocess": "buildStat",
                **args,
            }
            if other_variables:
                build_stat_step["needs"] = other_variables
            self.recipe[last_target].append(build_stat_step)

    def _vtt_steps(self, target: str):
        if os.path.basename(target) in self.config.get("vttSources", {}):
            return [
                {
                    "operation": "buildVTT",
                    "vttfile": self.config["vttSources"][os.path.basename(target)],
                }
            ]
        return []

    def build_a_variable(
        self, source: File, italic_ds: Italic = None, roman: bool = False
    ):
        suffix = self.config.get("filenameSuffix", "")
        if roman:
            target = self._vf_filename(
                source, suffix=suffix, italic_ds=italic_ds, roman=True
            )
        else:
            target = self._vf_filename(
                source, suffix=suffix, italic_ds=italic_ds, roman=False
            )
        steps = (
            [
                {"source": source.path},
                {
                    "operation": "buildVariable",
                    "args": self.fontmake_args(source, variable=True),
                },
            ]
            + self.config.get("postCompile", [])
            + self._vtt_steps(target)
        )
        if italic_ds:
            desired_slice = italic_ds[0] + "="
            if roman:
                desired_slice += str(italic_ds[1])
                steps += [{"operation": "subspace", "axes": desired_slice}]
            else:
                desired_slice += str(italic_ds[2])
                steps += [
                    {"operation": "subspace", "axes": desired_slice},
                ] + self._italic_fixup()

        steps += self._fix_step()

        self.recipe[target] = steps
        self.build_a_webfont(target, self._vf_filename(source, extension="woff2"))
        if self._do_smallcap(source):
            self.recipe[
                self._vf_filename(source, italic_ds=italic_ds, roman=roman, suffix="SC")
            ] = self._smallcap_steps(source, target)

    def build_all_statics(self):
        if not self.config.get("buildStatic", True):
            return
        for source in self.sources:
            for instance in source.instances:
                if self.config["buildTTF"]:
                    self.build_a_static(source, instance, output="ttf")
                if self.config["buildOTF"]:
                    self.build_a_static(source, instance, output="otf")

    def build_a_static(self, source: File, instance: InstanceDescriptor, output):
        suffix = self.config.get("filenameSuffix", "")
        target = self._static_filename(instance, suffix=suffix, extension=output)

        steps = [
            {"source": source.path},
        ]
        # if we're running fontc we skip conversion to UFO
        if not source.is_ufo and not self.config.get("use_fontc", False):
            instancename = instance.name
            if instancename is None:
                if not instance.familyName or not instance.styleName:
                    raise ValueError(
                        f"Instance {instance.filename} must have a name, or familyName and styleName"
                    )
                instancename = instance.familyName + " " + instance.styleName
            steps.append(
                {
                    "operation": "instantiateUfo",
                    "instance_name": instancename,
                    "glyphData": self.config.get("glyphData"),
                }
            )
        steps += (
            [
                {
                    "operation": "buildTTF" if output == "ttf" else "buildOTF",
                    "args": self.fontmake_args(source, variable=False),
                }
            ]
            + self.config.get("postCompile", [])
            + self._autohint_steps(target)
            + self._vtt_steps(target)
            + self._fix_step()
        )
        self.recipe[target] = steps
        self.build_a_webfont(target, self._static_filename(instance, extension="woff2"))
        if self._do_smallcap(source):
            self.recipe[
                self._static_filename(instance, extension=output, suffix="SC")
            ] = self._smallcap_steps(source, target)

    def build_a_webfont(self, original_target, wf_filename):
        if not self.config["buildWebfont"]:
            return
        if not original_target.endswith(".ttf"):
            return
        self.recipe[wf_filename] = copy.deepcopy(self.recipe[original_target]) + [
            {"operation": "compress"}
        ]

    def _autohint_steps(self, target):
        if bool(self.config.get("autohintTTF")) and target.endswith("ttf"):
            args = "--fail-ok "
            if self.config.get("ttfaUseScript"):
                args += " --auto-script"
            return [{"operation": "autohint", "args": args}]
        if bool(self.config.get("autohintOTF")) and target.endswith("otf"):
            return [{"operation": "autohintOTF"}]
        return []

    def _fix_step(self):
        return [{"operation": "fix", "args": self.fix_args()}]

    def _do_smallcap(self, source):
        if not self.config.get("buildSmallCap"):
            return False
        if source.is_glyphs:
            return "smcp" in source.gsfont.features
        elif source.is_designspace:
            source.designspace.loadSourceFonts(open_ufo)
            return "feature smcp" in source.designspace.sources[0].font.features.text
        else:  # UFO
            return "feature smcp" in open_ufo(source.path).features.text

    def _smallcap_steps(self, source, original):
        new_family_name = source.family_name + " SC"
        return [
            {"source": original},
            {"operation": "remapLayout", "args": "'smcp -> ccmp'"},
            {
                "operation": "rename",
                "args": "--just-family",
                "name": new_family_name,
            },
            {"operation": "fix", "args": self.fix_args()},
        ]

    def _italicize_stat_file(self, source: File, italic_ds: Italic):
        # In this situation we have a stat file, and we have a font with
        # either an ital or a slnt axis that we have split into two subspaced
        # VFs. We now need to rewrite the stat file to remove the slnt axis,
        # and potentially to copy the STAT table to the newly created file.

        # What kind of STAT file are we? A global one or a font-specific one?
        if isinstance(self.config["stat"], dict):
            old_font = self._vf_filename(source)
            new_font = self._vf_filename(source, italic_ds=italic_ds, roman=False)
            if old_font in self.config["stat"] and new_font not in self.config["stat"]:
                raise ValueError(
                    f"We are splitting the font on the {italic_ds[0]} axis, "
                    "but the stat: entry in the config file does not contain "
                    f"an entry for {new_font}. Please add one and try again."
                )
            # Presume the user has done the right thing
            return
        # This is easy, just drop slnt
        self.config["stat"] = [
            axis for axis in self.config["stat"] if axis["tag"] != "slnt"
        ]
        # Rewrite the stat file
        self.statfile.seek(0)
        self.statfile.truncate(0)
        yaml.dump(self.config["stat"], self.statfile)

    def _italic_fixup(self):
        # We have a font created by subspacing the ital or slnt axis, but its
        # name table is not italic yet (and we can't use --update-name-table
        # because we don't have a STAT table eyt). So we need to make this font
        # "italic enough" to convince gftools-fix-font to apply all its italic
        # font fixes (post.italicAngle etc.) when we call it with
        # --include-source-fixes.
        configfile = NamedTemporaryFile(delete=False, mode="w+")
        family_name = self.sources[0].family_name.replace(" ", "")
        # Since this is mad YAML, we can't use the normal YAML library
        # to write this. We'll just write it out manually.
        configfile.write(
            f"""
OS/2->fsSelection: 129
head->macStyle: "|= 0x02"
name->setName: ["{family_name}Italic", 25, 3, 1, 0x409]
name->setName: ["Italic", 2, 3, 1, 0x409]
name->setName: ["Italic", 17, 3, 1, 0x409]
        """
        )
        configfile.close()
        return [
            {
                "operation": "exec",
                "exe": "gftools-fontsetter",
                "args": "-o $out $in " + configfile.name,
            },
            {
                "operation": "fix",
                "args": "--include-source-fixes",
            },
        ]
