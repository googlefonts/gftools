from gftools.builder.operations import FontmakeOperationBase


class BuildTTF(FontmakeOperationBase):
    description = "Build a TTF from a source file"
    rule = "fontmake --output-path $out -o ttf $fontmake_type $in $fontmake_args"
