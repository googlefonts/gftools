import sys
import random
import subprocess
import re
import time


def fuzz_fonts(old_font, new_font, duration=60):
    """TODO this is ultra basic and terrible. Rework once noto is done"""
    chars = list(old_font.getBestCmap().keys())
    chars = [i for i in chars if i not in [45] + list(range(33))]

    now = time.time()

    res = []
    count = 0
    warn = 0
    while time.time() < now + duration:
        string = "".join(chr(random.choice(chars)) for i in range(random.randint(1, 9)))
        res1 = subprocess.check_output(["hb-shape", old_font.reader.file.name, string])
        res1 = ",".join(i.split("=")[0] for i in re.split(r"[\[\|]", res1.decode("utf-8")) if i)
        res2 = subprocess.check_output(["hb-shape", new_font.reader.file.name, string])
        res2 = ",".join(i.split("=")[0] for i in re.split(r"[\[\|]", res2.decode("utf-8")) if i)
        if res1 != res2:
            res.append(string)
            print(string)
            warn += 1
        count += 1
    print(f"tested: {count} warn: {warn}")
    return res



def input_fuzz(font):
    from gftools.diffenator import DFont
    from random import choices, randint
    import uharfbuzz as hb
    font = DFont(font)

    blob = hb.Blob.from_file_path(font.path)
    hbface = hb.Face(blob)
    hbfont = hb.Font(hbface)


    glyphs_to_find = font.ttFont.getGlyphNames()
    glyph_order = font.ttFont.getGlyphOrder()
    ff = font.glyph_combinator.ff
    ff.hoist_languages()
    features = ff.features
    scripts_and_langs = ff.scripts_and_languages
    seen = {v: (chr(k), None, None, None) for k,v in font.ttFont.getBestCmap().items()}
    strings = []
    for script, langs in scripts_and_langs.items():
        for lang in langs:
            for feat, routines in features.items():
                if feat == "aalt":
                    continue
                for routine in routines:
                    routine = routine.routine
                    glyph_sack = list(routine.involved_glyphs)

                    char_input = [seen[c] for c in glyph_sack if c in seen]

                    input_string = "".join([c[0] for c in char_input])
                    input_langs = set(c[1] for c in char_input)
                    input_scripts = set(c[2] for c in char_input)
                    input_feats = {feat: True}
                    input_feats[feat] = True

                    buf = hb.Buffer()
                    buf.add_str(input_string)
                    buf.guess_segment_properties()

                    hb.shape(hbfont, buf, features=input_feats)
                    
                    infos = buf.glyph_infos


                    import pdb
                    pdb.set_trace()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python Lib/gftools/diffenator/fuzzer.py font1.ttf font2.ttf")
        sys.exit()
    input_fuzz(sys.argv[1])