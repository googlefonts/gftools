from gftools.builder.operations import OperationBase


class FontcBuildVariable(OperationBase):
    description = "Build a variable font from a source file (with fontc)"
    rule = "fontc -o $out $in"
