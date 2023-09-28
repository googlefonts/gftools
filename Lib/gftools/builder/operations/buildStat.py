from gftools.builder.operations import OperationBase


class BuildSTAT(OperationBase):
    description = "Build a STAT table from one or more source files"
    rule = "gftools-gen-stat $other_args -- $in && mv $in.fix $out"
