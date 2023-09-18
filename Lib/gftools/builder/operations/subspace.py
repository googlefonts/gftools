from gftools.builder.operations import OperationBase


class Subspace(OperationBase):
    description = "Run varLib.instancer to subspace a variable font"
    rule = "fonttools varLib.instancer -o $out $in $axes"
