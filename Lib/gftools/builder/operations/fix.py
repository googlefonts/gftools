from gftools.builder.operations import OperationBase


class Fix(OperationBase):
    description = "Run gftools-fix"
    rule = "gftools-fix-font -o $out $args $in"
