from gftools.builder.operations import OperationBase


class HbSubset(OperationBase):
    description = "Run hb-subset to slim down a font"
    rule = "hb-subset --output-file=$in.subset --notdef-outline --unicodes=* --name-IDs=* --layout-features=* $in && mv $in.subset $out"
