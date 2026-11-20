from gftools.builder.operations import OperationBase


class TransferHints(OperationBase):
    description = "Transfer a font's TrueType hinting"
    rule = "gftools-transfer-hints -o $out $hints $in"
