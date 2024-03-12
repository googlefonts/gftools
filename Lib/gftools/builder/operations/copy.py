from gftools.builder.operations import OperationBase


class Copy(OperationBase):
    description = "Copy a file"
    rule = "cp $in $out"
