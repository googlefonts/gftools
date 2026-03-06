from gftools.builder.operations import OperationBase

class Prune(OperationBase):
    description = "Run gftools-prune"
    rule = "gftools-prune $in --out $out"
