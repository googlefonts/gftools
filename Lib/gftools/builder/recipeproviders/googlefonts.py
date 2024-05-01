import copy
import logging
import os
from tempfile import NamedTemporaryFile

import yaml
from strictyaml import load, YAMLValidationError

from gftools.builder.recipeproviders import RecipeProviderBase
from gftools.builder.schema import (
    GOOGLEFONTS_SCHEMA,
    stat_schema,
    stat_schema_by_font_name,
)
from gftools.utils import open_ufo

logger = logging.getLogger("GFBuilder")

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
            except:
                load(yaml.dump(self.config["stat"]), stat_schema_by_font_name)
            yaml.dump(self.config["stat"], self.statfile)
            self.statfile.close()
        else:
            self.statfile = None
        # Find variable fonts
        self.recipe = {}
        self.build_all_variables()
        self.build_all_statics()
        return self.recipe

    def _vf_filename(self, source, suffix="", extension="ttf"):
        """Determine the file name for a variable font."""
        sourcebase = os.path.splitext(source.basename)[0]
        if source.is_glyphs:
            tags = [ax.axisTag for ax in source.gsfont.axes]
        elif source.is_designspace:
            tags = [ax.tag for ax in source.designspace.axes]
        else:
            raise ValueError("Unknown source type")

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

    def _static_filename(self, instance, suffix="", extension="ttf"):
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
            if (
                (source.is_glyphs and len(source.gsfont.masters) < 2)
                or source.is_ufo
                or (source.is_designspace and len(source.designspace.sources) < 2)
            ):
                continue
            self.build_a_variable(source)
        self.build_STAT()

    def build_STAT(self):
        # Add buildStat to a variable target, it'll do for all of them

        # We've built a bunch of variables here, but we may also have
        # some woff2 we added as part of the process, so ignore them.
        # We also ignore any small cap VFs we made
        all_variables = [
            x
            for x in self.recipe.keys()
            if x.endswith("ttf") and not ("SC[" in x or "SC-Italic[" in x)
        ]
        if len(all_variables) > 0:
            last_target = all_variables[-1]
            if self.statfile:
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

    def _vtt_steps(self, target):
        if os.path.basename(target) in self.config.get("vttSources", {}):
            return [
                {
                    "operation": "buildVTT",
                    "vttfile": self.config["vttSources"][os.path.basename(target)],
                }
            ]
        return []

    def build_a_variable(self, source):
        target = self._vf_filename(source)
        steps = (
            [
                {"source": source.path},
                {
                    "operation": "buildVariable",
                    "args": self.fontmake_args(source, variable=True),
                },
            ]
            + self._vtt_steps(target)
            + self._fix_step()
        )
        self.recipe[target] = steps
        self.build_a_webfont(target, self._vf_filename(source, extension="woff2"))
        if self._do_smallcap(source):
            self.recipe[self._vf_filename(source, suffix="SC")] = self._smallcap_steps(
                source, target
            )

    def build_all_statics(self):
        if not self.config.get("buildStatic", True):
            return
        for source in self.sources:
            for instance in source.instances:
                if self.config["buildTTF"]:
                    self.build_a_static(source, instance, output="ttf")
                if self.config["buildOTF"]:
                    self.build_a_static(source, instance, output="otf")

    def build_a_static(self, source, instance, output):
        target = self._static_filename(instance, extension=output)

        steps = [
            {"source": source.path},
        ]
        if not source.is_ufo:
            steps.append(
                {
                    "operation": "instantiateUfo",
                    "instance_name": instance.name,
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
