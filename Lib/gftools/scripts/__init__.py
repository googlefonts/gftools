#!/usr/bin/env python3
# Copyright 2017 The Fontbakery Authors
# Copyright 2017 The Google Font Tools Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from __future__ import print_function
from argparse import RawTextHelpFormatter
from importlib import import_module
from pathlib import Path
from warnings import warn
import sys
import os
import argparse
import subprocess

from gftools._version import version as __version__


def _get_subcommands():
    subcommands = {}
    for module in Path(__file__).parent.glob("*.py"):
        module = module.stem
        if module == "__init__":
            continue
        friendly_name = module.replace("_", "-")
        subcommands[friendly_name] = (module, "gftools.scripts")

    # A special case
    subcommands["builder"] = ("__init__", "gftools.builder")

    return subcommands


def print_menu():
    print(" o-o              o     o--o")
    print("o                 |     |            o")
    print("| o-o o-o o-o o-o o o-o o-o o-o o-o -o- o-o")
    print("o   | | | | | | | | |-' |   | | | |  |   \\")
    print(" o-o  o-o o-o o-o o o-o o   o-o o o  o- o-o")
    print("                | Tools - Version", __version__)
    print("              o-o")
    print("\nBasic command examples:\n")
    print("    gftools compare-font font1.ttf font2.ttf")
    print("    gftools compare-font --help")
    print("    gftools --version")
    print("    gftools --help\n")


subcommands = _get_subcommands()

description = "Run gftools subcommands:{0}".format(
    "".join(["\n    {0}".format(sc) for sc in sorted(subcommands.keys())])
)

description += (
    "\n\nSubcommands have their own help messages.\n"
    "These are usually accessible with the -h/--help\n"
    "flag positioned after the subcommand.\n"
    "I.e.: gftools subcommand -h"
)

parser = argparse.ArgumentParser(
    description=description, formatter_class=RawTextHelpFormatter
)
parser.add_argument("subcommand", nargs=1, help="the subcommand to execute")

parser.add_argument(
    "--list-subcommands",
    action="store_true",
    help="print the list of subcommnds "
    "to stdout, separated by a space character. This is "
    "usually only used to generate the shell completion code.",
)

parser.add_argument(
    "--version", "-v", action="version", version="%(prog)s " + __version__
)


def main(args=None):
    if args is None:
        args = sys.argv
    if len(args) >= 2 and args[1] in subcommands:
        # relay
        (module, package) = subcommands[args[1]]
        mod = import_module(f".{module}", package)
        mod.main(args[2:])
    elif "--list-subcommands" in sys.argv:
        print(" ".join(list(sorted(subcommands.keys()))))
    else:
        # shows menu and help if no args
        print_menu()
        args = parser.parse_args()
        parser.print_help()


if __name__ == "__main__":
    main()
