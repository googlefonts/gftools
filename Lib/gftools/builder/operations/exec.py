from gftools.builder.operations import OperationBase


class Exec(OperationBase):
    description = "Run an arbitrary executable"
    rule = "$exe $args"

    def validate(self):
        if "exe" not in self.original:
            raise ValueError("No executable given")

        if "args" not in self.original:
            raise ValueError("No arguments given")

    @property
    def variables(self):
        # We would like to be able to use the "$in" and
        # "$out" template variables inside our "args" string,
        # but ninja does not perform this second level of
        # variable expansion. So we do it ourselves.
        vars = {
            "exe": self.original["exe"],
            "args": self.original["args"],
        }
        all_input_files = " ".join([source.path for source in self._sources])
        vars["args"] = vars["args"].replace("$in", all_input_files)
        if "$out" in vars["args"]:
            if len(self._targets) != 1:
                raise ValueError("Multiple outputs, but $out used")
            vars["args"] = vars["args"].replace("$out", self.first_target.path)
        return vars
