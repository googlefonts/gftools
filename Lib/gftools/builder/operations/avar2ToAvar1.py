from gftools.builder.operations import OperationBase


class Avar2ToAvar1(OperationBase):
    description = "Flatten an avar2 variable font into an avar1 variable font"
    rule = "gftools-avar2-to-avar1 $args $grid -o $out $in"

    def validate(self):
        grid = self.original.get("grid")
        if grid is not None and not isinstance(grid, (dict, list, str)):
            raise ValueError(
                "avar2ToAvar1: grid must be a mapping of axis tag to master "
                "count, a list of axis tags, or a string"
            )
        if isinstance(grid, dict):
            for tag, count in grid.items():
                if count is not None and not isinstance(count, int):
                    raise ValueError(
                        f"avar2ToAvar1: grid count for {tag} must be an integer"
                    )
        return super().validate()

    @property
    def variables(self):
        vars = super().variables
        grid = vars.pop("grid", None)
        if isinstance(grid, dict):
            # grid: {opsz: 3, wdth: 5, wght: 9} -> --grid opsz:3,wdth:5,wght:9
            # A null count means every knot the font has on that axis.
            spec = ",".join(
                tag if count is None else f"{tag}:{count}"
                for tag, count in grid.items()
            )
        elif isinstance(grid, list):
            spec = ",".join(grid)
        else:
            spec = grid
        vars["grid"] = f"--grid {spec}" if spec else ""
        return vars
