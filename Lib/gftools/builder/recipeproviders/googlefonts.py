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
        # Find variable fonts
        self.recipe = {}
        self.build_all_variables()
        self.build_all_statics()
        return self.recipe

    def build_all_variables(self):
        if not self.config.get("buildVariable", True):
             return
        for source in self.sources:
            if (source.is_glyphs and len(source.gsfont.masters) < 2) \
                or source.is_ufo \
                or (source.is_designspace and len(source.designspace.sources) < 2):
                continue
            self.build_a_variable(source)
        # Add buildStat to all variable targets
        all_variables = list(self.recipe.keys())
        if len(self.sources) > 1:
            for target, recipe in self.recipe.items():
                recipe.append({
                    "postprocess": "buildStat",
                    "needs": list(set(all_variables) - set([target]))
                })
    
    def build_a_variable(self, source):
        # Figure out target name
        sourcebase = os.path.splitext(source.basename)[0]
        if source.is_glyphs:
            tags = [ ax.axisTag for ax in source.gsfont.axes]
        elif source.is_designspace:
            tags = [ ax.tag for ax in source.designspace.axes]
        else:
            raise ValueError("Unknown source type")
        axis_tags = ",".join(sorted(tags))

        target = os.path.join(self.config["vfDir"], f"{sourcebase}[{axis_tags}].ttf")
        self.recipe[target] = [
            {"source": source.path},
            {"operation": "buildVariable"},
            # XXX set version
            { "operation": "fix" },
        ]

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
            {"operation": "buildTTF" if output == "ttf" else "buildOTF"}
        )
        steps.append({"operation": "fix"})
        instancebase = os.path.splitext(os.path.basename(instance.filename))[0]
        target = os.path.join(outdir, f"{instancebase}.{output}")
        self.recipe[target] = steps
