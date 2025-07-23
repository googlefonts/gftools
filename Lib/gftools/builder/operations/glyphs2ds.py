import os
from tempfile import TemporaryDirectory

from gftools.builder.file import File
from gftools.builder.operations import OperationBase
from glyphsLib.builder.axes import find_base_style


class Glyphs2DS(OperationBase):
    description = "Turn a Glyphs file into a Designspace file"
    rule = "fontmake -o ufo -g $in --output-dir $outdir $fontmake_args"

    def convert_dependencies(self, builder):
        self._target = TemporaryDirectory()  # Stow object

    @property
    def targets(self):
        target = self._target.name
        if "directory" in self.original:
            target = self.original["directory"]

        base_family = self.first_source.family_name
        # glyphsLib has a special case for Glyphs files where the masters have a
        # common style name; typically this manifests itself in single-master
        # Glyphs files, but it can also happen in multi-master files.
        # In that case, the designspace filename will be changed.
        if base_style := find_base_style(self.first_source.gsfont.masters):
            base_family += "-" + base_style
        dspath = os.path.join(target, base_family.replace(" ", "") + ".designspace")
        return [File(dspath)]

    @property
    def variables(self):
        return {
            "outdir": os.path.dirname(self.targets[0].path),
        }
