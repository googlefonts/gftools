import argparse
import subprocess
import os
from github import Github
import re

g = Github(os.environ["GITHUB_TOKEN"])
parser = argparse.ArgumentParser(description="Return the URL of a font's latest release artefact")
parser.add_argument('--user', help='the repository username', default="notofonts")
parser.add_argument('--repo', help='the repository name')
parser.add_argument('family', help='the font family name')
args = parser.parse_args()

if not (args.user and args.repo):
    repo_url = subprocess.check_output(["git", "remote", "get-url", "origin"]).decode("utf8").strip()
    url_split = repo_url.split("/")
    args.user, args.repo = url_split[3], url_split[4]
repo = g.get_repo(args.user + '/' + args.repo)

for release in repo.get_releases():
    m = re.match(r"^(.*)-(v[\d.]+)", release.tag_name)
    if not m:
        print(f"Unparsable release {release.tag_name} in {repo_name}")
        continue
    family, version = m[1], m[2]
    if family != args.family:
        continue
    assets = release.get_assets()
    download_url = assets[0].browser_download_url
    print(f"::set-output name=version::{version}")
    print(f"::set-output name=url::{download_url}")
    break
