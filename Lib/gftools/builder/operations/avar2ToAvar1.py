from gftools.builder.operations import OperationBase


class Avar2ToAvar1(OperationBase):
    description = "Flatten an avar2 variable font into an avar1 variable font"
    rule = "gftools-avar2-to-avar1 $args -o $out $in"
