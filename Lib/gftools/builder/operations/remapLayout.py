from gftools.builder.operations import OperationBase


class RemapLayout(OperationBase):
    description = "Run gftools-remap-layout to change a font's layout rules"
    rule = "gftools-remap-layout -o $out $in $args"
