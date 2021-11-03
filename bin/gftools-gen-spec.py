from gftools.fix import (
    __doc__ as fix_header,
    FixFSType,
    FixHinting,
    FixInstances,
)
import re
import sys

print(len(sys.argv))
if len(sys.argv) != 2:
    print("usage: gftools gen_spec out.txt")
    sys.exit()

out = sys.argv[1]


def build_toc(fixes):
    res = []
    for fix in fixes:
        title = re.search(r"(?<=## ).*", fix.__doc__).group(0)
        res.append(f"- [{title}](#{title.replace(' ', '-')})")
    return res


fixes = [v for k,v in globals().items() if k.startswith("Fix")]

text = [fix_header] + build_toc(fixes) + [f.__doc__ for f in fixes]

with open(out, "w") as doc:
    doc.write("\n".join(text))
