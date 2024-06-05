import argparse
import subprocess
import os
from github import Github
import re


def get_latest_release(family, user=None, repo=None):
    if not (user and repo):
        repo_url = (
            subprocess.check_output(["git", "remote", "get-url", "origin"])
            .decode("utf8")
            .strip()
        )
        url_split = repo_url.split("/")
        user, repo = url_split[3], url_split[4]

    g = Github(os.environ["GITHUB_TOKEN"])
    repo = g.get_repo(user + "/" + repo)
    for release in repo.get_releases():
        if release.draft:
            continue
        m = re.match(r"^(.*)-(v[\d.]+)", release.tag_name)
        if not m:
            print(f"Unparsable release {release.tag_name} in {repo_name}")
            continue
        thisfamily, version = m[1], m[2]
        if thisfamily != family:
            continue
        assets = release.get_assets()
        download_url = assets[0].browser_download_url
        return version, download_url
    return None, None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Return the URL of a font's latest release artefact"
    )
    parser.add_argument("--user", help="the repository username", default="notofonts")
    parser.add_argument("--repo", help="the repository name")
    parser.add_argument("family", help="the font family name")
    args = parser.parse_args()

    version, download_url = get_latest_release(args.family, args.user, args.repo)
    if version and download_url:
        print(f"::set-output name=version::{version}")
        print(f"::set-output name=url::{download_url}")
