#!/usr/bin/env python3
"""
Rearrange the features in a font file: drop features
or move lookups into another feature or language system.
"""
from argparse import ArgumentParser, RawTextHelpFormatter
from fontTools.ttLib import TTFont
import re
import logging

logging.basicConfig(level=logging.INFO)

parser = ArgumentParser(description=__doc__, formatter_class=RawTextHelpFormatter)
parser.add_argument("font", help="Font file")
parser.add_argument("-o", help="Output font file")
parser.add_argument(
    "commands",
    nargs="+",
    help="""\
Commands to rearrange the features in the font file.

Features and lookups are specified like so:
    <feature> = [script/][lang/]<feature>

If lookup id is not given, then all lookups in the feature are affected.
If script or lang are not given, then DFLT and dflt are assumed.
(The script and lang tags do not need to be padded to four characters.)

Commands may be:

* `!<feature>` to drop a feature.
* `<feature> -> <feature2>` to add the lookups to the end of feature2.
* `<feature> => |<feature2>` to move the lookups to the start of feature2.
* `<feature> -> <feature2>` to add the lookups to the end of feature2.
* `<feature> => |<feature2>` to move the lookups to the start of feature2.
""",
)
LAYOUT_TABLES = ["GSUB", "GPOS"]
KEY_RE = r"(?:(\w+)/)?(?:(\w+)/)?(\w+)"


def parse_key(key):
    match = re.match(KEY_RE, key)
    if match is None:
        raise ValueError(f"Invalid feature or lookup: {key}")
    script, lang, feature = match.groups()
    script = (script or "DFLT").ljust(4)
    lang = (lang or "dflt").ljust(4)
    return script, lang, feature


def find_langsys(table, script, lang):
    tag = type(table).__name__
    scripts = [
        sr.Script for sr in table.ScriptList.ScriptRecord if sr.ScriptTag == script
    ]
    if not scripts:
        logging.info(f"[{tag}] Script not found: {script}")
        return
    if lang == "dflt":
        langsys = scripts[0].DefaultLangSys
    else:
        langsys = [
            ls.LangSys for ls in scripts[0].LangSysRecord if ls.LangSysTag == lang
        ]
        if not langsys:
            logging.info(f"[{tag}] Language system not found: {lang}")
            return
        langsys = langsys[0]
    return langsys

def delete_feature(table, script, lang, feature):
    tag = type(table).__name__
    langsys = find_langsys(table, script, lang)
    featurelist = table.FeatureList.FeatureRecord
    logging.info(f"[{tag}] Feature indices were: {langsys.FeatureIndex}")
    langsys.FeatureIndex = [
        i for i in langsys.FeatureIndex if featurelist[i].FeatureTag != feature
    ]
    logging.info(f"[{tag}] Feature indices are now: {langsys.FeatureIndex}")

def delete_lookup(table, script, lang, feature, lookup):
    tag = type(table).__name__
    langsys = find_langsys(table, script, lang)
    featurelist = table.FeatureList.FeatureRecord
    done = False
    for i in langsys.FeatureIndex:
        if featurelist[i].FeatureTag != feature:
            continue
        lookups = featurelist[i].Feature.LookupListIndex
        if lookup in lookups:
            lookups.remove(lookup)
            logging.info(f"[{tag}] Removed lookup {lookup} from {feature}")
            done = True
    if not done:
        logging.info(f"[{tag}] Lookup {lookup} not found in {feature}")    

def remap_lookups(table, src, dst, operation="copy", start=False):
    tag = type(table).__name__
    src_script, src_lang, src_feature = src
    dst_script, dst_lang, dst_feature = dst
    src_langsys = find_langsys(table, src_script, src_lang)
    dst_langsys = find_langsys(table, dst_script, dst_lang)
    if not src_langsys:
        logging.error(f"[{tag}] Languagesystem {src_script}/{src_lang} not found")
        return
    if not dst_langsys:
        logging.error(f"[{tag}] Languagesystem {dst_script}/{dst_lang} not found")
        return
    src_features = src_langsys.FeatureIndex
    dst_features = dst_langsys.FeatureIndex
    src_lookups = []
    featurelist = table.FeatureList.FeatureRecord
    for src_feature_index in src_features:
        if featurelist[src_feature_index].FeatureTag == src_feature:
            src_lookups.extend(featurelist[src_feature_index].Feature.LookupListIndex)
            if operation == "move":
                featurelist[src_feature_index].Feature.LookupListIndex = []
    if not src_lookups:
        logging.info(f"[{tag}] No lookups found")
        return
    
    for dst_feature_index in dst_features:
        if featurelist[dst_feature_index].FeatureTag == dst_feature:
            dst_feature = featurelist[dst_feature_index].Feature
            if start:
                dst_feature.LookupListIndex = src_lookups + dst_feature.LookupListIndex
            else:
                dst_feature.LookupListIndex.extend(src_lookups)
            logging.info(f"[{tag}] {operation} lookups {src_lookups} to {featurelist[dst_feature_index].FeatureTag}")
            return
    logging.error(f"[{tag}] destination feature {dst_script}/{dst_lang}/{dst_feature} not found")
    
def main(args=None):
    args = parser.parse_args()
    ttfont = TTFont(args.font)
    tables = [ttfont[table].table for table in LAYOUT_TABLES if table in ttfont]
    for cmd in args.commands:
        if cmd.startswith("!"):
            script, lang, feature = parse_key(cmd[1:])
            for table in tables:
                delete_feature(table, script, lang, feature)
            continue
        src = re.match(KEY_RE, cmd)
        if src is None:
            raise ValueError(f"Could not parse source: {cmd}")
        cmd = cmd[len(src.group(0)):]

        remap = None
        if re.match(r"^\s*->\s*", cmd):
            remap = "copy"
        elif re.match(r"^\s*=>\s*", cmd):
            remap = "move"
        else:
            raise ValueError(f"Could not parse operation: {cmd}")
        dst = re.sub(r"^\s*->\s*|\s*=>\s*", "", cmd).strip()

        start = False
        if dst.startswith("|"):
            dst = dst[1:]
            start = True
        dst = re.match(KEY_RE, dst)
        if dst is None:
            raise ValueError(f"Could not parse destination: {cmd}")
        for table in tables:
            remap_lookups(
                table, parse_key(src[0]), parse_key(dst[0]), operation=remap, start=start
            )

    if args.o:
        ttfont.save(args.o)
    else:
        ttfont.save(args.font)

if __name__ == "__main__":
    main()