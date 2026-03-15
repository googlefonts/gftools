import os
import tempfile

import yaml

from gftools.builder.operations import OperationBase


class Fontsetter(OperationBase):
    description = "Run gftools-fontsetter"
    rule = "cp $in $out && gftools-fontsetter --inplace $out $args"

    @property
    def variables(self):
        vars = {k: v for k, v in self.original.items() if k != "needs"}
        # When "values" is present (e.g. from _italic_fixup), write them to a
        # temp YAML file and pass that as the config argument via $args.
        if "values" in vars:
            values = vars.pop("values")
            tmp = tempfile.NamedTemporaryFile(
                delete=False, mode="w", suffix=".yaml"
            )
            yaml.dump(values, tmp)
            tmp.close()
            vars["args"] = tmp.name
        return vars
