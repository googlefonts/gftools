import os
from gftools.builder.operations import OperationBase


class AddSpacingAxis(OperationBase):
    description = "Add spacing axis side bearings"
    rule = "gftools-gen-spac --inplace $in $args"
