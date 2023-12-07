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


class SheetStructureChange(Exception): pass


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
            "Artistic"
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
            "Stiff"
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
            "Artistic"
        ]
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
        columns = []
        res = []
        for row_idx, row in enumerate(self.data):
            if row_idx == 1:
                columns = row
            # Some rows have been used as padding so skip them.
            if row_idx < 4:
                continue
            for col_idx, cell in enumerate(row):
                # Doc also contains columns used for padding... meh!
                if cell == "" or columns[col_idx] == "":
                    continue
                # Group names are on row 0 and tags are on row 1. To find a
                # tag's group name, we iterate backwards on row 0 until we
                # hit a value e.g:
                # Sans,        ,       ,Serif,
                #     ,Humanist,Grotesk,     ,Garalde,Didone
                #
                # ["Sans/Humanist", "Sans/Grotesk", "Serif/Garalde", "Serif/Didone"]
                group = next(
                    self.data[0][i]
                    for i in range(col_idx, 0, -1)
                    if self.data[0][i] != ""
                )
                if group not in self.CATEGORIES:
                    raise ValueError(
                        f"{group} isn't a know category, {self.CATEGORIES.keys()}"
                    )

                tag = columns[col_idx]
                if tag not in self.CATEGORIES[group]:
                    raise ValueError(f"{tag} isn't in {self.CATEGORIES[group]}")
                res.append(
                    {
                        "Family": row[0],
                        "Group/Tag": f"/{group}/{tag}",
                        "Weight": int(cell),
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
        # Please don't cry about all the empty columns below ;-).
        columns_0 = [
            'Family',
            'Family Dir',
            'Existing Category',
            'Sample Image',
            '',
            "Eli's Quality Score",
            "Eben's Quality Score",
            "UT's Quality Score",
            ' Type \n Categories',
            'Serif',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            'Sans',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            'Slab',
            '',
            '',
            '',
            '',
            'Script',
            '',
            '',
            '',
            '',
            '',
            'Display',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            'Arabic',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            'Hebrew',
            '',
            '',
            '',
            '',
            '',
            'South East Asian (Thai, Khmer, Lao)',
            '',
            '',
            '',
            '',
            '',
            'Sinhala',
            '',
            '',
            '',
            '',
            'Indic',
            '',
            '',
            '',
            '',
            '',
            ' Expressive\n Categories',
            'Simplicity',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            'Youthful',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            'Flow',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            ''
        ]
        columns_1 = [
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            'Humanist Venetian',
            'Old Style Garalde',
            'Transitional',
            'Modern',
            'Scotch',
            'Didone',
            'Fat Face',
            '',
            '',
            'Humanist',
            'Grotesque',
            'Neo Grotesque',
            'Geometric',
            'Rounded',
            'Superelipse',
            'Glyphic',
            '',
            '',
            'Geometric',
            'Humanist',
            'Clarendon',
            '',
            '',
            'Formal',
            'Informal',
            'Handwritten',
            'Upright Script',
            '',
            '',
            'Blackletter',
            'Wacky',
            'Blobby',
            'Woodtype',
            'Stencil',
            'Inline',
            'Distressed',
            'Shaded',
            'Techno',
            'Art Nouveau',
            'Tuscan',
            'Art Deco',
            'Medieval',
            'Brush/Marker',
            '',
            '',
            'Kufi',
            'Naskh',
            'Nastaliq',
            'Maghribi',
            'Ruqah',
            'Diwani',
            'Bihari',
            'Warsh',
            'Sudani',
            'West African',
            '',
            '',
            'Normal',
            'Ashurit',
            'Cursive',
            'Rashi',
            '',
            '',
            'Looped',
            'Loopless',
            'Moul (Khmer)',
            'Chrieng (Khmer)',
            '',
            '',
            'Traditional/High contrast',
            'Contemporary/High contrast',
            'Low contrast',
            '',
            '',
            'Traditional/High contrast',
            'Contemporary/High contrast',
            'Low contrast',
            'Sign Painting/vernacular',
            'Reverse-contrast',
            '',
            'Calm/simple',
            'Competent',
            'Business',
            'Sincere',
            'Loud',
            'Awkward',
            'Innovative',
            'Artistic',
            'Playful',
            'Excited',
            'Cute',
            'Happy',
            'Childlike',
            'Loud',
            'Rugged',
            'Vintage',
            'Stiff',
            'Rugged',
            'Futuristic',
            'Calm',
            'Childlike',
            'Active',
            'Cute',
            'Sophisticated',
            'Fancy',
            'Artistic'
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
