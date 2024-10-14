from gftools.builder.operations import FontmakeOperationBase


class BuildVariable(FontmakeOperationBase):
    description = "Build a variable font from a source file"
    format = "variable"
    static = False
