#!/usr/bin/env python3
"""Generate a html report for the google/fonts repo

The report contains information regarding:
- Issues opened and closed
- How many families, metadata updates and infrastructure commits have been pushed
- How many commits each contributor has made

Usage:
gftools push-stats path/to/google/fonts/repo out.html
"""
from gftools.push.trafficjam import PushItems
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pkg_resources import resource_filename
from datetime import datetime
import pygit2
from github import Github
import os
import json
import argparse


def get_commits(repo):
    commits = list(repo.walk(repo.head.target))
    res = []
    for idx in range(1, len(commits)):
        current_commit = commits[idx - 1]
        prev_commit = commits[idx]

        # Basic meta
        author = current_commit.author.name
        title = current_commit.message.split("\n")[0]
        date = datetime.fromtimestamp(int(current_commit.commit_time))

        diff = prev_commit.tree.diff_to_tree(current_commit.tree)
        if "Merge branch" in current_commit.message:
            continue
        # Commit has all new files
        if all(d.status == 1 for d in diff.deltas):
            status = "new"
        # Contains modifications
        elif any(d.status == 3 for d in diff.deltas):
            status = "modified"
        else:
            status = "modified"

        # Type of commit
        if any(d.new_file.path.endswith(("ttf", "otf")) for d in diff.deltas):
            kind = "family"
        elif any(
            d.new_file.path.endswith(("metadata.pb", "DESCRIPTION.en_us.html"))
            for d in diff.deltas
        ):
            kind = "metadata"
        elif any(d.new_file.path.endswith("info.pb") for d in diff.deltas):
            kind = "designer"
        else:
            kind = "infrastructure"

        res.append(
            {
                "date": date.isoformat(),
                "title": title,
                "author": author,
                "status": status,
                "kind": kind,
                "id": str(current_commit.id),
            }
        )
    return res


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_path")
    parser.add_argument("out")
    args = parser.parse_args(args)

    push_template_dir = resource_filename("gftools", "push-templates")
    env = Environment(
        loader=FileSystemLoader(push_template_dir),
        autoescape=select_autoescape(),
    )

    data_out = os.path.join(os.path.dirname(args.out), "gf_repo_data.json")
    if os.path.exists(data_out):
        commit_data = json.load(open(data_out, encoding="utf8"))
        last_run = datetime.fromisoformat(commit_data["last_run"])
    else:
        commit_data = {"issues": []}
        last_run = datetime(2014, 1, 1)

    print("Getting commits")
    repo = pygit2.Repository(args.repo_path)
    commits = get_commits(repo)

    print("Getting server files")
    sb_path = os.path.join(args.repo_path, "to_sandbox.txt")
    sb_families = PushItems.from_server_file(sb_path)
    prod_path = os.path.join(args.repo_path, "to_production.txt")
    prod_families = PushItems.from_server_file(prod_path)

    template = env.get_template("index.html")

    print("Writing json data")
    commit_data = {
        "last_run": datetime.now().strftime("%Y-%m-%d"),
        "commits": commits,
        "pushes": {
            "sandbox": [i.to_json() for i in sb_families],
            "production": [i.to_json() for i in prod_families],
        },
    }
    json.dump(commit_data, open(data_out, "w", encoding="utf8"), indent=4)

    print("Writing report")
    with open(args.out, "w") as doc:
        doc.write(template.render(commit_data=json.dumps(commit_data)))


if __name__ == "__main__":
    main()
