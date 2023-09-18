from gftools.builder.operations import OperationBase


class Autohint(OperationBase):
    description = "Run gftools-autohint"
    rule = "gftools-autohint $autohint_args -o $out $in"
