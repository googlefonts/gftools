import copy
import os

import ufoLib2

from gftools.builder.recipeproviders.googlefonts import DEFAULTS, GFBuilder

name = "Noto builder"


class NotoBuilder(GFBuilder):
    def write_recipe(self):
        self.config = {**DEFAULTS, **self.config}
        # Convert any glyphs sources to DS
        newsources = []
        for source in self.config["sources"]:
            if source.endswith((".glyphs", ".glyphspackage")):
                source = self.builder.glyphs_to_ufo(source)
            newsources.append(source)
        self.config["sources"] = newsources
        # Find variable fonts
        self.recipe = {}
        self.build_all_variables()
        self.build_all_statics()
        return self.recipe

    def build_a_variable(self, source):
        familyname_path = source.family_name.replace(" ", "")
        sourcebase = os.path.splitext(source.basename)[0]
        if source.is_designspace:
            tags = [ax.tag for ax in source.designspace.axes]
        else:
            raise ValueError("Unknown source type " + source.path)
        axis_tags = ",".join(sorted(tags))

        # Unhinted variable
        target = os.path.join(
            "fonts",
            familyname_path,
            "unhinted",
            "variable",
            f"{sourcebase}[{axis_tags}].ttf",
        )
        self.recipe[target] = [
            {"source": source.path},
            {"operation": "buildVariable"},
            {"operation": "fix"},
        ]

        # Slim variable
        self.slim(target, tags)

        # Full variable
        if "includeSubsets" in self.config:
            target = os.path.join(
                "fonts",
                familyname_path,
                "full",
                "variable",
                f"{sourcebase}[{axis_tags}].ttf",
            )
            self.recipe[target] = [
                {"source": source.path},
                {
                    "operation": "addSubset",
                    "subsets": self.config["includeSubsets"],
                    "directory": "full-designspace",
                },
                {"operation": "buildVariable"},
                {"operation": "fix"},
            ]
            self.slim(target, tags)

    def build_all_statics(self):
        if not self.config.get("buildStatic", True):
            return
        for source in self.sources:
            for instance in source.instances:
                self.build_a_static(source, instance, output="ttf")
                self.build_a_static(source, instance, output="otf")

    def build_a_static(self, source, instance, output):
        familyname_path = source.family_name.replace(" ", "")

        # Unhinted static
        steps = [
            {"source": source.path},
            {
                "operation": "instantiateUfo",
                "instance_name": instance.name,
            },
            {"operation": "buildTTF" if output == "ttf" else "buildOTF"},
        ]

        instancebase = os.path.splitext(os.path.basename(instance.filename))[0]
        target = os.path.join(
            "fonts", familyname_path, "unhinted", output, f"{instancebase}.{output}"
        )
        self.recipe[target] = steps

        # Hinted static
        if output == "ttf":
            target = os.path.join(
                "fonts", familyname_path, "hinted", output, f"{instancebase}.{output}"
            )
            steps = copy.deepcopy(steps) + [
                {
                    "operation": "autohint",
                    "autohint_args": "--fail-ok --auto-script --discount-latin",
                },
                {"operation": "fix"},
            ]
            self.recipe[target] = steps

        # Full static
        if "includeSubsets" in self.config:
            target = os.path.join(
                "fonts", familyname_path, "full", output, f"{instancebase}.{output}"
            )
            steps = [
                {"source": source.path},
                {
                    "operation": "addSubset",
                    "subsets": self.config["includeSubsets"],
                    "directory": "full-designspace",
                },
                {
                    "operation": "instantiateUfo",
                    "instance_name": instance.name,
                    "target": "full-designspace/" + os.path.basename(instance.filename),
                },
                {"operation": "buildTTF" if output == "ttf" else "buildOTF"},
            ]
            if output == "ttf":
                steps.extend([
                    {
                        "operation": "autohint",
                        "autohint_args": "--fail-ok --auto-script --discount-latin",
                    },
                    {"operation": "fix"},
                ])
            self.recipe[target] = steps

    def slim(self, target, tags):
        axis_tags = ",".join(sorted(tags))
        axes = "wght=400:700"
        if "wdth" in tags:
            axes += " wdth=drop"

        newtarget = target.replace("variable", "slim-variable-ttf").replace(
            axis_tags, "wght"
        )
        self.recipe[newtarget] = copy.deepcopy(self.recipe[target]) + [
            {"operation": "subspace", "axes": axes},
            {"operation": "hbsubset"},
        ]
