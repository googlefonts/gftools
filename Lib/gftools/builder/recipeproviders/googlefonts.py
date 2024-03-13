import copy
import logging
import os
from tempfile import NamedTemporaryFile

import yaml
from strictyaml import load, YAMLValidationError

from gftools.builder.recipeproviders import RecipeProviderBase
from gftools.builder.schema import (GOOGLEFONTS_SCHEMA, stat_schema,
                                    stat_schema_by_font_name)

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
            self.config[field] = self.config[field].replace("$outputDir", self.config["outputDir"])
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

    def fontmake_args(self, variable=False):
        args = "--filter ... "
        if self.config.get("flattenComponents", True):
            args += " --filter FlattenComponentsFilter"
        if self.config.get("decomposeTransformedComponents", True):
            args += " --filter DecomposeTransformedComponentsFilter"

        if self.config.get("logLevel") != "WARN":
            args += " --verbose " + self.config["logLevel"].value
        if self.config.get("reverseOutlineDirection"):
            args += " --keep-direction"
        if self.config.get("removeOutlineOverlaps") is False:
            args += " --keep-overlaps"
        if self.config.get("expandFeaturesToInstances"):
            args += " --expand-features-to-instances"
        if self.config.get("extraFontmakeArgs") is not None:
            args += " " + str(self.config["extraFontmakeArgs"])
        if variable:
            if self.config.get("extraVariableFontmakeArgs") is not None:
                args += " " + str(self.config["extraVariableFontmakeArgs"])
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
        all_variables = [x for x in self.recipe.keys() if x.endswith("ttf")]
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

    def build_a_variable(self, source):
        # Figure out target name
        sourcebase = os.path.splitext(source.basename)[0]
        vf_args = ""

        if self.config.get("checkCompatibility") == False:
            vf_args += "--no-check-compatibility "

        if source.is_glyphs:
            tags = [ax.axisTag for ax in source.gsfont.axes]
        elif source.is_designspace:
            tags = [ax.tag for ax in source.designspace.axes]
        else:
            raise ValueError("Unknown source type")

        axis_tags = ",".join(sorted(tags))

        if source.is_glyphs:
            for gd in self.config.get("glyphData", []):
                vf_args += " --glyph-data " + gd

        target = os.path.join(self.config["vfDir"], f"{sourcebase}[{axis_tags}].ttf")
        steps = [
            {"source": source.path},
            {
                "operation": "buildVariable",
                "args": vf_args + self.fontmake_args(variable=True),
            },
        ]
        if os.path.basename(target) in self.config.get("vttSources", {}):
            steps.append(
                {
                    "operation": "buildVTT",
                    "vttfile": self.config["vttSources"][os.path.basename(target)],
                }
            )
        steps.append(
            {"operation": "fix", "args": self.fix_args()},
        )
        self.recipe[target] = steps
        if self.config["buildWebfont"]:
            target = os.path.join(
                self.config["woffDir"], f"{sourcebase}[{axis_tags}].woff2"
            )
            self.recipe[target] = copy.deepcopy(steps) + [{"operation": "compress"}]

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
        if output == "ttf":
            outdir = self.config["ttDir"]
        else:
            outdir = self.config["otDir"]
        instancebase = os.path.splitext(os.path.basename(instance.filename))[0]
        target = os.path.join(outdir, f"{instancebase}.{output}")

        static_args = ""
        if source.is_glyphs:
            for gd in self.config.get("glyphData", []):
                static_args += " --glyph-data " + gd

        steps = [
            {"source": source.path},
        ]
        if not source.is_ufo:
            steps.append(
                {"operation": "instantiateUfo", "instance_name": instance.name}
            )
        steps.append(
            {
                "operation": "buildTTF" if output == "ttf" else "buildOTF",
                "args": self.fontmake_args(variable=False) + static_args,
            }
        )
        if bool(self.config.get("autohintTTF")) and output == "ttf":
            args = "--fail-ok "
            if self.config.get("ttfaUseScript"):
                args += " --auto-script"
            steps.append({"operation": "autohint", "args": args})
        if bool(self.config.get("autohintOTF")) and output == "otf":
            steps.append({"operation": "autohintOTF"})
        if os.path.basename(target) in self.config.get("vttSources", {}):
            steps.append(
                {
                    "operation": "buildVTT",
                    "vttfile": self.config["vttSources"][os.path.basename(target)],
                }
            )
        steps.append({"operation": "fix", "args": self.fix_args()})
        self.recipe[target] = steps

        if self.config["buildWebfont"] and output == "ttf":
            target = os.path.join(self.config["woffDir"], f"{instancebase}.woff2")
            self.recipe[target] = copy.deepcopy(steps) + [{"operation": "compress"}]
