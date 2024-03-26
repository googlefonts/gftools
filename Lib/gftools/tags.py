"""
tags.py

This module contains objects to work with the "Google Fonts 2023
Typographic Categories" Google Sheet,
https://docs.google.com/spreadsheets/d/1Nc5DUsgVLbJ3P58Ttyhr5r-KYVnJgrj47VvUm1Rs8Fw/edit#gid=0

This sheet contains all the font tagging information which is used in
the Google Fonts website to help users find font families.
"""

import csv
import requests
from io import StringIO
from difflib import Differ


class SheetStructureChange(Exception):
    pass


class GFTags(object):
    # Original sheet tagging data created by Universal Thirst for the whole GF collection
    SHEET1_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQVM--FKzKTWL-8w0l5AE1e087uU_OaQNHR3_kkxxymoZV5XUnHzv9TJIdy7vcd0Saf4m8CMTMFqGcg/pub?gid=1193923458&single=true&output=csv"
    # Submissions from designers via form https://forms.gle/jcp3nDv63LaV1rxH6
    SHEET2_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQVM--FKzKTWL-8w0l5AE1e087uU_OaQNHR3_kkxxymoZV5XUnHzv9TJIdy7vcd0Saf4m8CMTMFqGcg/pub?gid=378442772&single=true&output=csv"
    CATEGORIES = {
        "Serif": [
            "Humanist Venetian",
            "Old Style Garalde",
            "Transitional",
            "Modern",
            "Scotch",
            "Didone",
            "Fat Face",
        ],
        "Sans": [
            "Humanist",
            "Grotesque",
            "Neo Grotesque",
            "Geometric",
            "Rounded",
            "Superelipse",
            "Glyphic",
        ],
        "Slab": ["Geometric", "Humanist", "Clarendon"],
        "Script": ["Formal", "Informal", "Handwritten", "Upright Script"],
        "Theme": [
            "Blackletter",
            "Wacky",
            "Blobby",
            "Woodtype",
            "Stencil",
            "Inline",
            "Distressed",
            "Shaded",
            "Techno",
            "Art Nouveau",
            "Tuscan",
            "Art Deco",
            "Medieval",
            "Brush",
            "Pixel",
            "Brush",
        ],
        "Arabic": [
            "Kufi",
            "Naskh",
            "Nastaliq",
            "Maghribi",
            "Ruqah",
            "Diwani",
            "Bihari",
            "Warsh",
            "Sudani",
            "West African",
        ],
        "Hebrew": ["Normal", "Ashurit", "Cursive", "Rashi"],
        "South East Asian (Thai, Khmer, Lao)": [
            "Looped",
            "Loopless",
            "Moul (Khmer)",
            "Chrieng (Khmer)",
        ],
        "Sinhala": [
            "Traditional",
            "Contemporary",
            "Low contrast",
        ],
        "Indic": [
            "Traditional",
            "Contemporary",
            "Low contrast",
            "Sign Painting",
            "Reverse-contrast",
        ],
        "Expressive": [
            "Competent",
            "Business",
            "Sincere",
            "Loud",
            "Awkward",
            "Innovative",
            "Playful",
            "Excited",
            "Happy",
            "Loud",
            "Rugged",
            "Vintage",
            "Stiff",
            "Futuristic",
            "Calm",
            "Childlike",
            "Active",
            "Cute",
            "Sophisticated",
            "Fancy",
            "Artistic",
        ],
        "Not text": [
            "Experimental",
            "Emojis",
            "Symbols",
        ],
        "Expressive": [
            "Business",
            "Sincere",
            "Loud",
            "Vintage",
            "Calm",
            "Calm/simple",
            "Stiff",
            "Competent",
            "Happy",
            "Childlike",
            "Excited",
            "Playful",
            "Awkward",
            "Innovative",
            "Rugged",
            "Futuristic",
            "Artistic",
            "Cute",
            "Fancy",
            "Sophisticated",
            "Active",
        ],
    }

    def __init__(self):
        self.sheet1_data = self._get_sheet_data(self.SHEET1_URL)
        self.sheet2_data = self._get_sheet_data(self.SHEET2_URL)
        self.seen_families = set()
        self.duplicate_families = set()
        self.data = self._parse_sheets_csv()

    def _get_sheet_data(self, sheet_url):
        req = requests.get(sheet_url)
        return list(csv.reader(StringIO(req.text)))

    def _parse_csv(self, data, skip_rows=[], skip_columns=[], family_name_col=0):
        """Convert the tabular sheet data into
        [
            {"Family": str, "Group/Tag": str, "Weight": int},
            ...
        ]"""
        res = []
        for i in range(len(data)):
            if i in skip_rows:
                continue
            family = data[i][family_name_col]
            if family in self.seen_families:
                self.duplicate_families.add(family)
                continue
            self.seen_families.add(family)
            for j in range(len(data[i])):
                if j in skip_columns:
                    continue
                if not data[i][j].isnumeric():
                    continue
                value = int(data[i][j])
                if value == 0:
                    continue
                category = data[0][j]
                # If no tag exists for a value, it means a value has been assigned
                # to the whole group such as Sans, Sans Serif etc. We don't want to
                # include these since we can deduce it ourselves according to Evan.
                sub_category = data[1][j].split("\n")[0]
                if sub_category == "":
                    continue
                if category not in self.CATEGORIES:
                    raise ValueError(
                        f"'{category}' not in known categories, '{self.CATEGORIES.keys()}'"
                    )
                if sub_category not in self.CATEGORIES[category]:
                    raise ValueError(
                        f"'{sub_category}' not in known sub categories, '{self.CATEGORIES[category]}'"
                    )
                res.append(
                    {
                        "Family": family,
                        "Group/Tag": f"/{category}/{sub_category}",
                        "Weight": value,
                    }
                )
        if self.duplicate_families:
            raise ValueError(
                f"Duplicate families found in sheet: {self.duplicate_families}. Please remove them."
            )
        res.sort(key=lambda k: (k["Family"], k["Group/Tag"]))
        return res

    def _parse_sheets_csv(self):
        sheet1 = self._parse_csv(
            self.sheet1_data,
            skip_rows=[0, 1, 2, 3],
            skip_columns=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        )
        sheet2 = self._parse_csv(
            self.sheet2_data,
            skip_rows=[0, 1],
            skip_columns=[0, 1, 2, 3, 4, 5, 6],
            family_name_col=2,
        )
        return sheet1 + sheet2

    def to_csv(self, fp):
        """Export the Google Sheet into a csv format suitable for the
        google/fonts git repo."""
        with open(fp, "w", encoding="utf-8") as out_doc:
            out_csv = csv.DictWriter(out_doc, ["Family", "Group/Tag", "Weight"])
            out_csv.writeheader()
            out_csv.writerows(self.data)

    def has_family(self, name):
        return any([i["Family"] == name for i in self.data])

    def check_structure(self):
        # Check a few families to determine whether the spreadsheet is broken
        test_tags = [
            # sheet1 row 0
            {"Family": "ABeeZee", "Group/Tag": "/Sans/Geometric", "Weight": 10},
            # sheet1 row 330
            {"Family": "Bonbon", "Group/Tag": "/Script/Handwritten", "Weight": 100},
            # sheet1 row 577
            {
                "Family": "Cormorant SC",
                "Group/Tag": "/Serif/Old Style Garalde",
                "Weight": 100,
            },
            # sheet1 row 900
            {"Family": "Gochi Hand", "Group/Tag": "/Script/Informal", "Weight": 100},
            # sheet1 row 1354
            {
                "Family": "Zilla Slab Highlight",
                "Group/Tag": "/Slab/Geometric",
                "Weight": 20,
            },
            # sheet2 row 1
            {
                "Family": "Noto Serif Hentaigana",
                "Group/Tag": "/Script/Formal",
                "Weight": 20,
            },
            # sheet2 row 2
            {
                "Family": "Platypi",
                "Group/Tag": "/Serif/Humanist Venetian",
                "Weight": 20,
            },
            {"Family": "Platypi", "Group/Tag": "/Theme/Art Nouveau", "Weight": 5},
            {"Family": "Sedan", "Group/Tag": "/Serif/Old Style Garalde", "Weight": 90},
        ]
        for tag in test_tags:
            if tag not in self.data:
                raise ValueError(f"{tag} should exist spreadsheet")
        print("Google Sheet's structure is intact")
