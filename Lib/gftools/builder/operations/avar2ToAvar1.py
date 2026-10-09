from gftools.builder.operations import OperationBase


class Avar2ToAvar1(OperationBase):
    description = "Flatten an avar2 variable font into an avar1 variable font"
    rule = "gftools-avar2-to-avar1 $args $grid $refine -o $out $in"

    def validate(self):
        grid = self.original.get("grid")
        if grid is not None and not isinstance(grid, (dict, list, str)):
            raise ValueError(
                "avar2ToAvar1: grid must be a mapping of axis tag to master "
                "count, a list of axis tags, or a string"
            )
        if isinstance(grid, dict):
            for tag, count in grid.items():
                if isinstance(count, list):
                    if not all(isinstance(v, (int, float)) for v in count):
                        raise ValueError(
                            f"avar2ToAvar1: grid positions for {tag} must be numbers"
                        )
                elif count is not None and not isinstance(count, int):
                    raise ValueError(
                        f"avar2ToAvar1: grid count for {tag} must be an integer "
                        "or a list of positions"
                    )
        refine = self.original.get("refine")
        if refine is not None:
            if not isinstance(refine, list):
                raise ValueError(
                    "avar2ToAvar1: refine must be a list of locations, each a "
                    "mapping of axis tag to user value"
                )
            for loc in refine:
                if not isinstance(loc, dict) or not all(
                    isinstance(v, (int, float)) for v in loc.values()
                ):
                    raise ValueError(
                        f"avar2ToAvar1: refine location {loc!r} must map axis "
                        "tags to numbers"
                    )
        return super().validate()

    @property
    def variables(self):
        vars = super().variables
        grid = vars.pop("grid", None)
        if isinstance(grid, dict):
            # grid: {opsz: 3, wdth: 5, wght: 9} -> --grid opsz:3,wdth:5,wght:9
            # A null count means every knot the font has on that axis; a
            # list, {wght: [300, 400, 700]}, means masters at those positions.
            def item(tag, count):
                if count is None:
                    return tag
                if isinstance(count, list):
                    return f"{tag}:" + "/".join(f"{v:g}" for v in count)
                return f"{tag}:{count}"

            spec = ",".join(item(tag, count) for tag, count in grid.items())
        elif isinstance(grid, list):
            spec = ",".join(grid)
        else:
            spec = grid
        vars["grid"] = f"--grid {spec}" if spec else ""
        # refine: [{wght: 352, wdth: 25, opsz: 9}] -> --refine-at wght=352,wdth=25,opsz=9
        # refine_crossings: true -> --refine-crossings
        flags = [
            "--refine-at " + ",".join(f"{t}={v:g}" for t, v in loc.items())
            for loc in vars.pop("refine", None) or []
        ]
        if vars.pop("refine_crossings", False):
            flags.append("--refine-crossings")
        vars["refine"] = " ".join(flags)
        return vars
