import os
import copy
from gftools.builder.recipeproviders.googlefonts import GFBuilder

name = "Noto builder"

class NotoBuilder(GFBuilder):

    def build_a_variable(self, source):
        # Figure out target name
        if source.is_glyphs:
            familyname = source.gsfont.familyName.replace(" ", "")
        else:
            raise NotImplementedError

        sourcebase = os.path.splitext(source.basename)[0]
        if source.is_glyphs:
            tags = [ ax.axisTag for ax in source.gsfont.axes]
        elif source.is_designspace:
            tags = [ ax.tag for ax in source.designspace.axes]
        else:
            raise ValueError("Unknown source type")
        axis_tags = ",".join(sorted(tags))

        target = os.path.join("fonts", familyname, "unhinted", "variable", f"{sourcebase}[{axis_tags}].ttf")
        self.recipe[target] = [
            {"source": source.path},
            {"operation": "buildVariable"},
            { "operation": "fix" },
        ]

        target = os.path.join("fonts", familyname, "unhinted", "slim-variable-ttf", f"{sourcebase}[{axis_tags}].ttf")
        self.recipe[target] = [
            {"source": source.path},
            {"operation": "buildVariable"},
            { "operation": "fix" },
            { "operation": "subspace" },
            { "operation": "hbsubset" },
        ]

    def build_all_statics(self):
        if not self.config.get("buildStatic", True):
            return
        for source in self.sources:
            for instance in source.instances:
                self.build_a_static(source, instance, output="ttf")

    def build_a_static(self, source, instance, output):
        if source.is_glyphs:
            familyname = source.gsfont.familyName.replace(" ", "")
        else:
            raise NotImplementedError

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
        instancebase = os.path.splitext(os.path.basename(instance.filename))[0]
        target = os.path.join("fonts", familyname, "unhinted", "ttf", f"{instancebase}.{output}")
        self.recipe[target] = steps


        target = os.path.join("fonts", familyname, "hinted", "ttf", f"{instancebase}.{output}")
        steps = copy.deepcopy(steps)
        steps.append({
            "operation": "autohint",
            "autohint_args": "--fail-ok --auto-script --discount-latin"
        })
        steps.append({"operation": "fix"})
        self.recipe[target] = steps
