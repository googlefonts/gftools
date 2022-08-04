import freetype as ft
import numpy as np
import uharfbuzz as hb
import logging
import tempfile
from blackrenderer.render import renderText
from PIL import Image

logger = logging.getLogger(__name__)


def draw_text(
    filename,
    text,
    size=64,
    features=None,
    script=None,
    lang=None,
):
    with tempfile.NamedTemporaryFile(suffix=".png") as out:
        renderText(filename, text, outputPath=out.name, fontSize=size, backendName="skia", script=str(script), lang=str(lang))
        img = Image.open(out.name)
        arr = np.asarray(img)
    return arr


if __name__ == "__main__":
    import argparse
    import re

    parser = argparse.ArgumentParser(description="Draw some text")
    parser.add_argument("font", metavar="TTF")
    parser.add_argument("string", metavar="TEXT")
    parser.add_argument("--out", metavar="PNG", default="out.png")
    parser.add_argument("--lang", metavar="LANGUAGE")
    parser.add_argument("--script", metavar="SCRIPT")
    parser.add_argument("--features", metavar="FEATURES")
    args = parser.parse_args()
    features = None
    if args.features:
        features = {}
        for f in args.features.split(","):
            if f[0] == "-":
                features[f[1:]] = False
            elif f[0] == "+":
                features[f[1:]] = True
            else:
                features[f] = True

    img = draw_text(
        args.font, args.string, lang=args.lang, script=args.script, features=features
    )
    from PIL import Image

    I = Image.fromarray(img[::-1, ::1])
    I.save(args.out)
