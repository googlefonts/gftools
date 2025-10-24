import os

from gftools.builder.operations import OperationBase


class BuildFvarInstances(OperationBase):
    description = "Run gftools-gen-fvar-instances"
    rule = "gftools-gen-fvar-instances --inplace $in $args"
