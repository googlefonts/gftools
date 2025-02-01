#!/usr/bin/env python3
# Copyright 2018 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Utility to setup a font for addition to Piper.


Generate METADATA.pb files for font families.

METADATA.pb files are used to serve the families on http://fonts.google.com.
Font families are stored in this repo by license type. The following
directories contain font families:

../fonts/ofl
../fonts/apache
../fonts/ufl

Generating a METADATA.pb file for a new family:

1. Determine the family's license type, ofl, ufl or apache
2. Create a new folder under the license type directory
3. Name the folder so it's the family name, all lowercase and no spaces.
4. Run the following: gftools add-font /path/to/new/family
5. Update the category field in the generated METADATA.pb file.

Generating a METADATA.pb file for an existing family:

1. run the following: gftools add-font /path/to/existing/family
"""
from __future__ import print_function
from functools import cmp_to_key
import argparse
import contextlib
import errno
import glob
import re
import os
import sys
import time
from fontTools import ttLib


from gflanguages import LoadLanguages
import gftools.fonts_public_pb2 as fonts_pb2
from gftools.util import google_fonts as fonts
from gftools.utils import cmp
from axisregistry import AxisRegistry
from gfsubsets import SubsetsInFont
from google.protobuf import text_format
from pkg_resources import resource_filename
from gftools.utils import remove_url_prefix, primary_script


RELAXED_SUBSETS = ["math", "symbols"]

axis_registry = AxisRegistry()


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--min_pct",
    type=int,
    default=50,
    help="What percentage of subset codepoints have to be supported"
    " for a non-ext subset.",
)
parser.add_argument(
    "--min_pct_ext",
    type=float,
    default=2,
    help="What percentage of subset codepoints have to be supported"
    " for a -ext subset.",
)
parser.add_argument(
    "--min_relaxed_pct",
    type=int,
    default=50,
    help="What percentage of subset codepoints have to be supported"
    f' for a relaxed subset ({", ".join(RELAXED_SUBSETS)}).',
)
parser.add_argument(
    "--lang", type=str, help="Path to lang metadata package", default=None
)
parser.add_argument("directory", type=str, help="A directory containing a font family")
parser.add_argument(
    "--github_url",
    type=str,
    default=None,
    help="The font family's github url which gets written to new description files",
)


def _FileFamilyStyleWeights(fontdir):
    """Extracts file, family, style, weight 4-tuples for each font in dir.

    Args:
      fontdir: Directory that supposedly contains font files for a family.
    Returns:
      List of fonts.FileFamilyStyleWeightTuple ordered by weight, style
      (normal first).
    Raises:
      OSError: If the font directory doesn't exist (errno.ENOTDIR) or has no font
      files (errno.ENOENT) in it.
      RuntimeError: If the font directory appears to contain files from multiple
      families.
    """
    if not os.path.isdir(fontdir):
        raise OSError(errno.ENOTDIR, "No such directory", fontdir)

    files = glob.glob(os.path.join(fontdir, "*.[ot]tf"))
    if not files:
        raise OSError(errno.ENOENT, "no font files found")

    result = [fonts.FamilyStyleWeight(f) for f in files]

    def _Cmp(r1, r2):
        return cmp(r1.weight, r2.weight) or -cmp(r1.style, r2.style)

    result = sorted(result, key=cmp_to_key(_Cmp))

    family_names = {i.family for i in result}
    if len(family_names) > 1:
        raise RuntimeError("Ambiguous family name; possibilities: %s" % family_names)

    return result


def _MakeMetadata(args, is_new):
    """Builds a dictionary matching a METADATA.pb file.

    Args:
      fontdir: Directory containing font files for which we want metadata.
      is_new: Whether this is an existing or new family.
    Returns:
      A fonts_pb2.FamilyProto message, the METADATA.pb structure.
    Raises:
      RuntimeError: If the variable font axes info differs between font files of
      same family.
    """
    file_family_style_weights = _FileFamilyStyleWeights(args.directory)

    first_file = file_family_style_weights[0].file
    old_metadata_file = os.path.join(args.directory, "METADATA.pb")

    metadata = fonts_pb2.FamilyProto()
    metadata.name = file_family_style_weights[0].family

    subsets_in_font = [
        s[0] for s in SubsetsInFont(first_file, args.min_pct, args.min_pct_ext)
    ]

    relaxed_subsets = set(RELAXED_SUBSETS) & set(
        [
            s[0]
            for s in SubsetsInFont(
                first_file, args.min_relaxed_pct, args.min_relaxed_pct
            )
        ]
    )

    subsets_in_font = list(set(subsets_in_font) | relaxed_subsets)

    if not is_new:
        old_metadata = fonts.ReadProto(fonts_pb2.FamilyProto(), old_metadata_file)
        metadata.designer = old_metadata.designer
        metadata.category[:] = old_metadata.category
        metadata.date_added = old_metadata.date_added
        subsets = set(old_metadata.subsets) | set(subsets_in_font)
        metadata.languages[:] = old_metadata.languages
        metadata.fallbacks.extend(old_metadata.fallbacks)
        if old_metadata.classifications:
            metadata.classifications[:] = old_metadata.classifications
        if old_metadata.stroke:
            metadata.stroke = old_metadata.stroke
        if old_metadata.is_noto:
            metadata.is_noto = True
        if old_metadata.display_name:
            metadata.display_name = old_metadata.display_name
        if old_metadata.primary_script:
            metadata.primary_script = old_metadata.primary_script
        if old_metadata.sample_text and old_metadata.sample_text.ByteSize():
            metadata.sample_text.CopyFrom(old_metadata.sample_text)
        if old_metadata.minisite_url:
            metadata.minisite_url = old_metadata.minisite_url
        if old_metadata.registry_default_overrides:
            metadata.registry_default_overrides.update(
                old_metadata.registry_default_overrides
            )
        if old_metadata.source:
            metadata.source.CopyFrom(old_metadata.source)
    else:
        metadata.designer = "UNKNOWN"
        metadata.category.append("SANS_SERIF")
        metadata.date_added = time.strftime("%Y-%m-%d")
        subsets = ["menu"] + subsets_in_font
        with ttLib.TTFont(file_family_style_weights[0][0]) as ttfont:
            script = primary_script(ttfont)
            if script is not None and script not in (
                "Latn",
                "Cyrl",
                "Grek",
            ):
                metadata.primary_script = script

    try:
        font_license = fonts.LicenseFromPath(args.directory)
        metadata.license = font_license
    except ValueError:
        print("WARNING: Could not determine license for %s" % args.directory)
        print("Continuing without setting license.")
    subsets = sorted(subsets)
    for subset in subsets:
        metadata.subsets.append(subset)

    for fontfile, family, style, weight in file_family_style_weights:
        filename = os.path.basename(fontfile)
        font_psname = fonts.ExtractName(
            fontfile, fonts.NAME_PSNAME, os.path.splitext(filename)[0]
        )
        font_copyright = fonts.ExtractName(
            fontfile, fonts.NAME_COPYRIGHT, "???."
        ).strip()

        font_metadata = metadata.fonts.add()
        font_metadata.name = family
        font_metadata.style = style
        font_metadata.weight = weight
        font_metadata.filename = filename
        font_metadata.post_script_name = font_psname
        default_fullname = os.path.splitext(filename)[0].replace("-", " ")
        font_metadata.full_name = fonts.ExtractName(
            fontfile, fonts.NAME_FULLNAME, default_fullname
        )
        font_metadata.copyright = font_copyright

    axes_info_from_font_files = {_AxisInfo(f.file) for f in file_family_style_weights}
    if len(axes_info_from_font_files) != 1:
        raise RuntimeError("Variable axes info not matching between font files")

    for axes_info in axes_info_from_font_files:
        if axes_info:
            for axes in axes_info:
                var_axes = metadata.axes.add()
                var_axes.tag = axes[0]
                var_axes.min_value = axes[1]
                var_axes.max_value = axes[2]

    registry_overrides = _RegistryOverrides(axes_info_from_font_files)
    if registry_overrides:
        for k, v in registry_overrides.items():
            metadata.registry_default_overrides[k] = v
    return metadata


def _RegistryOverrides(axes_info):
    """Get registry default value overrides for family axes.

    Args:
      axes_info: set of Variable axes info

    Returns:
      A dict structured {axis_tag: font_axis_default_value}
    """
    res = {}
    for font in axes_info:
        for axis_tag, min_val, max_val, dflt_val in font:
            if axis_tag not in axis_registry:
                continue
            default_val = axis_registry[axis_tag].default_value
            if default_val >= min_val and default_val <= max_val:
                continue
            if axis_tag not in res:
                res[axis_tag] = dflt_val
            else:
                res[axis_tag] = min(res[axis_tag], dflt_val)
    return res


def _AxisInfo(fontfile):
    """Gets variable axes info.

    Args:
      fontfile: Font file to look at for variation info

    Returns:
      Variable axes info
    """
    with contextlib.closing(ttLib.TTFont(fontfile)) as font:
        if "fvar" not in font:
            return frozenset()
        else:
            fvar = font["fvar"]
            axis_info = [
                (a.axisTag, a.minValue, a.maxValue, a.defaultValue) for a in fvar.axes
            ]
            return tuple(sorted(axis_info))


def _GetAvgSize(file_family_style_weights):
    """Gets average file size of all font weights.

    Returns:
         average file size.

    Args:
      file_family_style_weights: List of fonts.FileFamilyStyleWeightTuple.
    """
    total_size = 0
    for list_tuple in file_family_style_weights:
        total_size += os.stat(list_tuple.file).st_size
    return total_size / len(file_family_style_weights)


def _WriteTextFile(filename, text):
    """Write text to file.

    Nop if file exists with that exact content. This allows running against files
    that are in Piper and not marked for editing; you will get an error only if
    something changed.

    Args:
      filename: The file to write.
      text: The content to write to the file.
    """
    if os.path.isfile(filename):
        with open(filename, "r") as f:
            current = f.read()
        if current == text:
            print("No change to %s" % filename)
            return

    with open(filename, "w") as f:
        f.write(text)
    print("Wrote %s" % filename)


def _AddHumanReadableDateComment(text_proto):
    return re.sub(
        r"(date_added: \d+)", r"\1  # " + time.strftime("%Y-%m-%d"), text_proto
    )


def main(args=None):
    args = parser.parse_args(args)
    is_new = True
    fontdir = args.directory
    old_metadata_file = os.path.join(fontdir, "METADATA.pb")
    if os.path.isfile(old_metadata_file):
        is_new = False

    language_comments = fonts.LanguageComments(LoadLanguages(base_dir=args.lang))
    metadata = _MakeMetadata(args, is_new)
    fonts.WriteMetadata(
        metadata, os.path.join(fontdir, "METADATA.pb"), comments=language_comments
    )

    desc = os.path.join(fontdir, "DESCRIPTION.en_us.html")
    articledir = os.path.join(fontdir, "article")
    article = os.path.join(articledir, "ARTICLE.en_us.html")
    if os.path.isfile(desc):
        print("DESCRIPTION.en_us.html exists")
    elif os.path.isfile(article):
        print("ARTICLE.en_us.html exists")
    else:
        os.makedirs(os.path.join(fontdir, "article"))
        desc_text = "N/A"
        if args.github_url:
            human_url = remove_url_prefix(args.github_url)
            desc_text += f'\n<p>To contribute, please see <a href="{args.github_url}">{human_url}</a>.</p>'
        _WriteTextFile(article, desc_text)


if __name__ == "__main__":
    main()
