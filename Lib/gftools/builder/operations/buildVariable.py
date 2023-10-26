from gftools.builder.operations import FontmakeOperationBase


class BuildVariable(FontmakeOperationBase):
    description = "Build a variable font from a source file"
    rule = "fontmake --output-path $out -o variable $fontmake_type $in $args"
