#!/usr/bin/env python3
"""
Generate the to_production.txt and to_sandbox.txt server files in a local
google/fonts repository.

to_production.txt file tells the engineers which directories need to be pushed
to the production server. Likewise, the to_sandbox.txt file is for directories
to be pushed to the sandbox server.

In order for this script to work, the traffic jam must be kept up to date and
pull requests must use labels.

Usage:
gftools gen-push-lists /path/to/google/fonts
"""
from gftools.push import parse_server_file
from github import Github
from collections import defaultdict
import os
import sys
from pathlib import Path
from gftools.push import repo_path_to_google_path


def pr_directories(pr):
    results = set()
    files = pr.get_files()
    for f in files:
        path = Path(f.filename)
        if path.suffix == ".textproto" and any(d in path.parts for d in ("lang", "axisregistry")):
            results.add(repo_path_to_google_path(path))
        else:
            path = path.parent
            # If a noto article has been updated, just return the family dir
            # ofl/notosans/article --> ofl/notosans
            if "article" in path.parts:
                path = path.parent
            results.add(str(path))
    return results


def write_server_file(data):
    doc = []
    categories_to_write = []
    for cat in (
        "New",
        "Upgrade",
        "Small fix/other",
        "Designer profile",
        "API Stuff",
        "Knowledge",
        "Metadata / Description / License",
    ):
        if cat in data:
            categories_to_write.append(cat)

    for cat in data:
        if cat not in categories_to_write:
            print(f"{cat} isn't sorted appending to end of doc")
            categories_to_write.append(cat)

    for cat in categories_to_write:
        directories = sorted(data[cat])
        doc.append(f"# {cat}")
        doc.append("\n".join(directories))
        doc.append("")
    return "\n".join(doc)


def main():
    if len(sys.argv) != 2:
        print("Usage: gftools gen-push-lists /path/to/google/fonts")
        sys.exit()

    to_sandbox = defaultdict(set)
    to_production = defaultdict(set)

    github = Github(os.environ["GH_TOKEN"])
    repo = github.get_repo("google/fonts")

    projects = repo.get_projects()
    traffic_jam = next((p for p in projects if p.name == "Traffic Jam"), None)
    if not traffic_jam:
        raise ValueError("Traffic Jam column has been deleted or renamed")
    columns = traffic_jam.get_columns()

    seen_directories = set()
    print("Analysing pull requests in traffic jam. This may take a while!")
    for col in columns:
        if col.name not in set(
            ["Just merged / In transit", "In Sandbox list", "In Production list"]
        ):
            continue
        cards = col.get_cards()
        for card in cards:
            content = card.get_content()
            if not hasattr(content, "labels"):
                print(f"skipping {card}. No labels!")
                continue

            labels = set(l.name for l in content.labels)
            pr = content.as_pull_request()
            directories = set(f"{directory} # {pr.html_url}" for directory in pr_directories(pr))

            if "-- blocked" in labels or "--- Live" in labels:
                continue
            seen_directories |= directories
            if "I Font Upgrade" in labels or "III VF Replacement" in labels:
                cat = "Upgrade"
            elif "I New Font" in labels:
                cat = "New"
            elif "I Description/Metadata/OFL" in labels:
                cat = "Metadata / Description / License"
            elif "I Designer profile" in labels:
                cat = "Designer profile"
            elif "I Knowledge" in labels:
                cat = "Knowledge"
            elif "I Axis Registry" in labels or "I API / Website / Platform" in labels:
                cat = "API Stuff"
            else:
                cat = "Small fix/other"
            if "--- to sandbox" in labels:
                to_sandbox[cat] |= directories
            if "--- to production" in labels:
                to_production[cat] |= directories

    gf_repo_path = sys.argv[1]
    sb_path = os.path.join(gf_repo_path, "to_sandbox.txt")
    prod_path = os.path.join(gf_repo_path, "to_production.txt")

    # Keep paths which have been entered manually which do not belong to
    # a label. These need to be manually deleted as well.
    existing_sandbox = parse_server_file(sb_path)
    for i in existing_sandbox:
        if str(i.raw) not in seen_directories:
            to_sandbox[i.type].add(str(i.raw))

    existing_production = parse_server_file(prod_path)
    for i in existing_production:
        if str(i.raw) not in seen_directories:
            to_production[i.type].add(str(i.raw))

    with open(sb_path, "w") as sb_doc:
        sb_doc.write(write_server_file(to_sandbox))

    with open(prod_path, "w") as prod_doc:
        prod_doc.write(write_server_file(to_production))

    print("Done!")


if __name__ == "__main__":
    main()
