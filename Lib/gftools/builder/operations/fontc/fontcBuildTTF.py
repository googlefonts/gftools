from gftools.builder.operations.fontc import FontcOperationBase


class FontcBuildTTF(FontcOperationBase):
    description = "Build a TTF from a source file (with fontc)"
    rule = "fontc -o $out $in $args"
