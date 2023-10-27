from gftools.builder.operations import OperationBase


class Remap(OperationBase):
    description = "Rename a font's cmap table"
    rule = "gftools-remap-font -o $out $args $in $mappings"

    def validate(self):
        # Ensure there is a new name
        if "mappings" not in self.original:
            raise ValueError("No mappings specified")
        if not isinstance(self.original["mappings"], dict):
            raise ValueError("Mappings must be a dictionary")

    @property
    def variables(self):
        vars = super().variables
        vars["mappings"] = " ".join(
            ["{}={}".format(k, v) for k, v in self.original["mappings"].items()]
        )
        return vars
