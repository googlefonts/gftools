import copy
import os
from gftools.builder.recipeproviders import RecipeProviderBase


# Taken from gftools-builder
DEFAULTS = {
    "outputDir": "../fonts",
    "vfDir": "../fonts/variable",
    "ttDir": "../fonts/ttf",
    "otDir": "../fonts/otf",
    "woffDir": "../fonts/webfonts",
    "buildStatic": True,
    "buildOTF": True,
    "buildTTF": True,
    "autohintTTF": True,
    "ttfaUseScript": False,
    "logLevel": "INFO",
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
    def write_recipe(self):
        self.config = {**DEFAULTS, **self.config}
        self.config["buildWebfont"] = (
            self.config.get("buildWebfont") or self.config["buildStatic"]
        )
        # Find variable fonts
        self.recipe = {}
        self.build_all_variables()
        self.build_all_statics()
        return self.recipe

    def fontmake_args(self):
        args = "--filter ... "
        if self.config.get("flattenComponents", True):
            args += "--filter FlattenComponentsFilter "
        if self.config.get("decomposeTransformedComponents", True):
            args += "--filter DecomposeTransformedComponentsFilter "
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
        all_variables = list(self.recipe.keys())
        if len(all_variables) > 0:
            last_target = all_variables[-1]
            self.recipe[last_target].append(
                {
                    "postprocess": "buildStat",
                    "needs": list(set(all_variables) - set([last_target])),
                }
            )

    def build_a_variable(self, source):
        # Figure out target name
        sourcebase = os.path.splitext(source.basename)[0]
        if source.is_glyphs:
            tags = [ax.axisTag for ax in source.gsfont.axes]
        elif source.is_designspace:
            tags = [ax.tag for ax in source.designspace.axes]
        else:
            raise ValueError("Unknown source type")
        axis_tags = ",".join(sorted(tags))

        target = os.path.join(self.config["vfDir"], f"{sourcebase}[{axis_tags}].ttf")
        steps = [
            {"source": source.path},
            {"operation": "buildVariable", "fontmake_args": self.fontmake_args()},
            # XXX set version
            {"operation": "fix"},
        ]
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
                "fontmake_args": self.fontmake_args(),
            }
        )
        steps.append({"operation": "fix"})
        instancebase = os.path.splitext(os.path.basename(instance.filename))[0]
        target = os.path.join(outdir, f"{instancebase}.{output}")
        self.recipe[target] = steps

        if self.config["buildWebfont"] and output == "ttf":
            target = os.path.join(self.config["woffDir"], f"{instancebase}.woff2")
            self.recipe[target] = copy.deepcopy(steps) + [{"operation": "compress"}]
