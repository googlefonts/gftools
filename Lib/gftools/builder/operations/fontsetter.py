import os

from gftools.builder.operations import OperationBase


class Fontsetter(OperationBase):
    description = "Run gftools-fontsetter"
    rule = "gftools-fontsetter --inplace $in $args"
