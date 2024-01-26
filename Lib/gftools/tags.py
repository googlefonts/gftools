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
from functools import lru_cache


class SheetStructureChange(Exception):
    pass


class GFTags(object):
    SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQVM--FKzKTWL-8w0l5AE1e087uU_OaQNHR3_kkxxymoZV5XUnHzv9TJIdy7vcd0Saf4m8CMTMFqGcg/pub?gid=1193923458&single=true&output=csv"
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
        "Display": [
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
            "Brush/Marker",
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
            "Traditional/High contrast",
            "Contemporary/High contrast",
            "Low contrast",
        ],
        "Indic": [
            "Traditional/High contrast",
            "Contemporary/High contrast",
            "Low contrast",
            "Sign Painting/vernacular",
            "Reverse-contrast",
        ],
        "Simplicity": [
            "Calm/simple",
            "Competent",
            "Business",
            "Sincere",
            "Loud",
            "Awkward",
            "Innovative",
            "Artistic",
        ],
        "Youthful": [
            "Playful",
            "Excited",
            "Cute",
            "Happy",
            "Childlike",
            "Loud",
            "Rugged",
            "Vintage",
            "Stiff",
        ],
        "Flow": [
            "Rugged",
            "Futuristic",
            "Calm",
            "Childlike",
            "Active",
            "Cute",
            "Sophisticated",
            "Fancy",
            "Artistic",
        ],
    }

    def __init__(self):
        self.data = self._get_sheet_data()

    @lru_cache
    def _get_sheet_data(self):
        req = requests.get(self.SHEET_URL)
        return list(csv.reader(StringIO(req.text)))

    def _parse_csv(self):
        """Convert the tabular sheet data into
        [
            {"Family": str, "Group/Tag": str, "Weight": int},
            ...
        ]"""
        res = []
        # rows < 4 are column headers and padding
        for i in range(4, len(self.data)):
            # columns < 9 are personal quality scores, filepaths, imgs and padding
            for j in range(9, len(self.data[i])):
                if not self.data[i][j].isnumeric():
                    continue
                family = self.data[i][0]
                value = int(self.data[i][j])
                group = self.data[0][j]
                # If no tag exists for a value, it means a value has been assigned
                # to the whole group such as Sans, Sans Serif etc
                tag = self.data[1][j] or group
                res.append(
                    {
                        "Family": family,
                        "Group/Tag": f"/{group}/{tag}",
                        "Weight": value,
                    }
                )
        res.sort(key=lambda k: (k["Family"], k["Group/Tag"]))
        return res

    def to_csv(self, fp):
        """Export the Google Sheet into a csv format suitable for the
        google/fonts git repo."""
        munged_data = self._parse_csv()
        with open(fp, "w", encoding="utf-8") as out_doc:
            out_csv = csv.DictWriter(out_doc, ["Family", "Group/Tag", "Weight"])
            out_csv.writeheader()
            out_csv.writerows(munged_data)

    def check_structure(self):
        # Check Google Sheet columns haven't changed.
        # Personally, I wouldn't have used a Google Sheet since the data
        # isn't tabular. However, using a Google Sheet does mean we can all
        # edit the data collaboratively and it does mean users don't need to
        # know git or install other tools.
        # Please don't cry about all the empty columns below ;-). They're
        # mainly used as whitespace in the spreadsheet
        columns_0 = [
            "Family",
            "Family Dir",
            "Existing Category",
            "Sample Image",
            "",
            "Eli's Quality Score",
            "Eben's Quality Score",
            "UT's Quality Score",
            " Type \n Categories",
            "Serif",
            "Serif",
            "Serif",
            "Serif",
            "Serif",
            "Serif",
            "Serif",
            "Serif",
            "",
            "Sans",
            "Sans",
            "Sans",
            "Sans",
            "Sans",
            "Sans",
            "Sans",
            "Sans",
            "",
            "Slab",
            "Slab",
            "Slab",
            "Slab",
            "",
            "Script",
            "Script",
            "Script",
            "Script",
            "Script",
            "",
            "Display",
            "Display",
            "Display",
            "Display",
            "Display",
            "Display",
            "Display",
            "Display",
            "Display",
            "Display",
            "Display",
            "Display",
            "Display",
            "Display",
            "Display",
            "",
            "Arabic",
            "Arabic",
            "Arabic",
            "Arabic",
            "Arabic",
            "Arabic",
            "Arabic",
            "Arabic",
            "Arabic",
            "Arabic",
            "Arabic",
            "",
            "Hebrew",
            "Hebrew",
            "Hebrew",
            "Hebrew",
            "Hebrew",
            "",
            "South East Asian (Thai, Khmer, Lao)",
            "South East Asian (Thai, Khmer, Lao)",
            "South East Asian (Thai, Khmer, Lao)",
            "South East Asian (Thai, Khmer, Lao)",
            "South East Asian (Thai, Khmer, Lao)",
            "",
            "Sinhala",
            "Sinhala",
            "Sinhala",
            "Sinhala",
            "",
            "Indic",
            "Indic",
            "Indic",
            "Indic",
            "Indic",
            "Indic",
            " Expressive\n Categories",
            "Simplicity",
            "Simplicity",
            "Simplicity",
            "Simplicity",
            "Simplicity",
            "Simplicity",
            "Simplicity",
            "Simplicity",
            "Youthful",
            "Youthful",
            "Youthful",
            "Youthful",
            "Youthful",
            "Youthful",
            "Youthful",
            "Youthful",
            "Youthful",
            "Flow",
            "Flow",
            "Flow",
            "Flow",
            "Flow",
            "Flow",
            "Flow",
            "Flow",
            "Flow",
        ]
        columns_1 = [
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "Humanist Venetian",
            "Old Style Garalde",
            "Transitional",
            "Modern",
            "Scotch",
            "Didone",
            "Fat Face",
            "",
            "",
            "Humanist",
            "Grotesque",
            "Neo Grotesque",
            "Geometric",
            "Rounded",
            "Superelipse",
            "Glyphic",
            "",
            "",
            "Geometric",
            "Humanist",
            "Clarendon",
            "",
            "",
            "Formal",
            "Informal",
            "Handwritten",
            "Upright Script",
            "",
            "",
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
            "Brush/Marker",
            "",
            "",
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
            "",
            "",
            "Normal",
            "Ashurit",
            "Cursive",
            "Rashi",
            "",
            "",
            "Looped",
            "Loopless",
            "Moul (Khmer)",
            "Chrieng (Khmer)",
            "",
            "",
            "Traditional/High contrast",
            "Contemporary/High contrast",
            "Low contrast",
            "",
            "",
            "Traditional/High contrast",
            "Contemporary/High contrast",
            "Low contrast",
            "Sign Painting/vernacular",
            "Reverse-contrast",
            "",
            "Calm/simple",
            "Competent",
            "Business",
            "Sincere",
            "Loud",
            "Awkward",
            "Innovative",
            "Artistic",
            "Playful",
            "Excited",
            "Cute",
            "Happy",
            "Childlike",
            "Loud",
            "Rugged",
            "Vintage",
            "Stiff",
            "Rugged",
            "Futuristic",
            "Calm",
            "Childlike",
            "Active",
            "Cute",
            "Sophisticated",
            "Fancy",
            "Artistic",
        ]
        if self.data[0] != columns_0:
            raise SheetStructureChange(
                "Sheet's first row of columns has changed. If intentional, "
                "please update columns_0 variable."
            )
        if self.data[1] != columns_1:
            raise SheetStructureChange(
                "Sheet's second row of columns have changed. If intentional, "
                "please update columns_1 variable."
            )

        # Check a few families
        munged_data = self._parse_csv()
        test_tags = [
            # row 0
            {"Family": "ABeeZee", "Group/Tag": "/Sans/Geometric", "Weight": 10},
            # row 131
            {"Family": "Akaya Kanadaka", "Group/Tag": "/Serif/Serif", "Weight": 10},
            # row 330
            {"Family": "Bonbon", "Group/Tag": "/Script/Handwritten", "Weight": 100},
            # row 577
            {
                "Family": "Cormorant SC",
                "Group/Tag": "/Serif/Old Style Garalde",
                "Weight": 100,
            },
            # row 900
            {"Family": "Gochi Hand", "Group/Tag": "/Script/Informal", "Weight": 100},
            # row 1354
            {
                "Family": "Zilla Slab Highlight",
                "Group/Tag": "/Slab/Geometric",
                "Weight": 20,
            },
        ]
        for tag in test_tags:
            if tag not in munged_data:
                raise ValueError(f"{tag} should exist spreadsheet")
        print("Google Sheet's structure is intact")
