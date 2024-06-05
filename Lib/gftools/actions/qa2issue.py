"""Post the contents of a QA run either to a new GitHub issue or as a comment
to an existing one.

When a font is automatically tested, we want to alert the user with a more
helpful (and visible) message than just a failure in the action log; but at
the same time we don't want to spam them by opening new issues every commit.

This script takes a file and a version, and checks whether there is a GitHub
issue labelled qa-``version``. If not, it creates an issue with the text
provided, and labels it accordingly; if there is, it adds the text as a new comment.
"""

import argparse
import subprocess
from gftools.gfgithub import GitHubClient

if __name__ == "__main__":
    url_split = (
        subprocess.check_output(["git", "remote", "get-url", "origin"])
        .decode("utf8")
        .strip()
        .split("/")
    )
    client = GitHubClient(url_split[3], url_split[4])

    parser = argparse.ArgumentParser(description="Create or update github issue")
    parser.add_argument(
        "--template",
        help="the issue name",
        default="Fontbakery QA Report for Version {}",
    )
    parser.add_argument("version", help="the proposed version")
    parser.add_argument("file", help="file containing MarkDown content")
    args = parser.parse_args()

    label = f"qa-{args.version}"

    try:
        client._post(client.rest_url("labels"), {"name": label})
    except Exception as e:
        if "already_exists" not in str(e):
            raise

    text = open(args.file).read()

    open_issues = client._get(client.rest_url("issues", labels=label))
    if open_issues:
        issue_id = open_issues[0]["number"]
        response = client.create_issue_comment(issue_id, text)
    else:
        title = args.template.format(args.version)
        response = client.create_issue(title, text)
        number = response["number"]
        client._post(client.rest_url(f"issues/{number}/labels"), {"labels": [label]})
    see_url = response["html_url"]

    print(
        f"::error file=sources/config.yaml,title=Fontbakery check failed::See {see_url}"
    )
