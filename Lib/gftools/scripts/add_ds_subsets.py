import os
import re
import sys
from textwrap import dedent, wrap

from strictyaml import load

from gftools.subsetmerger import SUBSET_SOURCES, SubsetMerger, subsets_schema


def rewrap(text):
    paras = text.split("\n\n")
    return "\n\n".join("\n".join(wrap(dedent(para), width=72)) for para in paras)


EXAMPLES = """

gftools-add-ds-subsets \\
    --repo notofonts/latin-greek-cyrillic \\
    --file sources/NotoSans-Italic.glyphspackage \\
    --name "GF_Latin_Core" \\
    -o full/NotoSansElymaic.designspace NotoSansElymaic.designspace

gftools-add-ds-subsets \\
    --yaml subsets.yaml \\
    -o full/NotoSansCypriot.designspace NotoSansCypriot.designspace

Where subsets.yaml is:

- from: Noto Sans
  name: GF_Latin_Core
- from: Noto Sans Linear B
  ranges:
    - start: 0x10100
      end: 0x10133
"""


def main(args=None):
    import argparse

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=rewrap(
            f"""
Add a subset from another font to a designspace file and save.

If --yaml is given, it should be a YAML file describing the subsets to add.
Otherwise, --repo and --file must be given to specify the source repository
(as username/repo pair from from GitHub) and file name within the repository,
and then either --name (to use a named subset from the GF glyphsets) or
--codepoints (to specify a range of codepoints to subset, in the form
<start>-<end>,<start>-<end>,... where `start` and `end` are Unicode hex
codepoints) must be given.

The YAML file should be a list of subsets, each of which should have a `from`
key to specify the donor font, and either a `name` key (to use a named
subset from the GF glyphsets) or a `ranges` key (to specify a range of
codepoints to subset). The `from` key can either be a string (one of
{", ".join([f'"{k}"' for k in SUBSET_SOURCES.keys()])} or a dictionary
with a `repo` key specifying the GitHub repository (as username/repo pair)
and a `path` key specifying the file within the repository.

Example usage:
"""
        )
        + EXAMPLES,
    )
    parser.add_argument(
        "--googlefonts",
        help="Restrict donor instances to Google Fonts styles",
        action="store_true",
    )

    parser.add_argument("--yaml", "-y", help="YAML file describing subsets")

    parser.add_argument(
        "--repo",
        "-r",
        help="GitHub repository slug to use for subsetting. Use @ after slug to specify branch/tag/commit, e.g. org/repo@v0.1.0; 'latest' is supported for latest release",
    )
    parser.add_argument("--file", "-f", help="Source file within GitHub repository")
    parser.add_argument("--name", "-n", help="Name of subset to use from glyphset")
    parser.add_argument(
        "--allow-sparse",
        help="Allow skipping a non-default master missing from the donor designspace",
        action="store_true",
    )
    parser.add_argument("--codepoints", "-c", help="Range of codepoints to subset")
    parser.add_argument(
        "--json", "-j", action="store_true", help="Use JSON structured UFOs"
    )
    parser.add_argument(
        "--exclude-codepoints", help="Space-delimited unicodes to exclude"
    )
    parser.add_argument(
        "--exclude-codepoints-file",
        help="Newline delimited file with unicodes to exclude. "
        "Allows for comments with either # or //",
    )
    parser.add_argument(
        "--exclude-glyphs", help="Space-delimited glyph names to exclude"
    )
    parser.add_argument(
        "--exclude-glyphs-file",
        help="Newline delimited file with glyph names to exclude. "
        "Allows for comments with either # or //",
    )

    parser.add_argument("--output", "-o", help="Output designspace file")

    parser.add_argument("input", help="Input designspace file")
    args = parser.parse_args(args)

    if os.path.dirname(args.output) == os.path.dirname(args.input):
        print("Output file must be in a different directory from input file")
        sys.exit(1)

    if args.yaml:
        subsets = load(open(args.yaml).read(), subsets_schema).data
    else:
        # It's a one-shot operation, check repo/file/name/codepoints are all given
        if not args.repo or not args.file:
            print("Must specify --repo and --file")
            sys.exit(1)
        if not args.name and not args.codepoints:
            print("Must specify --name or --codepoints")
            sys.exit(1)
        # And then construct the YAML-like object ourselves
        # See subsets_schema in ..subsetmerger
        subsets = [
            {
                "from": {
                    "repo": args.repo,
                    "path": args.file,
                    "exclude_codepoints": args.exclude_codepoints,
                    "exclude_codepoints_file": args.exclude_codepoints_file,
                    "exclude_glyphs": args.exclude_glyphs,
                    "exclude_glyphs_file": args.exclude_glyphs_file,
                }
            }
        ]
        if args.name:
            subsets[0]["name"] = args.name
        else:
            subsets[0]["ranges"] = []
            for range in re.split(r"[\w,]+", args.codepoints):
                if not range:
                    continue
                start, end = range.split("-")
                subsets[0]["ranges"].append(
                    {
                        "start": int(start, 16),
                        "end": int(end, 16),
                    }
                )
    SubsetMerger(
        args.input,
        args.output,
        subsets,
        googlefonts=args.googlefonts,
        json=args.json,
        allow_sparse=args.allow_sparse,
    ).add_subsets()


if __name__ == "__main__":
    main()
