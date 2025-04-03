import os

from gftools.builder.operations import OperationBase


class BuildAvar2(OperationBase):
    description = "Run gftools-gen-avar2"
    rule = "gftools-gen-avar2 --inplace $in $args"
