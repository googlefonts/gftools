import os
from pathlib import Path
from tempfile import TemporaryDirectory

from gftools.builder.file import File
from gftools.builder.operations import OperationBase


class Glyphs2DS(OperationBase):
    description = "Turn a Glyphs file into a Designspace file"
    rule = "fontmake -o ufo -g $in --output-dir $outdir --designspace-path $dspath $fontmake_args"

    def convert_dependencies(self, builder):
        self._target = TemporaryDirectory()  # Stow object

    @property
    def targets(self):
        target = self._target.name
        if "directory" in self.original:
            target = self.original["directory"]

        base_name = Path(self.first_source.path).with_suffix(".designspace").name
        dspath = os.path.join(target, base_name)
        return [File(dspath)]

    @property
    def variables(self):
        return {
            "outdir": os.path.dirname(self.targets[0].path),
            "dspath": self.targets[0].path,
        }
