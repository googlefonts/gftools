from gftools.builder.operations import FontmakeOperationBase


class BuildTTF(FontmakeOperationBase):
    description = "Build a TTF from a source file"
    static = True
    format = "ttf"
