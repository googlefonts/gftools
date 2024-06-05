#!/usr/bin/env python3
"""
gftools lang-support

Adds language support metadata to METADATA.pb files.

Usage:

# Standard usage. Does not overwrite existing data.
gftools lang-support -l ./lang/ ./ofl/noto*/METADATA.pb

# Generate a report with insights about data and potential metadata holes.
gftools lang-support -l ./lang/ -r ./ofl/noto*/METADATA.pb

"""

import argparse
from fontTools.ttLib import TTFont
from gflanguages import LoadLanguages, LoadScripts
from gftools import fonts_public_pb2
from gftools.util import google_fonts as fonts
from google.protobuf import text_format
from pkg_resources import resource_filename
import csv
import os
from pkg_resources import resource_filename

parser = argparse.ArgumentParser(
    description="Add language support metadata to METADATA.pb files"
)
parser.add_argument("--lang", "-l", help="Path to lang metadata package")
parser.add_argument(
    "--report",
    "-r",
    action="store_true",
    help="Whether to output a report of lang metadata insights",
)
parser.add_argument(
    "--sample_text_audit",
    "-s",
    action="store_true",
    help="Whether to run the sample text audit",
)
parser.add_argument("--out", "-o", help="Path to output directory for report")
parser.add_argument("metadata_files", help="Path to METADATA.pb files", nargs="+")


def _WriteCsv(path, rows):
    with open(path, "w", newline="") as csvfile:
        writer = csv.writer(
            csvfile, delimiter="\t", quotechar='"', quoting=csv.QUOTE_MINIMAL
        )
        for row in rows:
            writer.writerow(row)


def _WriteReport(metadata_paths, out_dir, languages):
    rows = [
        [
            "id",
            "name",
            "lang",
            "script",
            "population",
            "ec_base",
            "ec_auxiliary",
            "ec_marks",
            "ec_numerals",
            "ec_punctuation",
            "ec_index",
            "st_fallback",
            "st_fallback_name",
            "st_masthead_full",
            "st_masthead_partial",
            "st_styles",
            "st_tester",
            "st_poster_sm",
            "st_poster_md",
            "st_poster_lg",
            "st_specimen_48",
            "st_specimen_36",
            "st_specimen_32",
            "st_specimen_21",
            "st_specimen_16",
        ]
    ]

    without_lang = []
    without_sample_text = []
    supported_without_sample_text = {}
    for metadata_path in metadata_paths:
        family = fonts.ReadProto(fonts_public_pb2.FamilyProto(), metadata_path)
        if len(family.languages) == 0:
            without_lang.append(family.name)
        else:
            supports_lang_with_sample_text = False
            for lang_code in family.languages:
                if languages[lang_code].HasField("sample_text"):
                    supports_lang_with_sample_text = True
                    break
            if not supports_lang_with_sample_text:
                without_sample_text.append(family.name)
        for l in family.languages:
            if (
                not languages[l].HasField("sample_text")
                and l not in supported_without_sample_text
            ):
                supported_without_sample_text[l] = languages[l]

    for lang in supported_without_sample_text.values():
        rows.append([lang.id, lang.name, lang.language, lang.script, lang.population])

    path = os.path.join(out_dir, "support.csv")
    _WriteCsv(path, rows)


def _SampleTextAudit(out_dir, languages, scripts, unused_scripts=[]):
    rows = [["id", "language", "script", "has_sample_text", "historical"]]
    # sort by script|has_sample_text|historical|id
    entries = []

    min_sample_text_languages = 0
    by_script = {}
    for l in languages.values():
        if l.script not in by_script:
            by_script[l.script] = []
        by_script[l.script].append(l)
    for script in by_script:
        if script in unused_scripts:
            continue
        languages_with_sample_text = {
            l.id
            for l in by_script[script]
            if l.HasField("sample_text")
            and not l.sample_text.HasField("fallback_language")
        }
        non_historical_languages_without_sample_text = [
            l
            for l in by_script[script]
            if not l.historical and l.id not in languages_with_sample_text
        ]
        if len(languages_with_sample_text) < 2:
            if (
                len(languages_with_sample_text) == 1
                and len(by_script[script]) > 1
                and len(non_historical_languages_without_sample_text) > 1
            ):
                min_sample_text_languages += 1
            elif len(languages_with_sample_text) == 0:
                if len(non_historical_languages_without_sample_text) > 1:
                    min_sample_text_languages += 2
                else:
                    min_sample_text_languages += 1

        if len(languages_with_sample_text) == 0 or (
            len(languages_with_sample_text) == 1
            and len([l for l in by_script[script] if not l.historical]) > 1
        ):
            for l in by_script[script]:
                entries.append(
                    {
                        "id": l.id,
                        "language": l.name,
                        "script": scripts[l.script].name,
                        "has_sample_text": l.id in languages_with_sample_text,
                        "historical": l.historical,
                    }
                )

    print(min_sample_text_languages)

    last_script = None
    entries.sort(
        key=lambda x: (
            x["script"],
            not x["has_sample_text"],
            not x["historical"],
            x["id"],
        )
    )
    for e in entries:
        if last_script is not None and e["script"] != last_script:
            rows.append([])
        rows.append(
            [
                e["id"],
                e["language"],
                e["script"],
                "X" if e["has_sample_text"] else "",
                "X" if e["historical"] else "",
            ]
        )
        last_script = e["script"]

    path = os.path.join(out_dir, "sample_text_audit.csv")
    _WriteCsv(path, rows)


def main(args=None):
    args = parser.parse_args(args)
    languages = LoadLanguages(base_dir=args.lang)
    scripts = LoadScripts(base_dir=args.lang)

    if args.report:
        assert len(argv) > 1, "No METADATA.pb files specified"
        assert args.out is not None, "No output dir specified (--out)"
        print("Writing insights report...")
        _WriteReport(argv[1:], args.out, languages)
    elif args.sample_text_audit:
        assert args.out is not None, "No output dir specified (--out)"
        print("Auditing sample text")
        seen_scripts = set()
        unused_scripts = set()
        for path in argv[1:]:
            family = fonts.ReadProto(fonts_public_pb2.FamilyProto(), path)
            for l in family.languages:
                seen_scripts.add(languages[l].script)
        for s in scripts:
            if s not in seen_scripts:
                unused_scripts.add(s)
        _SampleTextAudit(args.out, languages, scripts, unused_scripts)
    else:
        for path in args.metadata_files:
            family_metadata = fonts.ReadProto(fonts_public_pb2.FamilyProto(), path)
            if len(family_metadata.languages) > 0:
                continue
            exemplar_font_fp = os.path.join(
                os.path.dirname(path), fonts.GetExemplarFont(family_metadata).filename
            )
            exemplar_font = TTFont(exemplar_font_fp)
            supported_languages = fonts.SupportedLanguages(exemplar_font, languages)
            if family_metadata.HasField("is_noto") and family_metadata.is_noto:
                supported_languages = [
                    l for l in supported_languages if "Latn" not in l.id
                ]
            supported_languages = sorted([l.id for l in supported_languages])
            family_metadata.languages.extend(supported_languages)
            fonts.WriteMetadata(family_metadata, path)


if __name__ == "__main__":
    main()
