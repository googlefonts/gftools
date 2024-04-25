import logging
import os
import shutil

from gftools.builder.operations import OperationBase

log = logging.getLogger(__name__)
SUBSETTER_ENV_KEY = "GFTOOLS_SUBSETTER"


class HbSubset(OperationBase):
    description = "Run a subsetter to slim down a font"
    rule = "$subsetter --output-file=$in.subset --notdef-outline --unicodes=* --name-IDs=* --layout-features=* --glyph-names $args $in && mv $in.subset $out"

    @property
    def subsetter(self):
        subsetter = self.original.get(
            "subsetter", os.environ.get(SUBSETTER_ENV_KEY, "auto")
        )
        if subsetter == "python":
            return "pyftsubset"
        elif subsetter == "harfbuzz":
            return "hb-subset"
        else:  # hb-subset if installed, pyftsubset otherwise
            if shutil.which("hb-subset"):
                log.warning("Using hb-subset for subsetting")
                return "hb-subset"
            else:
                log.info("Using pyftsubset for subsetting")
                return "pyftsubset"

    @property
    def variables(self):
        super_vars = super().variables
        super_vars["subsetter"] = self.subsetter
        return super_vars
