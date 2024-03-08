"""Generates a METADATA.pb from a config.yaml and a GitHub release URL

"""
import argparse
import os
from tempfile import TemporaryDirectory
import yaml
import zipfile

from gftools.packager import load_metadata
import gftools.fonts_public_pb2 as fonts_pb2
from gftools.builder import GFBuilder
from gftools.utils import download_file
from fontTools.ttLib import TTFont
import gftools.util.google_fonts as fonts
from copy import deepcopy


parser = argparse.ArgumentParser(description="Create an upstream.yaml for a family")
parser.add_argument("url", help="URL of GitHub release")
parser.add_argument("--family", help="Family name", required=False)
parser.add_argument("--config", help="Config file", default="sources/config.yaml", required=False)


def get_family_name(config):
    if "familyName" in config:
        return config["familyName"]
    return GFBuilder(config).get_family_name()


def generate_metadata(config, url):
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        raise ValueError("Not being run from a GitHub action?")
    if "category" not in config:
        config["category"] = ["SANS_SERIF"]

    metadata = fonts_pb2.FamilyProto()
    metadata.name = get_family_name(config)
    metadata.source.repository_url = os.environ["GITHUB_SERVER_URL"] + "/" + repo
    metadata.source.archive_url = url
    metadata.source.branch = "main"
    metadata.category.append(config["category"][0])
    metadata.designer = "Will be filled in"
    return metadata


def update_file_list(metadata):
    print("Downloading release archive...")
    with TemporaryDirectory() as tmp:
        archive_path = os.path.join(tmp, "archive.zip")
        download_file(metadata.source.archive_url, archive_path)
        license_found = False
        description_found = False
        a_font = None
        with zipfile.ZipFile(archive_path, "r") as zip_ref:
            zip_ref.extractall(tmp)
        metadata.source.files.clear()
        for root, _, files in os.walk(tmp):
            for file in files:
                fullpath = os.path.join(root, file)
                relpath = os.path.relpath(fullpath, tmp)
                print(relpath)
                item = fonts_pb2.SourceFileProto()
                if file == "OFL.txt":
                    license_found = True
                    item.source_file = relpath
                    item.dest_file = file
                    metadata.source.files.append(item)
                elif file == "DESCRIPTION.en_us.html":
                    description_found = True
                    metadata["files"][relpath] = file
                    item.source_file = relpath
                    item.dest_file = file
                    metadata.source.files.append(item)
                elif file == "ARTICLE.en_us.html":
                    item.source_file = relpath
                    item.dest_file = "article/"+file
                    metadata.source.files.append(item)
                elif file.endswith("ttf"):
                    if config.get("buildVariable", True):
                        # Only add the file if it is the variable font
                        if "[" in file:
                            item.source_file = relpath
                            item.dest_file = file
                            metadata.source.files.append(item)
                            a_font = fullpath
                    else:
                        # Add statics
                        item.source_file = relpath
                        item.dest_file = file
                        metadata.source.files.append(item)
                        a_font = fullpath

        # If there was a "googlefonts/" directory in the release, just
        # use files in that directory.
        if any("googlefonts/" in x.source_file for x in metadata.source.files):
            existing_files = deepcopy(metadata.source.files)
            metadata.source.files.clear()
            for item in existing_files:
                if "googlefonts/" in item.source_file or not ".ttf" in item.source_file:
                    metadata.source.files.append(item)

        if not license_found:
            raise ValueError(
                "No license file was found. Ensure OFL.txt is added the the release"
            )
        if not description_found and "Noto" not in metadata.name:
            raise ValueError(
                "No description file was found. Ensure DESCRIPTION.en_us.html is added the the release"
            )
        if not a_font:
            if config.get("buildVariable", True):
                raise ValueError("No variable font files were found. Is the build broken?")
            raise ValueError("No font files were found. Is the release broken?")

        designer = TTFont(a_font)["name"].getDebugName(9)
        if "Noto" in metadata.name:
            metadata.designer = "Google"
        elif designer:
            metadata.designer = designer


if __name__ == "__main__":
    args = parser.parse_args()
    if args.family:
        config = {"familyName": args.family}
    else:
        config = yaml.load(
            open(args.config), Loader=yaml.FullLoader
        )

    if os.path.isfile("METADATA.pb"):
        metadata = load_metadata("METADATA.pb")
    else:
        try:
            metadata = generate_metadata(config, args.url)
        except Exception as e:
            raise ValueError(
                "Something went wrong generating METADATA.pb (bug in updateupstream): "
                + str(e)
            )

    # Add archive URL
    metadata.source.archive_url = args.url
    update_file_list(metadata)
    fonts.WriteProto(metadata, "METADATA.pb")
