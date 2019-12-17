#!/usr/bin/env python3
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
Automated build process for variable font onboarding to:
https://github.com/google/fonts


BASIC USE:

This script is used to build variable fonts from the command line of a
UNIX system (MacOS, GNU+Linux, Windows Subsystem for Linux (WSL)).

To start the build process, navigate to the root directory of a font repo
and run the following:

python3 $SOURCE/BUILD.py

For additional build features, the script can be run with flags, like so:

python3 $SOURCE/BUILD.py --googlefonts ~/Google/fonts/ofl/$FONTNAME --static


FLAGS:

--googlefonts ~/Google/fonts/ofl/foo    Sets upstream repo location

--drawbot                               Render the specimen with DrawBot

--ttfautohint "-args"                   Autohints fonts given args

--fontbakery                            Run QA tests on fonts in upstream

--static                                Output static fonts from VF source

--fixnonhinting                         Run if --ttfautohint is not used

--addfont                               Update font metadata
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
parser.add_argument(
    "--static", help="Build static fonts", action="store_true"
)
parser.add_argument(
    "--fixnonhinting", help="Fix nonhinting with gs tools", action="store_true"
)
parser.add_argument(
    "--addfont", help="Update metadata", action="store_true"
)
parser.add_argument(
    "--ufosrc", help="Build from ufo source and not glyphs", action="store_true"
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
    Print in yellow
    """
    print("\033[93m {}\033[00m".format(prt))


def intro():
    """
    Gives basic script info.
    """
    printG("#    # #####        #####    ################")
    printG("#    # #            #   #    #   ##         #")
    printG(" #  #  ####          #   #  #   # #   #######")
    printG(" #  #  #     <---->  #    ##    # #      #")
    printG("  ##   #              #        #  #   ####")
    printG("  ##   #              ##########  #####")
    print("\n**** Starting variable font build script:")
    print("     [+]", time.ctime())
    printG("    [!] Done")


def display_args():
    """
    Prints info about argparse flag use.
    """
    print("\n**** Settings:")

    print("     [+] --drawbot\t\t", end="")
    if args.drawbot == True:
        printG(args.drawbot)
    else:
        printR(args.drawbot)

    print("     [+] --googlefonts\t\t", end="")
    if args.googlefonts is not None:
        printG(args.googlefonts)
    else:
        printR(args.googlefonts)

    print("     [+] --ttfautohint\t\t", end="")
    if args.ttfautohint is not None:
        printG(args.ttfautohint)
    else:
        printR(args.ttfautohint)

    print("     [+] --fontbakery\t\t", end="")
    if args.fontbakery == True:
        printG(args.fontbakery)
    else:
        printR(args.fontbakery)

    print("     [+] --static\t\t", end="")
    if args.static == True:
        printG(args.static)
    else:
        printR(args.static)

    print("     [+] --fixnonhinting\t", end="")
    if args.fixnonhinting == True:
        printG(args.fixnonhinting)
    else:
        printR(args.fixnonhinting)

    print("     [+] --addfont\t\t", end="")
    if args.addfont == True:
        printG(args.addfont)
    else:
        printR(args.addfont)

    print("     [+] --ufosrc\t\t", end="")
    if args.ufosrc == True:
        printG(args.ufosrc)
    else:
        printR(args.ufosrc)

    printG("    [!] Done")
    time.sleep(8)


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
    time.sleep(2)


def get_source_list():
    """
    Gets a list of source files.
    """
    print("\n**** Making a list of Glyphsapp source files:")
    os.chdir("source")
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


def run_fontmake_variable():
    """
    Builds ttf variable font files with FontMake.
    """
    for source in sources:
        print("\n**** Building %s variable font files with FontMake:" % source)
        print("     [+] Run: fontmake ")
        if args.ufosrc == True:
            subprocess.call(
                "fontmake \
                          -g source/master_ufo/%s.designspace \
                          -o variable \
                          --output-path fonts/%s-VF.ttf"
                % (source, source),
                shell=True,
            )
        else:
            subprocess.call(
                "fontmake \
                          -g source/%s.glyphs \
                          -o variable \
                          --output-path fonts/%s-VF.ttf"
                % (source, source),
                shell=True,
            )
        print("     [!] Done")
    printG("    [!] Done")


def run_fontmake_static():
    """
    Builds ttf static font files with FontMake.
    """
    for source in sources:
        print("\n**** Building %s static font files with FontMake:" % source)
        print("     [+] Run: fontmake ")
        subprocess.call(
            "fontmake \
                      -g source/%s.glyphs \
                      -o ttf \
                      --keep-overlaps -i"
            % (source),
            shell=True,
        )
        print("     [!] Done")
    printG("    [!] Done")


def prep_static_fonts():
    """
    Move static fonts to the fonts/static directory.
    Run ttfautohint on all fonts and fix missing dsig
    """
    print("\n**** Moving static fonts:")
    for path in glob.glob("instance_ttf/*.ttf"):
        print(path)
        subprocess.call("cp %s fonts/static-fonts/" % path, shell=True)
    subprocess.call("rm -rf instance_ttf", shell=True)

    for static_font in glob.glob("fonts/static-fonts/*.ttf"):
        print(static_font)
        subprocess.call(
                "gftools fix-dsig %s --autofix"
                % static_font, shell=True
                )
        if args.fixnonhinting == True:
            print("FIXING NONHINTING")
            subprocess.call(
                    "gftools fix-nonhinting %s %s.fix"
                    % (static_font, static_font), shell=True
                    )
            subprocess.call(
                    "mv %s.fix %s"
                    % (static_font, static_font), shell=True
                    )
            subprocess.call(
                    "rm -rf %s.fix"
                    % static_font, shell=True
                    )
            subprocess.call(
                    "rm -rf fonts/static-fonts/*gasp.ttf", shell=True
                    )
            print("     [+] Done:", static_font)

        if args.ttfautohint == True:
            subprocess.call(
                "ttfautohint %s %s temp.ttf"
                % (args.ttfautohint, static_font),
                shell=True,
            )
            subprocess.call("cp temp.ttf %s" % static_font, shell=True)
            subprocess.call("rm -rf temp.ttf", shell=True)
    time.sleep(1)
    printG("    [!] Done")


def rm_build_dirs():
    """
    Cleanup build dirs
    """
    print("\n**** removing build directories")
    print("     [+] run: rm -rf variable_ttf master_ufo instance_ufo")
    subprocess.call(
            "rm -rf variable_ttf master_ufo instance_ufo", shell=True
            )
    printG("    [!] Done")
    time.sleep(1)


def fix_dsig():
    """
    Fixes DSIG table
    """
    print("\n**** Run: gftools: fix DSIG")
    for source in sources:
        subprocess.call(
            "gftools fix-dsig fonts/%s-VF.ttf --autofix"
            % source,
            shell=True,
        )
        print("     [+] Done:", source)
    printG("    [!] Done")
    time.sleep(1)


def fix_nonhinting():
    """
    Fixes non-hinting
    """
    print("\n**** Run: gftools: fix nonhinting")
    for path in glob.glob("fonts/*.ttf"):
        print(path)
        subprocess.call(
                "gftools fix-nonhinting %s %s.fix"
                % (path, path), shell=True
                )
        subprocess.call(
                "mv %s.fix %s"
                % (path, path), shell=True
                )
        subprocess.call(
                "rm -rf %s.fix"
                % path, shell=True
                )
        subprocess.call(
            "rm -rf fonts/*gasp.ttf", shell=True
            )
        print("     [+] Done:", path)
    printG("    [!] Done")
    time.sleep(1)


def ttfautohint():
    """
    Runs ttfautohint with flags set. For more info run: ttfautohint --help
    """
    print("\n**** Run: ttfautohint")
    os.chdir("fonts")
    cwd = os.getcwd()
    print("     [+] In Directory:", cwd)
    for source in sources:
        subprocess.call(
            "ttfautohint %s %s-VF.ttf %s-VF-Fix.ttf"
            % (args.ttfautohint, source, source),
            shell=True,
        )
        subprocess.call(
            "cp %s-VF-Fix.ttf %s-VF.ttf"
            % (source, source), shell=True
            )
        subprocess.call(
                "rm -rf %s-VF-Fix.ttf"
                % source, shell=True
        )
        print("     [+] Done:", source)
    os.chdir("..")
    cwd = os.getcwd()
    print("     [+] In Directory:", cwd)
    printG("    [!] Done")
    time.sleep(1)


def ttfautohint_static():
    """
    Runs ttfautohint with flags set. For more info run: ttfautohint --help
    """
    print("\n**** Run: ttfautohint")
    os.chdir("fonts")
    cwd = os.getcwd()
    print("     [+] In Directory:", cwd)
    for source in sources:
        subprocess.call(
            "ttfautohint %s %s-VF.ttf %s-VF-Fix.ttf"
            % (args.ttfautohint, source, source),
            shell=True,
        )
        subprocess.call(
                "cp %s-VF-Fix.ttf %s-VF.ttf"
                % (source, source), shell=True
                )
        subprocess.call(
                "rm -rf %s-VF-Fix.ttf"
                % source, shell=True
                )
        print("     [+] Done:", source)
    os.chdir("..")
    cwd = os.getcwd()
    print("     [+] In Directory:", cwd)
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
                "cp fonts/%s-VF.ttf %s/"
                % (source, args.googlefonts), shell=True
            )
            print("     [+] Done:", source)
    for path in glob.glob("fonts/static-fonts/*.ttf"):
        print(path)
        subprocess.call(
                "cp %s %s/static/"
                % (path, args.googlefonts), shell=True
        )
    else:
        pass
    printG("    [!] Done")
    time.sleep(1)


def add_font():
    """
    Build new metadata file for font if gf flag is used.
    """
    print("\n**** Making new metadata file for font.")
    if args.googlefonts is not None:
        subprocess.call(
                "gftools add-font %s"
                % args.googlefonts, shell=True
        )
        print("     [+] Done:")
    else:
        printR("    [!] Error: Use Google Fonts Flag (--googlefonts)")
    printG("    [!] Done")
    time.sleep(1)


def fontbakery():
    """
    Run FontBakery on the GoogleFonts repo.
    """
    print("\n**** Run: FontBakery:")
    for source in sources:
        subprocess.call(
            "fontbakery check-googlefonts %s/%s-VF.ttf \
            --ghmarkdown docs/FONTBAKERY-REPORT-%s.md"
            % (args.googlefonts, source, source), shell=True,
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
        "python3 docs/drawbot-sources/basic-specimen.py",
        shell=True,
    )
    printG("    [!] Done")
    time.sleep(1)


def main():
    """
    Executes font build sequence
    """
    intro()
    display_args()
    check_root_dir()
    get_source_list()
    get_style_list()
    run_fontmake_variable()
    # fix non-hinting
    if args.fixnonhinting == True:
        fix_nonhinting()
    else:
        pass
    # make static fonts
    if args.static == True:
        run_fontmake_static()
        prep_static_fonts()
    else:
        pass
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
    # AddFont
    if args.addfont == True:
        add_font()
    else:
        pass
    # FontBakery
    if args.fontbakery == True:
        fontbakery()
    else:
        pass
    # DrawBot
    if args.drawbot == True:
        render_specimens()
    else:
        pass

if __name__ == "__main__":
    main()
