from gftools.builder.operations import OperationBase


class Exec(OperationBase):
    description = "Run an arbitrary executable"
    rule = "$exe $args"

    def validate(self):
        if "exe" not in self.original:
            raise ValueError("No executable given")

        if "args" not in self.original:
            raise ValueError("No arguments given")
