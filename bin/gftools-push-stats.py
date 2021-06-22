#!/usr/bin/env python3
"""Report how many fonts have been added/updated between two dates

Usage: python push-stats.py from_date to_date
       python push-stats.py 2020-01-01 2020-06-01

WARNING: was written in < 30 mins by Marc Foley. Do not expect miracles :)
"""
import requests
import json
from datetime import datetime, timedelta
import sys

if len(sys.argv) != 3:
    print("Usage: python info.py YYYY-MM-DD YYYY-MMDD")
    print("e.g: python info.py 2020-01-01 2020-06-01")
    sys.exit()

from_date = sys.argv[1]
to_date = sys.argv[2]

r = requests.get("http://fonts-dev.sandbox.google.com/metadata/fonts")
data = json.loads(r.text.replace(")]}'", ""))


family_meta = data['familyMetadataList']


new_families = []
updated_families = []
for family in family_meta:
    if family['dateAdded'] >= from_date and family['dateAdded'] <= to_date:
        new_families.append(family)

    if family['lastModified'] >= from_date and family['lastModified'] <= to_date:
        if family not in new_families:
            updated_families.append(family)

print("new families", len(new_families))
print("updated families", len(updated_families))


def family_info(family):
    axes = ",".join([a['tag'] for a in family['axes']])
    print(f"{family['family']}\t{axes}")

print("NEW FAMILIES")
for family in new_families:
    family_info(family)
print("")

print("UPDATED FAMILIES")
for family in updated_families:
    family_info(family)
print("")
