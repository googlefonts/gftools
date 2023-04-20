#!/usr/bin/env python3
"""Tool to take files from a font family project upstream git repository
to the google/fonts GitHub repository structure, taking care of all the details.

Documentation at gftools/docs/gftools-packager/README.md
"""

import sys
from gftools import packager
from gftools.packager import upstream
from gftools.packager.exceptions import UserAbortError, ProgramAbortError
import argparse


def _ansi_bold(text: str) -> str:
    return f"\033[1m{text}\033[0m"


parser = argparse.ArgumentParser(
    prog="gftools packager",
    description="Package upstream font families for Google Fonts.",
    epilog=f'{_ansi_bold("Documentation:")} '
    "https://github.com/googlefonts/gftools/tree/main/docs/gftools-packager"
    "\n"
    f'{_ansi_bold("Issues:")} '
    "https://github.com/googlefonts/gftools/issues",
)

parser.add_argument(
    "--force",
    action="store_true",
    help="This allows the program to manipulate/change/delete data "
    "in [target]. Without this flag only adding new items "
    "is allowed.",
)

subparsers = parser.add_subparsers(
    dest="subcommand",
    title="subcommands",
    description="valid subcommands",
    help="additional help",
    required=True,
)

packager_parser = subparsers.add_parser(
    "package-git",
    help=(
        "Package a font family or families, updating a git clone of "
        "the google/fonts repository with the new family data. "
        "This is the most common use of the packager."
    ),
)

package_local_parser = subparsers.add_parser(
    "package-locally",
    help=(
        "Package a font family or families, saving the family data "
        "to a local directory. This is useful for creating an environment "
        "where the font can be tested with fontbakery as if it were ready "
        "to be added to google/fonts, and for testing the packager itself."
    ),
)

upstream_parser = subparsers.add_parser(
    "generate-upstream",
    help=(
        "Create and output the upstream.yaml to the file name given by target. "
        "This is intended to help bootstrapping new upstream configurations. "
        "In its simplest form, if no name argument is given, it will output the "
        "yaml template. "
        "However, if name is given, this will also try to include all available "
        "information. "
        "Use -f/--force to override existing file."
    ),
)

# Common arguments
for a_parser in [packager_parser, package_local_parser]:
    a_parser.add_argument(
        "--no-allowlist",
        action="store_true",
        help="Don't use the allowlist of allowed files to copy from "
        'TARGET in upstream-conf "files". This is meant to enable '
        "forward compatibility with new files and should not "
        "be used regularly. Instead file an issue to add new "
        "files to the allowlist.",
    )
    a_parser.add_argument(
        "file_or_families",
        metavar="name",
        type=str,
        nargs="*",
        help="The family name(s) or file name(s) of upstream conf yaml "
        'files to be packaged. If a name ends with the ".yaml" suffix, '
        "it's treated as a file otherwise it's used as family name "
        "and  packager tries to gather upstream configuration from "
        "the google/fonts GitHub repository. If no name is specified, "
        "no package will be created. This is useful to only make a "
        "PR from an already created branch, not adding a commit, "
        "use -b/--branch and see see -p/--pr.",
    )

# Local Packager

package_local_parser.add_argument(
    "--directory",
    metavar="DIR",
    type=str,
    required=True,
    help="Package the font to a local directory for testing purposes. "
    "See -f/--force to allow changing non-empty directories. ",
)

# Packager

packager_parser.add_argument(
    "--googlefonts-clone",
    type=str,
    dest="gf_git",
    required=True,
    help="Target a git repository clone of GitHub google/fonts and "
    "create or override a branch from upstream main using a generated "
    "default branch name or a branch name specified with -b/--branch",
)

packager_parser.add_argument(
    "-b",
    "--branch",
    type=str,
    default="",
    help="Set the local target branch name instead "
    'of using the generated branch name, like: "gftools_packager_{familyname}". ',
)
packager_parser.add_argument(
    "-a",
    "--add-commit",
    action="store_true",
    help="Don't override existing branch and instead add a new "
    "commit to the branch. Use this to create a PR for multiple "
    "familes e.g. a super family or a bunch update. "
    "It's likely that you want to combine this with -b/--branch.",
)
packager_parser.add_argument(
    "--pr",
    action="store_true",
    help="Make a pull request. "
    "This implies -g/--gf-git, i.e. target will be treated as if -g/--gf-git is set. "
    "See --pr-upstream  and --push-upstream.",
)
packager_parser.add_argument(
    "--pr-upstream",
    type=str,
    default="google/fonts",
    help="The upstream where the pull request goes, as a GitHub "
    '"owner/repoName" pair (default: google/fonts). ',
)
packager_parser.add_argument(
    "--push-upstream",
    type=str,
    default="",
    # we can push to a clone of google/fonts and then pr from
    # that clone to --pr-upstream, however, our ghactions QA can't
    # run on a different repo, that's why this is mostly for testing.
    help='The upstream where the push goes, as a GitHub "owner/repoName" '
    "pair (default: the value of --pr-upstream). ",
)

# Upstream generator

upstream_parser.add_argument(
    "--file",
    dest="target",
    metavar="YAML",
    default="upstream.yaml",
    type=str,
    help="The file to save the configuration to (defaults to upstream.yaml)",
)
upstream_parser.add_argument(
    "family",
    nargs="?",
    type=str,
    help="A family name; if given, data about this family is retrieved from Google Fonts",
)


def main(args=None):
    args = parser.parse_args(args)
    try:
        if args.subcommand == "generate-upstream":
            upstream.output_upstream_yaml(args)
        else:
            # "Encourage" user to create sensible argument combinations
            if args.subcommand == "package-git":
                if args.push_upstream and not args.pr:
                    parser.error("--push-upstream cannot be used without --pr")
            packager.make_package(args)

    except UserAbortError as e:
        print("Aborted", f"{e}")
        sys.exit(1)
    except ProgramAbortError as e:
        print(f"Aborted by program: {e}")
        sys.exit(1)
    print("Done!")


if __name__ == "__main__":
    main()
