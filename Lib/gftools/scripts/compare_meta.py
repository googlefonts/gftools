#!/usr/bin/env python3
"""Compare metadata from different servers and generate a vimdiff HTML report."""
import json
import subprocess
import os
from glob import glob
import tempfile
import requests
from gftools.push.servers import (
    SANDBOX_META_URL,
    PRODUCTION_META_URL,
    SANDBOX_VERSIONS_URL,
    PRODUCTION_VERSIONS_URL,
)
import argparse
import sys


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


def munge_designer(obj):
    return obj


def munge_family(obj):
    if "family" not in obj:
        return "Not in server yet"
    obj["coverage"] = list(obj["coverage"].keys())
    obj.pop("stats")
    obj.pop("size")
    obj.pop("lastModified")
    return obj


def pr_json(number):
    cmd = ["gh", "pr", "view", number, "--json", "title,labels,number,files"]
    msg = subprocess.run(cmd, check=True, capture_output=True)
    data = json.loads(msg.stdout.decode("utf-8"))
    return data


def levenstein(a, b):
    if len(a) < len(b):
        return levenstein(b, a)

    if len(b) == 0:
        return len(a)

    if len(b) == 1:
        return 1 if a.find(b) != -1 else len(a)

    # let a and b be lists of characters
    a = list(a)
    b = list(b)
    alen = len(a)
    blen = len(b)
    current_row = range(alen + 1)

    for i in range(1, blen + 1):
        previous_row, current_row = current_row, [i] * (alen + 1)
        for j in range(1, alen + 1):
            insertions = previous_row[j] + 1
            deletions = current_row[j - 1] + 1
            substitutions = previous_row[j - 1] + (a[j - 1] != b[i - 1])
            current_row[j] = min(insertions, deletions, substitutions)

    return current_row[alen]


def doc_in_server(doc, dev_data, sb_data, prod_data):
    dev_res = levenstein(json.dumps(dev_data), doc)
    sb_res = levenstein(json.dumps(sb_data), doc)
    prod_res = levenstein(json.dumps(prod_data), doc)

    best = min(dev_res, sb_res, prod_res)
    if dev_res == best:
        return "dev"
    elif sb_res == best:
        return "sb"
    elif prod_res == best:
        return "prod"


def which_server_metadata(string, family):
    munge = munge_family
    dev_meta = munge(json.loads(requests.get(f"{DEV_META_URL}/{family}").text[4:]))
    sb_meta = munge(json.loads(requests.get(f"{SANDBOX_META_URL}/{family}").text[4:]))
    prod_meta = munge(
        json.loads(requests.get(f"{PRODUCTION_META_URL}/{family}").text[4:])
    )
    res = doc_in_server(string, dev_meta, sb_meta, prod_meta)


def pr_type(data):
    if data["labels"][0]["name"] == "I Metadata/OFL":
        file_to_check = next(f for f in data["files"] if "METADATA.pb" in f["path"])
        if file_to_check:
            with open(file_to_check["path"], "r") as doc:
                which_server_metadata(doc.read(), "Huninn")


def get_designer(url, designer):
    dev_meta = requests.get(url).json()
    for family in dev_meta["familyMetadataList"]:
        for family_designer in family["designers"]:
            if family_designer == designer:
                family_to_check = family["family"]
                data = json.loads(requests.get(f"{url}/{family_to_check}").text[4:])
                return next(d for d in data["designers"] if d["name"] == designer)
    return {}


def generate_vimdiff_html(sb_file, prod_file, output_file):
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
            sb_file,
            prod_file,
            "-c",
            "windo set wrap",
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
    parser.add_argument("--gf-path", help="path to google/fonts")
    diff_type = parser.add_mutually_exclusive_group()
    diff_type.add_argument("--pr", help="diff a pr")
    diff_type.add_argument("--meta", action="store_true", help="compare font metadata")
    diff_type.add_argument("--fontv", action="store_true", help="compare font version")
    diff_type.add_argument("--family", help="family to compare")
    diff_type.add_argument("--designer", help="designer to compare")

    parser.add_argument("-o", "--out", help="output path to html file")
    args = parser.parse_args(args)
    # TODO make this a required arg if a pr is given
    if args.gf_path:
        os.chdir(args.gf_path)
    if args.pr:
        raise (NotImplementedError("PR diff not implemented yet"))
        data = pr_json(args.pr)
        pr_type(data)
        import pdb

        pdb.set_trace()
        return
    if args.meta:
        munge = munge_meta
        sb_meta = munge(requests.get(SANDBOX_META_URL).json())
        prod_meta = munge(requests.get(PRODUCTION_META_URL).json())
    elif args.fontv:
        munge = munge_fontv
        sb_meta = munge(json.loads(requests.get(SANDBOX_VERSIONS_URL).text[4:]))
        prod_meta = munge(json.loads(requests.get(PRODUCTION_VERSIONS_URL).text[4:]))
    elif args.family:
        munge = munge_family
        sb_meta = munge(
            json.loads(requests.get(f"{SANDBOX_META_URL}/{args.family}").text[4:])
        )
        prod_meta = munge(
            json.loads(requests.get(f"{PRODUCTION_META_URL}/{args.family}").text[4:])
        )
    elif args.designer:
        munge = munge_designer
        sb_meta = get_designer(SANDBOX_META_URL, args.designer)
        prod_meta = get_designer(PRODUCTION_META_URL, args.designer)

    with tempfile.TemporaryDirectory() as temp_dir:
        sb_file = os.path.join(temp_dir, "sb_meta.json")
        prod_file = os.path.join(temp_dir, "prod_meta.json")
        with open(sb_file, "w") as f:
            json.dump(sb_meta, f, indent=4)
        with open(prod_file, "w") as f:
            json.dump(prod_meta, f, indent=4)
        if args.out:
            generate_vimdiff_html(sb_file, prod_file, args.out)
        else:
            generate_vimdiff_html(
                sb_file, prod_file, os.path.join(temp_dir, "diff.html")
            )
            if sys.platform == "linux":
                open_cmd = "xdg-open"
            elif sys.platform == "darwin":
                open_cmd = "open"
            elif sys.platform == "win32":
                open_cmd = "start"
            else:
                raise NotImplementedError("Unsupported OS")
            subprocess.run([open_cmd, os.path.join(temp_dir, "diff.html")])
            print("Hit any key to exit")
            input()


if __name__ == "__main__":
    main()
