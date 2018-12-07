#!/usr/bin/env python
# coding: utf-8
# Copyright 2018 The Font Bakery Authors.
# Copyright 2018 The Google Font Tools Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# See AUTHORS.txt for the list of Authors and LICENSE.txt for the License.
"""
Builds variable fonts using flags for input.

NOTE: Not ready for UFOS.

This is the python variable font build script I have been using, but all the settings have been moved to args so it's easier to maintain. 

For example, I'm using the following command to build Orbitron, run from the font repo root directory:

    gftools build-vf --googlefonts \
      ~/Google/fonts/ofl/orbitron \
      --fontbakery \
      --drawbot \
      --ttfautohint "-I -W --increase-x-height=0 --stem-width-mode=sss --default-script=latn";

This will do the following:

1. Build the font with fontmake
2. Run ttfautohint with the given given args
3. Copy new fonts to the Google fonts directory
4. Generate new DrawBot specimens
5. Run FontBakery in the GoogleFonts directory
6. Add a new FontBakery report to the docs directory   

A video demo of how this works is here:

https://www.youtube.com/watch?v=l59jWpiR3xs
"""
import argparse
import glob
import os
import subprocess
import time
from fontTools.ttLib import TTFont


# Initialize flag parser
parser = argparse.ArgumentParser()
parser.add_argument(
    "--drawbot", help="Render a specimen with DrawBot", action="store_true"
)
parser.add_argument(
    "--fontbakery", help="Test fonts with fontbakery", action="store_true"
)
parser.add_argument(
    "--googlefonts", help="Store GoogleFonts directory name"
)
parser.add_argument(
    "--ttfautohint", help="Store ttfautohint flags"
)
args = parser.parse_args()


# Initialize empty lists
sources = []
sources_styles = []


def printR(prt):
    """
    Print in red
    """
    print("\033[91m {}\033[00m".format(prt))


def printG(prt):
    """
    Print in green
    """
    print("\033[92m {}\033[00m".format(prt))


def printY(prt):
    """
    Print in red
    """
    print("\033[93m {}\033[00m".format(prt))


def intro():
    """ 
    Gives basic script info.
    """
    printG("#    # #####                    #####    ################")
    time.sleep(0.1)
    printG("#    # #                        #   #    #   ##         #")
    time.sleep(0.1)
    printG(" #  #  ####                      #   #  #   # #   #######")
    time.sleep(0.1)
    printG(" #  #  #     <---------------->  #    ##    # #      #")
    time.sleep(0.1)
    printG("  ##   #                          #        #  #   ####")
    time.sleep(0.1)
    printG("  ##   #                          ##########  #####")
    time.sleep(0.1)
    print("\n**** Starting variable font build script:")
    print("     [+]", time.ctime())
    printG("    [!] Done")
    time.sleep(0.1)


def display_args():
    """
    Gives info about the flags.
    """
    print("\n**** Settings:")
    time.sleep(0.1)
    print("     [+] --drawbot\t", args.drawbot)
    time.sleep(0.1)
    print("     [+] --googlefonts\t", args.googlefonts)
    time.sleep(0.1)
    print("     [+] --ttfautohint\t", args.ttfautohint)
    time.sleep(0.1)
    print("     [+] --fontbakery\t", args.fontbakery)
    time.sleep(0.1)
    printG("    [!] Done")


def check_root_dir():
    """
    Checks to make sure script is run from a git repo root directory.
    """
    print("\n**** Looking for the font repo root directory:")
    REPO_ROOT = [".gitignore", ".git"]
    repo_test = os.listdir(path=".")
    repo_test_result = all(elem in repo_test for elem in REPO_ROOT)
    if repo_test_result:
        print("     [+] OK: Looks good")
        printG("    [!] Done")
    else:
        printR("     [!] ERROR: Run script from the root directory")
    time.sleep(1)


def get_source_list():
    """
    Gets a list of source files.
    """
    print("\n**** Making a list of Glyphsapp source files:")
    os.chdir("sources")
    for name in glob.glob("*.glyphs"):
        sources.append(os.path.splitext(name)[0])
    os.chdir("..")
    print("     [+] SOURCES: List of sources =", sources)
    time.sleep(1)
    printG("    [!] Done")


def get_style_list():
    """
    Gets a list of styles from the source list.
    """
    print("\n**** Starting build process:")
    for source in sources:
        time.sleep(0.5)
        print("     [+] SOURCES: Preparing to build", source)
        print("     [+] SOURCES: Style =", source.rpartition("-")[2])
        sources_style = str(source.rpartition("-")[2])
        sources_styles.append(sources_style)
    print("     [+] SOURCES: Styles =", sources_styles)
    time.sleep(1)
    printG("    [!] Done")


def run_fontmake():
    """
    Builds ttf fonts files with font make.
    """
    for source in sources:
        print("\n**** Building %s font files with Fontmake:" % source)
        print("     [+] Run: fontmake ")
        subprocess.call(
            "fontmake \
                      -g sources/%s.glyphs \
                      -o variable \
                      --output-path fonts/%s-VF.ttf \
            > /dev/null 2>&1"
            % (source, source),
            shell=True,
        )
        print("     [!] Done")
    printG("    [!] Done")


def rm_build_dirs():
    """
    Cleanup build dirs
    """
    print("\n**** Removing build directories")
    print("     [+] Run: rm -rf variable_ttf master_ufo instance_ufo")
    subprocess.call("rm -rf variable_ttf master_ufo instance_ufo", shell=True)
    printG("    [!] Done")
    time.sleep(1)


def ttfautohint():
    """
    Runs ttfautohint with various flags set. For more info run: ttfautohint --help
    """
    print("\n**** Run: ttfautohint")
    os.chdir("fonts")
    cwd = os.getcwd()
    print("     [+] In Directory:", cwd)
    for source in sources:
        subprocess.call(
            "ttfautohint \
                         %s \
                         %s-VF.ttf %s-VF-Fix.ttf"
            % (args.ttfautohint, source, source),
            shell=True,
        )
        subprocess.call("cp %s-VF-Fix.ttf %s-VF.ttf" % (source, source), shell=True)
        subprocess.call("rm -rf %s-VF-Fix.ttf" % source, shell=True)
        os.chdir("..")
        cwd = os.getcwd()
        print("     [+] In Directory:", cwd)
        print("     [+] Done:", source)
    printG("    [!] Done")
    time.sleep(1)


def fix_dsig():
    """
    Fixes DSIG table
    """
    print("\n**** Run: gftools")
    for source in sources:
        subprocess.call(
            "gftools \
                     fix-dsig fonts/%s-VF.ttf --autofix \
                     > /dev/null 2>&1"
            % source,
            shell=True,
        )
        print("     [+] Done:", source)
    printG("    [!] Done")
    time.sleep(1)


def google_fonts():
    """
    Copy font output to the GoogleFonts repo.
    """
    print("\n**** Copying font output to the GoogleFonts repo.")
    if args.googlefonts is not None:
        for source in sources:
            subprocess.call(
                "cp fonts/%s-VF.ttf %s/" % (source, args.googlefonts), shell=True
            )
            print("     [+] Done:", source)
    else:
        pass
    printG("    [!] Done")
    time.sleep(1)


def fontbakery():
    """
    Run FontBakery on the GoogleFonts repo.
    """
    print("\n**** Run: FontBakery:")
    for source in sources:
        subprocess.call(
            "fontbakery \
                        check-googlefonts %s/%s-VF.ttf \
                        --ghmarkdown docs/FONTBAKERY-REPORT-%s.md "
            % (args.googlefonts, source, source),
            shell=True,
        )
        print("     [+] Done:", source)
    printG("    [!] Done")
    time.sleep(1)


def render_specimens():
    """
    Render specimens
    """
    print("\n**** Run: DrawBot")
    subprocess.call(
        "python3 docs/drawbot-sources/basic-specimen.py \
        > /dev/null 2>&1",
        shell=True,
    )
    printG("    [!] Done")
    time.sleep(1)


def main():
    """
    Executes variable font build sequence
    """
    intro()
    display_args()
    check_root_dir()
    get_source_list()
    get_style_list()
    run_fontmake()
    rm_build_dirs()
    fix_dsig()
    # ttfautohint
    if args.ttfautohint is not None:
        ttfautohint()
    else:
        pass
    # GoogleFonts
    if args.googlefonts is not None:
        google_fonts()
    else:
        pass
    # FontBakery
    if args.fontbakery == True:
        fontbakery()
    else:
        pass
    # Drawbot
    if args.drawbot == True:
        render_specimens()
    else:
        pass


if __name__ == "__main__":
    main()
