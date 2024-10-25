from gftools.builder.operations.fontc import FontcOperationBase


class FontcBuildVariable(FontcOperationBase):
    description = "Build a variable font from a source file (with fontc)"
    rule = f"$fontc_path -o $out $in $args"
