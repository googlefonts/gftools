"""Test whether the font should be PRed to GF, inform GitHub if so.
"""
import os

import yaml

if __name__ == "__main__":
    config = yaml.load(
        open(os.path.join("sources", "config.yaml")), Loader=yaml.FullLoader
    )
    if "googleFonts" in config and config["googleFonts"]:
        print("This font should be submitted to Google Fonts")
        print("::set-output name=is_gf::true")
    else:
        print("This font should not be submitted to Google Fonts")
        print("::set-output name=is_gf::false")
