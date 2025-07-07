from gftools.builder.operations import OperationBase


class AddChws(OperationBase):
    description = "Add chws feature to font"
    rule = "add-chws -o $out $in"
