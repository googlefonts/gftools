from gftools.spec.font import __doc__ as header
from gftools.spec.font import (
    SpecFSType,
    SpecHinting,
    SpecInstances,
    SpecMonospace,
)

def load_specs():
    return [v for k,v in globals().items() if k.startswith("Spec") if k != "BaseSpec"]


class FixFonts:
    def __init__(self, fonts, specs=load_specs(), license="ofl"):
        self.fonts = fonts
        self.specs = specs
        self.license = license
        self.report = []
        self.diff = {}
    
    def fix(self, produce_diffs=True):
        for font in self.fonts:
            for spec in self.specs:
                s = spec(font)
                s.fix()


def _build_toc(specs):
    res = []
    for spec in specs:
        res.append(f"- [{spec.TITLE}](#{spec.TITLE.replace(' ', '-')})")
    return res


def generate_spec(specs=load_specs()):
    text = [header] + _build_toc(specs)
    for spec in specs:
        text.append(f"## {spec.TITLE}")
        text.append(spec.TEXT + '\n')
        if spec.LINKS:
            text += ["<details>", "<summary>Further reading</summary>"]
            text += spec.LINKS
            text += ["</details>\n"]
    return "\n".join(text)
