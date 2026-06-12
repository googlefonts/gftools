#!/usr/bin/env python3
"""
Add and replace tags from another tagging spreadsheet.
"""
import csv
import math
import argparse
from pathlib import Path


def read_csv(filepath):
    """Read CSV file and return list of rows."""
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        return list(reader)


def write_csv(filepath, rows):
    """Write rows to CSV file."""
    with open(filepath, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerows(rows)


def sort_rows(rows):
    """
    Sort rows by displayName (col 0) then category (col 2), faithful to the JS:
    if (`${a.displayName},${a.category}` < `${b.displayName},${b.category}`)

    The "displayName,category" string is the primary key (kept comma-joined as in
    the JS so family/tag ordering stays byte-identical to existing files). The
    axis column (col 1) is NOT part of the primary key — including it there would
    reshuffle every variable-font row away from the established (family, tag)
    order. Instead, within each (family, tag) group VF rows are ordered by the
    NUMERIC axis value, so e.g. wght@400 precedes wght@800 and wght@900 precedes
    wght@1000.
    """

    data_rows = rows

    def axis_value(axis):
        # Parse "wght@400" -> ("wght", 400.0) so variable-font rows order by the
        # NUMERIC axis value (wght@400 before wght@800, wght@900 before wght@1000).
        # Static rows (empty axis) sort first within a (family, tag) group.
        if "@" in axis:
            name, _, value = axis.partition("@")
            try:
                return (name, float(value))
            except ValueError:
                return (axis, math.inf)
        return ("", float("-inf"))

    def sort_key(row):
        # Primary key "displayName,category" (col 0, col 2 — NOT the axis col 1),
        # kept as the original JS string so family/tag order stays byte-identical.
        # Tiebreak on the axis (col 1) by numeric value within each (family, tag).
        return (f"{row[0]},{row[2]}", axis_value(row[1]))

    sorted_data = sorted(data_rows, key=sort_key)
    return sorted_data


def merge_csvs(source_path, target_path, tag_category, output_path=None):
    """
    Merge source CSV into target CSV.
    - If first 3 columns match, update 4th column only
    - Otherwise, add new row
    - Sort and save result
    """
    source_rows = read_csv(source_path)
    target_rows = read_csv(target_path)

    # Assume first row is header
    if len(source_rows) == 0 or len(target_rows) == 0:
        print("Error: One or both CSV files are empty")
        return

    source_data = {(r[0], r[1], r[2]): r for r in source_rows}
    target_data = {(r[0], r[1], r[2]): r for r in target_rows if r}

    to_add = set(source_data.keys()) - set(target_data.keys())
    to_update = set(source_data.keys()) & set(target_data.keys())

    for key in to_add:
        _, _, category = key
        if category != tag_category:
            continue
        target_data[key] = source_data[key]

    for key in to_update:
        _, _, category = key
        if category != tag_category:
            continue
        target_data[key][3] = source_data[key][3]

    all_rows = list(target_data.values())
    sorted_rows = sort_rows(all_rows)

    output = output_path if output_path else target_path
    write_csv(output, sorted_rows)
    print(f"Merged CSV saved to: {output}")
    print(f"Total rows (including header): {len(sorted_rows)}")


def main(args=None):
    parser = argparse.ArgumentParser(
        description="Merge two CSV files with custom logic and sorting"
    )
    parser.add_argument(
        "source", type=Path, help="Source CSV file (rows to merge from)"
    )
    parser.add_argument(
        "target", type=Path, help="Target CSV file (rows to merge into)"
    )
    parser.add_argument("tag_category", help="Tag category to add/replace")
    parser.add_argument(
        "-o", "--output", type=Path, help="Output CSV file (default: overwrite target)"
    )
    args = parser.parse_args(args)

    merge_csvs(args.source, args.target, args.tag_category, args.output)


if __name__ == "__main__":
    main()
