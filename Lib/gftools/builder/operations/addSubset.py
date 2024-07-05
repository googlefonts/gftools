import os
from tempfile import NamedTemporaryFile, TemporaryDirectory

import yaml

from gftools.builder.file import File
from gftools.builder.operations import OperationBase


class AddSubset(OperationBase):
    description = "Add a subset from another font"
    rule = "gftools-add-ds-subsets $args -j -y $yaml -o $out $in"

    def validate(self):
        # Ensure there is a new name
        if not self.first_source.is_font_source:
            raise ValueError("%s is not a font source file" % self.first_source)
        if "subsets" not in self.original:
            raise ValueError("No subsets defined")

    def convert_dependencies(self, graph):
        self._target = TemporaryDirectory()  # Stow object
        self._orig = NamedTemporaryFile(delete=False, mode="w")
        yaml.dump(self.original["subsets"], self._orig)
        self._orig.close()

    @property
    def targets(self):
        if "directory" in self.original:
            target = self.original["directory"]
        else:
            target = self._target.name
        dspath = os.path.join(
            target, self.first_source.basename.rsplit(".", 1)[0] + ".designspace"
        )
        return [File(dspath)]

    @property
    def variables(self):
        return {
            "yaml": self._orig.name,
            "args": self.original.get("args"),
        }
