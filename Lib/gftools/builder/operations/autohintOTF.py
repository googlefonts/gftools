from gftools.builder.operations import OperationBase


class AutohintOTF(OperationBase):
    description = "Run otfautohint"
    rule = "otfautohint $args -o $out $in \|\| otfautohint $args -o $out $in --no-zones-stems"
