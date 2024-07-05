import copy
import os
import sys
from collections import defaultdict

import yaml
from strictyaml import (
    Bool,
    HexInt,
    Int,
    Map,
    Optional,
    Seq,
    Str,
    YAMLValidationError,
    load,
)

from gftools.builder.recipeproviders.googlefonts import (
    DEFAULTS,
    GOOGLEFONTS_SCHEMA,
    GFBuilder,
)
from gftools.util.styles import STYLE_NAMES

name = "Noto builder"

subsets_schema = Seq(
    Map(
        {
            "from": Str(),
            Optional("name"): Str(),
            Optional("ranges"): Seq(
                Map({"start": Int() | HexInt(), "end": Int() | HexInt()})
            ),
            Optional("layoutHandling"): Str(),
            Optional("force"): Str(),
        }
    )
)
_newschema = GOOGLEFONTS_SCHEMA._validator
_newschema[Optional("includeSubsets")] = subsets_schema
_newschema[Optional("buildUIVF")] = Bool()
schema = Map(_newschema)


class NotoBuilder(GFBuilder):
    schema = schema

    def write_recipe(self):
        self.revalidate()

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
        self.has_variables = bool(self.recipe)
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
            "variable-ttf",
            f"{sourcebase}[{axis_tags}].ttf",
        )
        self.recipe[target] = [
            {"source": source.path},
            {
                "operation": "buildVariable",
                "args": self.fontmake_args(source, variable=True),
            },
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
                "variable-ttf",
                f"{sourcebase}-UI-VF.ttf",
            )
            self.recipe[uivftarget] = [
                {"source": source.path},
                {
                    "operation": "buildVariable",
                    "args": self.fontmake_args(source, variable=True),
                },
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
                "variable-ttf",
                f"{sourcebase}[{axis_tags}].ttf",
            )
            self.recipe[target] = [
                {"source": source.path},
                {
                    "operation": "addSubset",
                    "subsets": self.config["includeSubsets"],
                    "directory": "full-designspace",
                    "args": "--allow-sparse",
                },
                {
                    "operation": "buildVariable",
                    "args": self.fontmake_args(source, variable=True),
                },
            ]
            self.slim(target, tags)

            # Googlefonts vf
            target = os.path.join(
                "../",
                "fonts",
                familyname_path,
                "googlefonts",
                "variable-ttf",
                f"{sourcebase}[{axis_tags}].ttf",
            )
            self.recipe[target] = [
                {"source": source.path},
                {
                    "operation": "addSubset",
                    "subsets": self.config["includeSubsets"],
                    "directory": "full-designspace",
                    "args": "--allow-sparse",
                },
                {
                    "operation": "buildVariable",
                    "args": self.fontmake_args(source, variable=True),
                },
                {"operation": "fix", "args": "--include-source-fixes"},
            ]
        else:
            # GF VF, no subsets
            target = os.path.join(
                "../",
                "fonts",
                familyname_path,
                "googlefonts",
                "variable-ttf",
                f"{sourcebase}[{axis_tags}].ttf",
            )
            self.recipe[target] = [
                {"source": source.path},
                {
                    "operation": "buildVariable",
                    "args": self.fontmake_args(source, variable=True),
                },
                {"operation": "fix", "args": "--include-source-fixes"},
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
            if len(variables) > 0:
                last_target = variables[-1]
                other_variables = list(set(variables) - set([last_target]))
                build_stat_step = {"postprocess": "buildStat"}
                if other_variables:
                    build_stat_step["needs"] = other_variables
                self.recipe[last_target].append(build_stat_step)

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
                "args": self.fontmake_args(source, variable=False),
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
                    "args": "--fail-ok --auto-script --discount-latin",
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
                    "args": "--allow-sparse",
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
                    "args": self.fontmake_args(source, variable=False),
                },
            ]
            if output == "ttf":
                steps.extend(
                    [
                        {
                            "operation": "autohint",
                            "args": "--fail-ok --auto-script --discount-latin",
                        },
                    ]
                )
            self.recipe[target] = steps

            # Googlefonts static
            if not self.has_variables and (
                output == "ttf" and instance.styleName in STYLE_NAMES
            ):
                target = os.path.join(
                    "../",
                    "fonts",
                    familyname_path,
                    "googlefonts",
                    output,
                    f"{instancebase}.{output}",
                )
                steps = copy.deepcopy(steps) + [
                    {"operation": "fix", "args": "--include-source-fixes"},
                ]
                self.recipe[target] = steps
        # There are no subsets to be added
        # We only build a googlefonts static if we don't have any variable fonts
        # since the GF PR will be either one variable or loads of statics, not both.
        elif not self.has_variables and (
            output == "ttf" and instance.styleName in STYLE_NAMES
        ):
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
                {
                    "operation": "buildTTF",
                    "args": self.fontmake_args(source, variable=False),
                },
                {
                    "operation": "autohint",
                    "args": "--fail-ok --auto-script --discount-latin",
                },
                {"operation": "fix", "args": "--include-source-fixes"},
            ]

    def slim(self, target, tags):
        axis_tags = ",".join(sorted(tags))
        axes = "wght=400:700"
        if "wdth" in tags:
            axes += " wdth=drop"

        newtarget = target.replace("variable-ttf", "slim-variable-ttf").replace(
            axis_tags, "wght"
        )
        self.recipe[newtarget] = copy.deepcopy(self.recipe[target]) + [
            {"operation": "subspace", "axes": axes},
            {"operation": "hbsubset"},
        ]
