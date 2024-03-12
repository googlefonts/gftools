from gftools.builder.operations import OperationBase


class Autohint(OperationBase):
    description = "Run gftools-autohint"
    rule = "gftools-autohint $args -o $out $in"
