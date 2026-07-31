from gftools.builder.operations import OperationBase


class GenStatic(OperationBase):
    description = "Generate a static font from a variable font"
    rule = 'gftools-gen-static $in "$family" "$style" $args -o $out'

    def validate(self):
        if "family" not in self.original:
            raise ValueError("No family name specified")
        if "style" not in self.original:
            raise ValueError("No style name specified")
