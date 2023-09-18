from gftools.builder.operations import OperationBase


class BuildSTAT(OperationBase):
    in_place = True
    description = "Build a STAT table from one or more source files"
    rule = "gftools-gen-stat --inplace $other_args -- $in"
