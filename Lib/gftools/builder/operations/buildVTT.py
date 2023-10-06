from gftools.builder.operations import OperationBase


class BuildVTT(OperationBase):
    description = "Run gftools-build-vtt"
    rule = "gftools-build-vtt -o $out $in $vttfile"
