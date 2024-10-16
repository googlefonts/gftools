from gftools.builder.operations.fontc import FontcOperationBase


class FontcBuildVariable(FontcOperationBase):
    description = "Build a variable font from a source file (with fontc)"
    rule = "fontc -o $out $in $args"
