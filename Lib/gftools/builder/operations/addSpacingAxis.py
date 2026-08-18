import logging

from gftools.builder.operations import OperationBase

log = logging.getLogger(__name__)


class AddSpacingAxis(OperationBase):
    description = "Add spacing axis side bearings"
    rule = "gftools-gen-spac --inplace $in $min $max --user-min $userMin --user-max $userMax $args"

    def validate(self):
        if "min" not in self.original and "max" not in self.original:
            raise ValueError(
                "addSpacingAxis: at least one of min & max must be specified"
            )
        vars = self.variables
        if vars["min"] > 0:
            raise ValueError("addSpacingAxis: min must be negative")
        if vars["max"] < 0:
            raise ValueError("addSpacingAxis: max must be positive")
        if vars["min"] == vars["max"] == 0:
            log.warning("addSpacingAxis: min & max shouldn't both be zero")
        return super().validate()

    @property
    def variables(self):
        design_min = int(self.original.get("min", 0))
        design_max = int(self.original.get("max", 0))
        return {
            "min": design_min,
            "max": design_max,
            "userMin": int(self.original.get("userMin", design_min)),
            "userMax": int(self.original.get("userMax", design_max)),
            **super().variables,
        }
