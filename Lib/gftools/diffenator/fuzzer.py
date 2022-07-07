from fontTools.ttLib import TTFont
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


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python Lib/gftools/diffenator/fuzzer.py font1.ttf font2.ttf")
        sys.exit()
    f1 = TTFont(sys.argv[1])
    f2 = TTFont(sys.argv[2])
    fuzz_fonts(f1, f2)