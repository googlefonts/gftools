from gftools.builder.operations import OperationBase


class Rename(OperationBase):
    description = "Rename a font"
    rule = 'gftools-rename-font -o $out $args $in "$name"'

    def validate(self):
        # Ensure there is a new name
        if "name" not in self.original:
            raise ValueError("No new name specified")

    @property
    def variables(self):
        vars = super().variables
        vars["name"] = self.original["name"]
        return vars
