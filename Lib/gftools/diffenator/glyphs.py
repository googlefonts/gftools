from itertools import permutations
import itertools
from fontFeatures.ttLib.GSUBUnparser import GSUBUnparser
from fontFeatures.ttLib import unparseLanguageSystems
from fontFeatures import FontFeatures
from argparse import ArgumentParser
from fontTools.ttLib import TTFont
from fontTools.subset import Options
from fontTools.ttLib import TTFont
import uharfbuzz as hb
from fontTools.ttLib import TTFont



MATRAS = [
    chr(0x093F), #dev2
    chr(0x09BF) #beng
]

class GlyphCombinator:
    def __init__(self, ttFont, hbFont, features={"kern": True, "liga": True}):
        self.ttFont = ttFont
        self.hbFont = hbFont

        self.glyphs = {v: chr(k) for k, v in self.ttFont.getBestCmap().items()}
        self.reverse_glyphs = {chr(k): v for k,v in self.ttFont.getBestCmap().items()}
        self.gids = {idx: n for idx, n in enumerate(self.ttFont.getGlyphOrder())}
        self.reverse_gids = {n: idx for idx, n in enumerate(self.ttFont.getGlyphOrder())}
        self.dotted_circle = self.reverse_glyphs.get("◌", "")
        self.routine_map = {}
        self.features = features 
        self.script = "DFLT"
        self.language = "dflt"
        self.ff = FontFeatures()

        if "GSUB" not in self.ttFont:
            self.languageSystems = {}
            return
        self.languageSystems = unparseLanguageSystems([self.ttFont["GSUB"]])
        unparsed = GSUBUnparser(
            self.ttFont["GSUB"], self.ff, self.languageSystems, font=self.ttFont, config={}
        )
        unparsed.unparse(doLookups=True)

        for feat, routines in self.ff.features.items():
            for r in routines:
                self.routine_map[r.name] = feat
    
    def get_combinations(self, features=None, script=None, language=None):
        self.features = features or self.features
        self.script = script or self.script
        self.language = language or self.language
        if "GSUB" not in self.ttFont:
            return
        for routine in self.ff.routines:
            self._process_routine(routine)

    def shape(self, text):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        buf.set_script_from_ot_tag(str(self.script))
        buf.set_language_from_ot_tag(str(self.language))

        hb.shape(self.hbFont, buf, self.features)

        infos = buf.glyph_infos
        return ["".join(self.gids[i.codepoint]) for i in infos]

    def get_ligs(self, combo):
        for c in range(len(combo)+1):
            for j in range(c+1, len(combo) + 1):
                left = list(combo[:c]) if len(combo[:c]) > 0 else []
                right = list(combo[j:]) if len(combo[j:]) > 0 else []
                r = left + ["-".join(combo[c:j])] + right
                r = [i for i in r if len(i) > 0]
                if not all(i in self.glyphs for i in r):
                    continue
                yield r

    def get_replacement(self, rule, input, seen=set()):
        if hasattr(rule, "replacement"):
            return rule.replacement

        replacement = []
        for lk in rule.lookups:
            if not lk:
                continue
            self._process_routine(lk[0].routine)
            seen.add(rule)
            replacement += [
                self.get_replacement(r, input, seen)[0] for r in lk[0].routine.rules
            ]
        return replacement
    
    def get_char_input(self, combo, feature=None):
        """Convert glyph names to unicode characters and do basic reordering"""
        seq = [self.glyphs[c] for c in combo]
        # MF primitive glyph reordering. Add new scripts when required.
        if feature == "pres":
            if seq[0] in MATRAS: # swap dMatraI around
                seq[0],seq[-1] = seq[-1], seq[0]
        if feature == "rphf":
            seq.append("◌")
        if feature == "abvs":
            seq.append("◌")
        # TODO generalise this
        # decompose clusters
        if "र्ं" in seq and len(combo) > 1: # deva
            seq.remove("र्ं")
            seq.remove("◌")
            seq.insert(0, "र्")
            seq.append("ं")
        if 'র্ঁ' in seq and len(combo) > 1: # beng
            seq.remove('র্ঁ')
            seq.insert(0, 'র্')
            seq.append('ঁ')
        return seq

    def _process_routine(self, routine):
        try:
            feature = self.routine_map[routine.name]
        except:
            feature = None

        for rule in routine.rules:

            fullinput = (
                rule.precontext
                + getattr(rule, "input", [])
                + getattr(rule, "glyphs", [])
                + rule.postcontext
            )

            # Skip large inputs
            # TODO: Return groups instead of flattening!
            total = 1
            for s in fullinput:
                total *= len(s)
            if total >= 500000:
                print(f"Skipping rule: {rule} too many inputs!",)
                break

            combinations = itertools.product(*fullinput)
            found_shaping = False
            original = None
            for fcombo in combinations:
                for combo in self.get_ligs(fcombo):

                    replacement = self.get_replacement(rule, combo, seen=set())

                    char_input = self.get_char_input(combo, feature)
                    if not original:
                        original = "".join(char_input).replace("◌", "")

                    # TODO: improving self.get_char_input will drop the need for us to use
                    # permutations
                    perms = permutations(char_input)
                    for perm in perms:
                        string = "".join(perm)
                        # XXX There is a problem here for rules which apply in the
                        # middle of an orthographic cluster. For example, a rule
                        # like "sub uni192A uni1922 by uni192A1922" should ligate
                        # the two mark glyphs. However, since we are feeding the
                        # two characters in alone without a preceding base glyph,
                        # the shaper will first insert dotted circles before each
                        # one, separating them into different clusters and causing
                        # the rule not to fire.
                        hb_res = self.shape(string)

                        for g in hb_res:
                            if not any(g in rep for rep in replacement):
                                continue

                            found_shaping = True
                            if self.dotted_circle in hb_res:
                                key = hb_res.remove(self.dotted_circle)
                            key = "-".join(hb_res)
                            # Do not overwite combos which have already been found.
                            if key in self.glyphs:
                                continue
                            self.glyphs[key] = string.replace("◌", "")
                            break
            # Certain features will only produce the given result after another feature has been applied
            # this happens with the 'half' feature. TODO test and add more
            if not found_shaping:
                if feature in ["half"]:
                    print(f"manually adding", replacement[0][0], original)
                    self.glyphs[replacement[0][0]] = original


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python ./Lib/gftools/glyphs.py font.ttf")
        sys.exit()
    font_path = sys.argv[1]
    if len(sys.argv) >= 3:
        features = {i: True for i in sys.argv[2].split(",")}
    else:
        features = {"kern": True, "liga": True}
    ttFont = TTFont(font_path)
    g = GlyphCombinator(ttFont, features)
    g.get_combinations()
    print(g.glyphs)
    print(f"total: {len(g.glyphs)}")