import copy
import os
import sys
from collections import defaultdict

import ufoLib2

from gftools.builder.recipeproviders.googlefonts import DEFAULTS, GFBuilder
from gftools.util.styles import STYLE_NAMES

name = "Noto builder"


class NotoBuilder(GFBuilder):
    def write_recipe(self):
        self.config = {**DEFAULTS, **self.config}
        # Convert any glyphs sources to DS
        newsources = []
        self.config["original_sources"] = self.config["sources"]
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
            "../",
            "fonts",
            familyname_path,
            "unhinted",
            "variable",
            f"{sourcebase}[{axis_tags}].ttf",
        )
        self.recipe[target] = [
            {"source": source.path},
            {"operation": "buildVariable", "fontmake_args": self.fontmake_args()},
            {"operation": "fix"},
        ]

        # UI variable
        if self.config.get("buildUIVF"):
            # Find my glyphs source
            glyphs_source = self.config["original_sources"][
                self.config["sources"].index(source.path)
            ]
            uivftarget = os.path.join(
                "../",
                "fonts",
                familyname_path,
                "unhinted",
                "variable",
                f"{sourcebase}-UI-VF.ttf",
            )
            self.recipe[uivftarget] = [
                {"source": source.path},
                {"operation": "buildVariable", "fontmake_args": self.fontmake_args()},
                {"operation": "fix"},
                {
                    "operation": "exec",
                    "exe": sys.executable,
                    "args": f"-m notobuilder.builduivf -o '{uivftarget}' '{target}' '{glyphs_source}'",
                    "needs": [target],
                },
            ]

        # Slim variable
        self.slim(target, tags)

        # Full variable
        if "includeSubsets" in self.config:
            target = os.path.join(
                "../",
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
                {"operation": "buildVariable", "fontmake_args": self.fontmake_args()},
            ]
            self.slim(target, tags)

            # Googlefonts vf
            target = os.path.join(
                "../",
                "fonts",
                familyname_path,
                "googlefonts",
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
                {"operation": "buildVariable", "fontmake_args": self.fontmake_args()},
                {"operation": "fix"},
            ]
        else:
            # GF VF, no subsets
            target = os.path.join(
                "../",
                "fonts",
                familyname_path,
                "googlefonts",
                "variable",
                f"{sourcebase}[{axis_tags}].ttf",
            )
            self.recipe[target] = [
                {"source": source.path},
                {"operation": "buildVariable", "fontmake_args": self.fontmake_args()},
                {"operation": "fix"},
            ]

    def build_STAT(self):
        # In each directory, add buildStat to one recipe with a needs:
        # of all the other VFs in that directory
        variables_by_directory = defaultdict(list)
        for variable in self.recipe.keys():
            if "UI-VF" in variable:
                continue
            variables_by_directory[os.path.dirname(variable)].append(variable)
        for variables in variables_by_directory.values():
            if len(variables) > 1:
                last_target = variables[-1]
                others = variables[:-1]
                self.recipe[last_target].append(
                    {
                        "postprocess": "buildStat",
                        "needs": list(set(others) - set([last_target])),
                    }
                )

    def build_a_static(self, source, instance, output):
        familyname_path = source.family_name.replace(" ", "")

        # Unhinted static
        steps = [
            {"source": source.path},
            {
                "operation": "instantiateUfo",
                "instance_name": instance.name,
            },
            {
                "operation": "buildTTF" if output == "ttf" else "buildOTF",
                "fontmake_args": self.fontmake_args(),
            },
        ]

        instancebase = os.path.splitext(os.path.basename(instance.filename))[0]
        target = os.path.join(
            "../",
            "fonts",
            familyname_path,
            "unhinted",
            output,
            f"{instancebase}.{output}",
        )
        self.recipe[target] = steps

        # Hinted static
        if output == "ttf":
            target = os.path.join(
                "../",
                "fonts",
                familyname_path,
                "hinted",
                output,
                f"{instancebase}.{output}",
            )
            steps = copy.deepcopy(steps) + [
                {
                    "operation": "autohint",
                    "autohint_args": "--fail-ok --auto-script --discount-latin",
                },
            ]
            self.recipe[target] = steps

        # Full static
        if "includeSubsets" in self.config:
            target = os.path.join(
                "../",
                "fonts",
                familyname_path,
                "full",
                output,
                f"{instancebase}.{output}",
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
                    "target": "full-designspace/instance_ufos/"
                    + os.path.basename(instance.filename)
                    + ".json",
                },
                {
                    "operation": "buildTTF" if output == "ttf" else "buildOTF",
                    "fontmake_args": self.fontmake_args(),
                },
            ]
            if output == "ttf":
                steps.extend(
                    [
                        {
                            "operation": "autohint",
                            "autohint_args": "--fail-ok --auto-script --discount-latin",
                        },
                    ]
                )
            self.recipe[target] = steps

            # Googlefonts static
            if output == "ttf" and instance.styleName in STYLE_NAMES:
                target = os.path.join(
                    "../",
                    "fonts",
                    familyname_path,
                    "googlefonts",
                    output,
                    f"{instancebase}.{output}",
                )
                steps = copy.deepcopy(steps) + [
                    {"operation": "fix"},
                ]
                self.recipe[target] = steps
        elif output == "ttf" and instance.styleName in STYLE_NAMES:
            # GF static, no subsets
            target = os.path.join(
                "../",
                "fonts",
                familyname_path,
                "googlefonts",
                "ttf",
                f"{instancebase}.{output}",
            )
            self.recipe[target] = [
                {"source": source.path},
                {
                    "operation": "instantiateUfo",
                    "instance_name": instance.name,
                },
                {"operation": "buildTTF", "fontmake_args": self.fontmake_args()},
                {
                    "operation": "autohint",
                    "autohint_args": "--fail-ok --auto-script --discount-latin",
                },
                {"operation": "fix"},
            ]

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
