from gftools.builder.operations import OperationBase


class Compress(OperationBase):
    description = "Compress to webfont"
    rule = "fonttools ttLib.woff2 compress -o $out $in"
