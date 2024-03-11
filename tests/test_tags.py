import pytest
import tempfile
import subprocess
import os
from pathlib import Path
import csv


@pytest.fixture(scope="session")
def items():
    with tempfile.TemporaryDirectory() as tmp_dir:
        gf_path = Path(tmp_dir) / "google" / "fonts"
        os.makedirs(gf_path / "ofl" / "abel")
        subprocess.run(["gftools", "font-tags", "write", gf_path])

        csv_path = gf_path / "tags" / "all" / "families.csv"
        with open(csv_path, encoding="utf-8") as doc:
            return list(
                csv.DictReader(doc, ["Family", "Group/Tag", "Weight"], strict=True)
            )


@pytest.mark.parametrize(
    "item",
    [
        {"Family": "Handlee", "Group/Tag": "/Script/Handwritten", "Weight": "100"},
        {"Family": "Karla", "Group/Tag": "/Sans/Grotesque", "Weight": "100"},
        {"Family": "Family", "Group/Tag": "Group/Tag", "Weight": "Weight"},
        {"Family": "Aleo", "Group/Tag": "/Slab/Humanist", "Weight": "100"},
    ],
)
def test_write_font_tags(items, item):
    assert item in items
