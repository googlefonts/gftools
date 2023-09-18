from gftools.builder.operations import FontmakeOperationBase


class BuildOTF(FontmakeOperationBase):
    description = "Build a OTF from a source file"
    rule = "fontmake --output-path $out -o otf $fontmake_type $in $fontmake_args"
