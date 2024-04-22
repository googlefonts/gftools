#!/usr/bin/env python3
"""
Rearrange the features in a font file: drop features
or move lookups into another feature or language system.
"""
from collections import defaultdict
import logging
import re
from argparse import ArgumentParser, RawTextHelpFormatter
from typing import List, Tuple

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables

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
KEY_RE = r"(?:(\w+|\*)/)?(?:(\w+|\*)/)?(\w+|\*)"


def parse_key(key):
    """Parse a language system and feature tag combination"""
    match = re.match(KEY_RE, key)
    if match is None:
        raise ValueError(f"Invalid feature or lookup: {key}")
    script, lang, feature = match.groups()
    script = (script or "*").ljust(4)
    lang = (lang or "*").ljust(4)
    return script, lang, feature


def build_targets(
    src_langsyses: List[Tuple[str, str]], dst_langsyses: List[Tuple[str, str]]
):
    targets = []
    # Many to one
    if len(src_langsyses) > 1 and len(dst_langsyses) == 1:
        dst = dst_langsyses[0]
        for src in src_langsyses:
            targets.append((src, dst))
    # One to many
    elif len(src_langsyses) == 1 and len(dst_langsyses) > 1:
        src = src_langsyses[0]
        for dst in dst_langsyses:
            targets.append((src, dst))
    elif len(src_langsyses) == 1 and len(dst_langsyses) == 1:
        targets.append((src_langsyses[0], dst_langsyses[0]))
    # Many to many
    elif len(src_langsyses) == len(dst_langsyses):
        if src_langsyses != dst_langsyses:
            logging.error(
                "Source and destination language systems do not match: %s vs %s",
                src_langsyses,
                dst_langsyses,
            )
            return []
        for src in src_langsyses:
            targets.append((src, src))
    return targets


def freeze_lookuplist(table):
    """Turns the header of a GSUB/GPOS table into a dictionary, keyed by
    (script,lang) with the values being dictionaries mapping feature tags
    to a list of lookup indices."""
    params = {}
    lookuplist = defaultdict(lambda: defaultdict(list))
    featurelist = table.FeatureList.FeatureRecord

    def freeze_langsys(script_tag, lang_tag, langsys):
        for index in langsys.FeatureIndex:
            feature_tag = featurelist[index].FeatureTag
            params[feature_tag] = featurelist[index].Feature.FeatureParams
            lookups = featurelist[index].Feature.LookupListIndex
            lookuplist[(script_tag, lang_tag)][feature_tag].extend(lookups)

    for scriptrecord in table.ScriptList.ScriptRecord:
        script_tag = scriptrecord.ScriptTag
        freeze_langsys(script_tag, "dflt", scriptrecord.Script.DefaultLangSys)
        for langsys in scriptrecord.Script.LangSysRecord:
            freeze_langsys(script_tag, langsys.LangSysTag, langsys.LangSys)
    return lookuplist, params


def thaw_lookuplist(table, lookuplist, params):
    """Builds a feature list from a lookup list dictionary. Patterned after
    fontTools.feaLib.builder.makeTable."""
    table.FeatureList = otTables.FeatureList()
    table.FeatureList.FeatureRecord = []
    combinations = []  # List of (script, lang, feature_tag, indices)
    for (script, lang), features in lookuplist.items():
        for feature_tag, indices in features.items():
            combinations.append((script, lang, feature_tag, tuple(indices)))
    # Sort combinations by feature tag
    combinations.sort(key=lambda x: x[2])
    # Build the list
    feature_indices = {}
    new_langsys_feature_indices = defaultdict(list)
    for script, lang, feature_tag, lookup_indices in combinations:
        feature_key = (feature_tag, lookup_indices)
        feature_index = feature_indices.get(feature_key)
        feature_index = feature_indices.get(feature_key)
        if feature_index is None:
            feature_index = len(table.FeatureList.FeatureRecord)
            frec = otTables.FeatureRecord()
            frec.FeatureTag = feature_tag
            frec.Feature = otTables.Feature()
            frec.Feature.FeatureParams = params.get(feature_tag, None)
            frec.Feature.LookupListIndex = list(lookup_indices)
            frec.Feature.LookupCount = len(lookup_indices)
            table.FeatureList.FeatureRecord.append(frec)
            feature_indices[feature_key] = feature_index
        new_langsys_feature_indices[(script, lang)].append(feature_index)

    # Build the script list
    def fixup_feature_indices(langsys, indices):
        if indices:
            langsys.FeatureIndex = indices
        else:
            langsys.FeatureIndex = []
        langsys.FeatureCount = len(langsys.FeatureIndex)

    for scriptrecord in table.ScriptList.ScriptRecord:
        script_tag = scriptrecord.ScriptTag
        fixup_feature_indices(
            scriptrecord.Script.DefaultLangSys,
            new_langsys_feature_indices.get((script_tag, "dflt")),
        )
        for langsys in scriptrecord.Script.LangSysRecord:
            fixup_feature_indices(
                langsys.LangSys,
                new_langsys_feature_indices.get((script_tag, langsys.LangSysTag)),
            )


def find_langsyses(lookuplist, wanted_script, wanted_lang):
    """Find the language systems in a lookup list"""
    matching = []
    for script, lang in lookuplist.keys():
        if (script == wanted_script or wanted_script == "*   ") and (
            lang == wanted_lang or wanted_lang == "*   "
        ):
            matching.append((script, lang))
    return matching


def de_default(d):
    """Turn a defaultdict into an ordinary dictionary"""
    return {k: dict(v) for k, v in d.items()}


def remap_lookups(table, src, dst, operation="copy", start=False):
    tag = type(table).__name__
    src_script, src_lang, src_feature_name = src
    dst_script, dst_lang, dst_feature_name = dst
    lookuplists, params = freeze_lookuplist(table)
    src_langsyses = find_langsyses(lookuplists, src_script, src_lang)
    dst_langsyses = find_langsyses(lookuplists, dst_script, dst_lang)
    logging.debug("[%s] Before: %s", tag, de_default(lookuplists))
    to_remove = set()
    if not src_langsyses:
        logging.error(f"[%s] Languagesystem {src_script}/{src_lang} not found", tag)
        return
    for (src_script, src_lang), (dst_script, dst_lang) in build_targets(
        src_langsyses, dst_langsyses
    ):
        key = src_script + "/" + src_lang
        if src_feature_name not in lookuplists[(src_script, src_lang)]:
            logging.info("[%s/%s] No source feature found", tag, key)
            continue
        lookups = lookuplists[(src_script, src_lang)][src_feature_name]
        if operation == "move":
            to_remove.add((src_script, src_lang, src_feature_name, tuple(lookups)))
        logging.info(
            "[%s/%s/%s] Adding lookups %s",
            tag,
            dst_script + "/" + dst_lang,
            dst_feature_name,
            lookups,
        )
        if start:
            lookuplists[(dst_script, dst_lang)][dst_feature_name] = (
                lookups + lookuplists[(dst_script, dst_lang)][dst_feature_name]
            )
        else:
            lookuplists[(dst_script, dst_lang)][dst_feature_name].extend(lookups)
    for script, lang, feature, lookups in to_remove:
        logging.info(
            "[%s/%s/%s/%s] Removing lookups %s",
            tag,
            script,
            lang,
            feature,
            list(lookups),
        )
        lookuplists[(script, lang)][feature] = [
            l for l in lookuplists[(script, lang)][feature] if l not in lookups
        ]
    logging.debug("[%s] After: %s", tag, de_default(lookuplists))
    thaw_lookuplist(table, lookuplists, params)


def delete_feature(table, script, lang, feature):
    tag = type(table).__name__
    lookuplists, params = freeze_lookuplist(table)
    logging.debug("[%s] Before: %s", tag, de_default(lookuplists))
    src_langsyses = find_langsyses(lookuplists, script, lang)
    for src_script, src_lang in src_langsyses:
        key = src_script + "/" + src_lang
        if feature not in lookuplists[(src_script, src_lang)]:
            logging.info("[%s/%s] No source feature found", tag, key)
            continue
        lookuplists[(src_script, src_lang)][feature] = []
        logging.info("[%s/%s] Removed feature %s", tag, key, feature)
    logging.debug("[%s] After: %s", tag, de_default(lookuplists))
    thaw_lookuplist(table, lookuplists, params)


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
        cmd = cmd[len(src.group(0)) :]

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
                table,
                parse_key(src[0]),
                parse_key(dst[0]),
                operation=remap,
                start=start,
            )

    if args.o:
        ttfont.save(args.o)
    else:
        ttfont.save(args.font)


if __name__ == "__main__":
    main()
