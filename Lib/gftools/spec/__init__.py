from gftools.spec.font import (
    SpecFSType,
    SpecHinting,
    SpecInstances,
    SpecItalicAngle,
    SpecMonospace,
)

def load_specs():
    return [v for k,v in globals().items() if k.startswith("Spec") if k != "BaseSpec"]


class FixFonts:
    def __init__(self, fonts, specs=load_specs()):
        self.fonts = fonts
        self.specs = specs
        self.report = []
        self.diff = {}
    
    def fix(self, produce_diffs=True):
        for font in self.fonts:
            for spec in self.specs:
                s = spec(font)
                s.fix()
