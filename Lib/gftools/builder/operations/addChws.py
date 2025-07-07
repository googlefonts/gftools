from pathlib import Path
from tempfile import NamedTemporaryFile
from gftools.builder.file import File
from gftools.builder.operations import OperationBase


class AddChws(OperationBase):
    description = "Add chws feature to font"
    rule = "add-chws -o $out $in"

    # add-chws require the output to have a .ttf extension
    @property
    def targets(self):
        return [File(str(Path(self.first_source.path).with_suffix(".chws.ttf")))]

    def set_target(self, target: File):
        raise ValueError("Cannot set target on addChws operation")
