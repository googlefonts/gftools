#!/usr/bin/env python3
"""Generate a html report for the google/fonts repo

The report contains information regarding:
- Issues opened and closed
- How many families, metadata updates and infrastructure commits have been pushed
- How many commits each contributor has made

Usage:
gftools push-stats path/to/google/fonts/repo out.html
"""
from gftools.push import parse_server_file
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


def get_issues(repo):
    issues = list(repo.get_issues(state="all", since=datetime(2014, 1, 1)))
    res = []
    for i in issues:
        if i.pull_request:  # ignore prs
            continue
        d = {
            "date": i.created_at.isoformat().split("T")[0],
            "title": i.title,
            "closed": True if i.closed_at else False,
        }
        res.append(d)
    return res



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_path")
    parser.add_argument("out")
    args = parser.parse_args()

    push_template_dir = resource_filename("gftools", "push-templates")
    env = Environment(
        loader=FileSystemLoader(push_template_dir),
        autoescape=select_autoescape(),
    )

    print("Getting commits")
    repo = pygit2.Repository(args.repo_path)
    commits = get_commits(repo)

    print("Getting issues")
    github = Github(os.environ["GH_TOKEN"])
    repo = github.get_repo("google/fonts")
    issues = get_issues(repo)

    print("Getting server files")
    sb_path = os.path.join(args.repo_path, "to_sandbox.txt")
    sb_families = parse_server_file(sb_path)
    prod_path = os.path.join(args.repo_path, "to_production.txt")
    prod_families = parse_server_file(prod_path)

    template = env.get_template("index.html")
    with open(args.out, "w") as doc:
        doc.write(
            template.render(
                commit_data=json.dumps(
                    {
                        "issues": issues,
                        "commits": commits,
                        "pushes": {
                            "sandbox": [i.to_json() for i in sb_families],
                            "production": [i.to_json() for i in prod_families],
                        }
                    }
                ),
                current_year=datetime.now().year,
            )
        )


if __name__ == "__main__":
    main()