from gftools.builder.operations import OperationBase
import glyphsLib
import gftools.builder


class PaintCompiler(OperationBase):
    description = "Run paintcompiler on a variable font"
    rule = "paintcompiler $args -o $out $in"

    @property
    def variables(self):
        vars = super().variables
        vars["args"] = self.original.get("args", "")
        return vars
