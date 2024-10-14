from gftools.builder.operations import FontmakeOperationBase


class BuildOTF(FontmakeOperationBase):
    description = "Build a OTF from a source file"
    format = "otf"
    static = True
