"""Test whether a new release of a font is needed, inform GitHub if so.

This looks for changes to the font sources which alter the font version. If
the version in the font source is greater than the version number found in
the last git tag, then the new version number (to be used as a git tag)
is reported to GitHub actions via the set-output mechanism.

This is expected to be run within a git repository:

    % python3 -m gftools.actions.checkversionbump
    Current version is:  v1.001
    There were no git tags.
    Current version is  <bumpversion.Version:major=1, minor=1>
    Old version was  v1.000
    Result was untagged, new tag v1.001
    ::set-output name=result::untagged
    ::set-output name=newtag::v1.001

"""

import yaml
import os
import re
from sys import exit
from bumpfontversion.ufohandler import UFOHandler
from bumpfontversion.glyphshandler import GlyphsHandler
import pygit2
import tempfile


def get_version(path):
    for handler in [UFOHandler(), GlyphsHandler()]:
        if not handler.applies_to(path):
            continue
        return handler.current_version(path)


def get_git_tags():
    repo = pygit2.Repository(os.path.join(os.getcwd(), ".git"))
    regex = re.compile("^refs/tags/v")
    tags = [r.replace("refs/tags/", "") for r in repo.references if regex.match(r)]
    return tags


def format_tag(version):
    v = int(version["major"].value) + (int(version["minor"].value) / 1000)
    return "v%.03f" % v


def version_has_ever_changed(file, version):
    repo = pygit2.Repository(os.path.join(os.getcwd(), ".git"))
    last = repo[repo.head.target]
    print("Current version is ", version)
    for commit in repo.walk(last.id, pygit2.GIT_SORT_TIME):
        with tempfile.TemporaryDirectory() as tmpdirname:
            repo.checkout_tree(commit, directory=tmpdirname)
            if os.path.isfile(os.path.join(tmpdirname, "sources", file)):
                old_version = format_tag(
                    get_version(os.path.join(tmpdirname, "sources", file))
                )
                if old_version != format_tag(version):
                    print("Old version was ", old_version)
                    return True
    return False


if __name__ == "__main__":
    config = yaml.load(
        open(os.path.join("sources", "config.yaml")), Loader=yaml.FullLoader
    )
    sources = config["sources"]

    current_version = None

    for source in sources:
        this_version = get_version(os.path.join("sources", source))
        if current_version and format_tag(current_version) != format_tag(this_version):
            print(
                "Version mismatch: {} in {} != {}".format(
                    format_tag(current_version), source, format_tag(this_version)
                )
            )
            exit(1)
        current_version = this_version

    tags = get_git_tags()
    print("Current version is: ", format_tag(current_version))
    if tags:
        print("There were git tags, current version not amongst them: ", tags)
        needs_release = current_version not in tags
    else:
        print("There were no git tags.")
        needs_release = version_has_ever_changed(sources[0], current_version)

    if needs_release:
        result = "untagged"
        newtag = format_tag(current_version)
    else:
        result = "ok"
        newtag = ""

    print(f"Result was {result}, new tag {newtag}")
    print(f"::set-output name=result::{result}")
    print(f"::set-output name=newtag::{newtag}")
