from gftools.builder.operations import FontmakeOperationBase


class BuildVariable(FontmakeOperationBase):
    description = "Build a variable font from a source file"
    rule = "fontmake --output-path $out -o variable $fontmake_type $in $fontmake_args"

    @property
    def variables(self):
        vars = {}
        if self.first_source.is_glyphs:
            vars["fontmake_type"] = "-g"
        else:
            vars["fontmake_type"] = "-m"
        
        return vars
