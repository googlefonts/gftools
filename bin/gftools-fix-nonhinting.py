#!/usr/bin/env python3
# Copyright 2017 The Font Bakery Authors.
# Copyright 2017 The Google Font Tools Authors
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
#
# The magic is in two places:
#
# 1. The GASP table. Vern Adams <vern@newtypography.co.uk>
#    suggests it should have value 15 for all sizes.
#
# 2. The PREP table. Raph Levien <firstname.lastname@gmail.com>
#    suggests using his code to turn on 'drop out control'
#    Learn more:
#    https://developer.apple.com/fonts/TrueType-Reference-Manual/RM05/Chap5.html#SCANCTRL
#    https://developer.apple.com/fonts/TrueType-Reference-Manual/RM05/Chap5.html#SCANTYPE
#
# PUSHW_1
#  511
# SCANCTRL
# PUSHB_1
#  4
# SCANTYPE
#
# This script depends on fontTools Python library, available
# in most packaging systems and sf.net/projects/fonttools/
#
# Usage:
#
# $ gftools fix-nonhinting FontIn.ttf FontOut.ttf

# Import our system library and fontTools ttLib
"""
Fixes TTF GASP table so that its program
contains the minimal recommended instructions.
"""
from __future__ import print_function
from argparse import (ArgumentParser,
                      RawTextHelpFormatter)
import os
from fontTools import ttLib
from fontTools.ttLib.tables import ttProgram
from gftools.fix import fix_unhinted_font


parser = ArgumentParser(description=__doc__,
                        formatter_class=RawTextHelpFormatter)
parser.add_argument('fontfile_in',
                     nargs=1,
                    help="Font in OpenType (TTF/OTF) format")
parser.add_argument('fontfile_out',
                    nargs=1,
                    help="Filename for the output")

def main():
  args = parser.parse_args()

  # Open the font file supplied as the first argument on the command line
  fontfile_in = os.path.abspath(args.fontfile_in[0])
  font = ttLib.TTFont(fontfile_in)

  # Save a backup
  backupfont = '{}-backup-fonttools-prep-gasp{}'.format(fontfile_in[0:-4],
                                                        fontfile_in[-4:])
  # print "Saving to ", backupfont
  font.save(backupfont)
  print(backupfont, " saved.")

  # Print the Gasp table
  if "gasp" in font:
      print("GASP was: ", font["gasp"].gaspRange)
  else:
      print("GASP wasn't there")

  # Print the PREP table
  if "prep" in font:
    old_program = ttProgram.Program.getAssembly(font["prep"].program)
    print("PREP was:\n\t" + "\n\t".join(old_program))
  else:
    print("PREP wasn't there")

  fix_unhinted_font(font)
  # Print the Gasp table
  print("GASP now: ", font["gasp"].gaspRange)

  # Print the PREP table
  current_program = ttProgram.Program.getAssembly(font["prep"].program)
  print("PREP now:\n\t" + "\n\t".join(current_program))

  # Save the new file with the name of the input file
  fontfile_out = os.path.abspath(args.fontfile_out[0])
  font.save(fontfile_out)
  print(fontfile_out, " saved.")

if __name__ == "__main__":
  main()

