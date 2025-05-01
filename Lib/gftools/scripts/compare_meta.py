#!/usr/bin/env python3
"""Compare metadata from different servers and generate a vimdiff HTML report."""
import json
import subprocess
import os
from glob import glob
import tempfile
import requests
from gftools.push.servers import (
    DEV_META_URL,
    SANDBOX_META_URL,
    PRODUCTION_META_URL,
    DEV_VERSIONS_URL,
    SANDBOX_VERSIONS_URL,
    PRODUCTION_VERSIONS_URL
)
import argparse


def munge_meta(obj):
    family_res = {}
    for family in obj["familyMetadataList"]:
        family_res[family["family"]] = {
            k: v
            for k, v in family.items()
            if k
            not in [
                "lastModified",
                "popularity",
                "trending",
                "defaultSort",
                "size",
                "dateAdded",
                #            "subsets"
            ]
        }
    obj["familyMetadataList"] = family_res
    obj["axisRegistry"].sort(key=lambda x: x["tag"])
    return obj


def munge_fontv(obj):
    return obj


def munge_family(obj):
    if "family" not in obj:
        return "Not in server yet"
    obj["coverage"] = list(obj["coverage"].keys())
    obj.pop("stats")
    obj.pop("size")
    obj.pop("lastModified")
    return obj


def generate_vimdiff_html(dev_file, sb_file, prod_file, output_file):
    """
    Use vimdiff to compare dev_meta, sb_meta, and prod_meta and save the results as an HTML file.
    Automatically handle swap files by deleting them if they exist.
    """
    # Check and delete swap files if they exist
    swap_files = glob(".*.swp")
    for swap_file in swap_files:
        os.remove(swap_file)
    try:
        # Run vimdiff in batch mode and output the results to an HTML file
        cmd = [
            "/usr/bin/vim",
            "-i",
            "NONE",
            "-n",
            "-N",
            "-d",
            dev_file,
            sb_file,
            prod_file,
            "-c",
            "TOhtml",
            "-c",
            f"sav! {output_file}",
            "-c",
            "qall!",
        ]
        subprocess.run(cmd, check=True)
        print(f"Comparison saved to {output_file}")
    except subprocess.CalledProcessError as e:
        print(f"Error running vimdiff: {e}")


def main(args=None):
    parser = argparse.ArgumentParser(
        description="Compare metadata from different servers."
    )
    diff_type = parser.add_mutually_exclusive_group()
    diff_type.add_argument("--meta", action="store_true", help="compare font metadata")
    diff_type.add_argument("--fontv", action="store_true", help="compare font version")
    diff_type.add_argument("--family", help="family to compare")

    parser.add_argument("out", help="output path to html file")
    args = parser.parse_args(args)
    if args.meta:
        munge = munge_meta
        dev_meta = munge(requests.get(DEV_META_URL).json())
        sb_meta = munge(requests.get(SANDBOX_META_URL).json())
        prod_meta = munge(requests.get(PRODUCTION_META_URL).json())
    elif args.fontv:
        munge = munge_fontv
        dev_meta = munge(json.loads(requests.get(DEV_VERSIONS_URL).text[4:]))
        sb_meta = munge(json.loads(requests.get(SANDBOX_VERSIONS_URL).text[4:]))
        prod_meta = munge(json.loads(requests.get(PRODUCTION_VERSIONS_URL).text[4:]))
    elif args.family:
        munge = munge_family
        dev_meta = munge(json.loads(requests.get(f"{DEV_META_URL}/{args.family}").text[4:]))
        sb_meta = munge(json.loads(requests.get(f"{SANDBOX_META_URL}/{args.family}").text[4:]))
        prod_meta = munge(json.loads(requests.get(f"{PRODUCTION_META_URL}/{args.family}").text[4:]))

    with tempfile.TemporaryDirectory() as temp_dir:
        dev_file = os.path.join(temp_dir, "dev_meta.json")
        sb_file = os.path.join(temp_dir, "sb_meta.json")
        prod_file = os.path.join(temp_dir, "prod_meta.json")
        with open(dev_file, "w") as f:
            json.dump(dev_meta, f, indent=4)
        with open(sb_file, "w") as f:
            json.dump(sb_meta, f, indent=4)
        with open(prod_file, "w") as f:
            json.dump(prod_meta, f, indent=4)
        generate_vimdiff_html(dev_file, sb_file, prod_file, args.out)


if __name__ == "__main__":
    main()
