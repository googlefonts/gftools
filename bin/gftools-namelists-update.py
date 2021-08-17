#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2021, Google Inc.
# Author: Adam Twardoch (adam+github@twardoch.com)
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import sys
import json
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.unicode import Unicode
from datetime import datetime
import gftools
from gftools.util import google_fonts as gf
nam_folder = str(Path(Path(gftools.__file__).parent, 'encodings'))
gf.FLAGS['nam_dir'].parse(nam_folder)
today = datetime.today().strftime('%Y-%m-%d')

class NamList(object):
    def __init__(self):
        self.unicodes = set()
        self.namlist = {
            'fileName': None,
            'ownCharset': set(),
            'header': {
                'lines': [],
                'includes': set()
            },
            'ownNoCharcode': set(),
            'includes': None,
            'charset': None,
            'noCharcode': None
        }

    def add_from_font(self, font_path):
        font = TTFont(font_path)
        for cmap in font["cmap"].tables:
            if not cmap.isUnicode():
                continue
            self.namlist['ownCharset'].update(cp for cp, name in cmap.cmap.items())
        font.close()

    def _format_codepoint(self, codepoint):
        if 0xE000 <= codepoint <= 0xF8FF:
            item_description = 'PRIVATE USE AREA U+{0:04X}'.format(codepoint)
            char = ' '
        elif codepoint == 0x000D:
            # Special case, this only happens in Latin-core.
            # FIXME: we should consider remover CR from Latin-core
            item_description = 'CR'
            char = ' '
        elif codepoint == 0x0000:
            item_description = ''
            char = ''
        else:
            item_description = Unicode[codepoint]
            char = chr(codepoint)
        return ('0x{0:04X}'.format(codepoint), char, item_description)

    def add_from_nam(self, nam_path):
        if Path(nam_path).exists():
            namlist = gf.ReadNameList(nam_path, unique_glyphs=True)
            self.namlist = {**self.namlist, **namlist}

    def update_header(self, text):
        self.namlist['header']['lines'] = [f"# {text}\n"] + self.namlist['header']['lines']

    def format_namlist(self, out=sys.stdout):
        for line in self.namlist['header']['lines']:
            print(line.strip(), file=out)
        charcodes = sorted(self.namlist['ownCharset'])
        excluded_chars = []
        for charcode in charcodes:
            hexchar, char, item_description = self._format_codepoint(charcode)
            if item_description not in excluded_chars:
                string = "{} {} {}".format(hexchar, char, item_description)
                print(string, file=out)

    def save_namlist(self, nam_path):
        with open(nam_path, 'w', encoding='utf-8') as f:
            self.format_namlist(f)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        json_path = sys.argv[1]
        with open(json_path, 'r', encoding='utf-8') as f:
            update_nam_records = json.load(f)
    else:
        update_nam_records = {}
        for nam_path in Path(nam_folder).glob('*_unique-glyphs.nam'):
            update_nam_records[str(nam_path)] = []
    for nam_path, font_paths in update_nam_records.items():
        nl = NamList()
        nl.add_from_nam(nam_path)
        print(f"Updating {Path(nam_path).name}")
        if len(font_paths):
            font_bases = ", ".join([Path(p).stem for p in font_paths])
            upd_message = f"Updated from {font_bases}"
        else:
            upd_message = "Reformatted"
        for font_path in font_paths:
            print(f"  from {Path(font_path).name}")
            nl.add_from_font(font_path)
        nl.update_header(f"{today} {upd_message} by Adam Twardoch")
        nl.save_namlist(nam_path)
