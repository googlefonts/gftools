from gftools.builder.operations import OperationBase


class ApplyHinting(OperationBase):
    description = "Apply a font's TrueType hinting file"
    rule = "gftools-apply-hinting -o $out $in $hintingfile"
