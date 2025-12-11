#!/usr/bin/env python3
"""
Add and replace tags from another tagging spreadsheet.
"""
import csv
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
    Sort rows by displayName (col 0) and category (col 1).
    Ported from JS code:
    if (`${a.displayName},${a.category}` < `${b.displayName},${b.category}`)
    """

    data_rows = rows

    def sort_key(row):
        # Create sort key as "displayName,category"
        return f"{row[0]},{row[1]},{row[2]}"

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
