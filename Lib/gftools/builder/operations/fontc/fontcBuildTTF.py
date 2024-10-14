from gftools.builder.operations import OperationBase


class FontcBuildTTF(OperationBase):
    description = "Build a TTF from a source file (with fontc)"
    rule = "fontc -o $out $in"
