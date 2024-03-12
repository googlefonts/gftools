from gftools.builder.operations import OperationBase


class FeatureFreeze(OperationBase):
    description = "Run pyftfeatfreeze to freeze a font"
    rule = "pyftfeatfreeze $args $in $out"
