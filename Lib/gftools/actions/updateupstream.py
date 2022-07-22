"""Generates an upstream.yaml from a config.yaml and a GitHub release URL

"""
import argparse
import os
from tempfile import TemporaryDirectory
import yaml
import zipfile

import gftools.packager
from gftools.builder import GFBuilder
from strictyaml import as_document
from gftools.utils import download_file
from fontTools.ttLib import TTFont


parser = argparse.ArgumentParser(description="Create an upstream.yaml for a family")
parser.add_argument("url", help="URL of GitHub release")
parser.add_argument("--family", help="Family name", required=False)
parser.add_argument("--config", help="Config file", default="sources/config.yaml", required=False)


def get_family_name(config):
    if "familyName" in config:
        return config["familyName"]
    return GFBuilder(config).get_family_name()


def generate_upstream(config, url):
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        raise ValueError("Not being run from a GitHub action?")
    if "category" not in config:
        config["category"] = ["SANS_SERIF"]

    upstream = {
        "name": get_family_name(config),
        "repository_url": os.environ["GITHUB_SERVER_URL"] + "/" + repo + ".git",
        "archive": url,
        "branch": "main",
        "category": config["category"],
        "build": "",
        "files": {},
        "designer": "Will be filled in",
    }
    return upstream


def update_file_list(upstream):
    print("Downloading release archive...")
    upstream["files"] = {}
    with TemporaryDirectory() as tmp:
        archive_path = os.path.join(tmp, "archive.zip")
        download_file(upstream["archive"], archive_path)
        license_found = False
        description_found = False
        a_font = None
        with zipfile.ZipFile(archive_path, "r") as zip_ref:
            zip_ref.extractall(tmp)
        for root, _, files in os.walk(tmp):
            for file in files:
                fullpath = os.path.join(root, file)
                relpath = os.path.relpath(fullpath, tmp)
                print(relpath)
                if file == "OFL.txt":
                    license_found = True
                    upstream["files"][relpath] = file
                elif file == "DESCRIPTION.en_us.html":
                    description_found = True
                    upstream["files"][relpath] = file
                elif file == "ARTICLE.en_us.html":
                    upstream["files"][relpath] = "article/"+file
                elif file.endswith("ttf"):
                    if config.get("buildVariable", True):
                        # Only add the file if it is the variable font
                        if "[" in file:
                            upstream["files"][relpath] = file
                            a_font = fullpath
                    else:
                        # Add statics
                        upstream["files"][relpath] = file
                        a_font = fullpath

        # If there was a "googlefonts/" directory in the release, just
        # use files in that directory.
        if any("googlefonts/" in x for x in upstream["files"].keys()):
            upstream["files"] = {str(k):str(v) for k,v in upstream["files"].items() if "googlefonts/" in str(k) or not ".ttf" in str(k) }

        if not license_found:
            raise ValueError(
                "No license file was found. Ensure OFL.txt is added the the release"
            )
        if not description_found and "Noto" not in upstream["name"]:
            raise ValueError(
                "No description file was found. Ensure DESCRIPTION.en_us.html is added the the release"
            )
        if not a_font:
            if config.get("buildVariable", True):
                raise ValueError("No variable font files were found. Is the build broken?")
            raise ValueError("No font files were found. Is the release broken?")

        designer = TTFont(a_font)["name"].getDebugName(9)
        if "Noto" in upstream["name"]:
            upstream["designer"] = "Google"
        elif designer:
            upstream["designer"] = designer


if __name__ == "__main__":
    args = parser.parse_args()
    if args.family:
        config = {"familyName": args.family}
    else:
        config = yaml.load(
            open(args.config), Loader=yaml.FullLoader
        )

    if os.path.isfile("upstream.yaml"):
        try:
            upstream = gftools.packager._upstream_conf_from_file(
                "upstream.yaml", yes=True, quiet=True
            )
        except Exception as e:
            raise ValueError("Something went wrong parsing upstream.yaml: " + str(e))
    else:
        try:
            upstream = as_document(
                generate_upstream(config, args.url),
                gftools.packager.upstream_yaml_schema,
            )
        except Exception as e:
            raise ValueError(
                "Something went wrong generating upstream.yaml (bug in updateupstream): "
                + str(e)
            )

    # Add archive URL
    upstream["archive"] = args.url
    update_file_list(upstream)

    with open("upstream.yaml", "w") as upstream_yaml_file:
        upstream_yaml_file.write(upstream.as_yaml())
