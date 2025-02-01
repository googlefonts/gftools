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
import sys
import os
from gftools.push.trafficjam import (
    PushItems,
    PushStatus,
    PushList,
)
from gftools.push.utils import branch_matches_google_fonts_main
from pathlib import Path
from gftools.utils import is_google_fonts_repo
from contextlib import contextmanager
import pygit2


@contextmanager
def in_google_fonts_repo(gf_path):
    cwd = os.getcwd()
    try:
        os.chdir(gf_path)
        yield True
    finally:
        os.chdir(cwd)


def main(args=None):
    if len(sys.argv) != 3:
        print("Usage: gftools gen-push-lists /path/to/google/fonts")
        sys.exit()

    gf_path = Path(sys.argv[2])
    if not is_google_fonts_repo(gf_path):
        raise ValueError(f"'{gf_path}' is not a valid google/fonts repo")

    with in_google_fonts_repo(gf_path):
        branch_matches_google_fonts_main(gf_path)
        to_sandbox_fp = os.path.join(gf_path, "to_sandbox.txt")
        to_production_fp = os.path.join(gf_path, "to_production.txt")

        # get existing push items
        board_items = PushItems.from_traffic_jam()
        sandbox_file = PushItems.from_server_file(
            to_sandbox_fp, PushStatus.IN_DEV, PushList.TO_SANDBOX
        )
        production_file = PushItems.from_server_file(
            to_production_fp, PushStatus.IN_SANDBOX, PushList.TO_PRODUCTION
        )

        sandbox_board = board_items.to_sandbox()
        production_board = board_items.to_production()
        live_board = board_items.live()

        to_sandbox = (sandbox_file + sandbox_board) - production_board
        to_production = (production_file + production_board) - live_board

        to_sandbox.to_server_file(to_sandbox_fp)
        to_production.to_server_file(to_production_fp)

    repo = pygit2.Repository(str(gf_path))
    if any("tags/all/families.csv" in d.delta.new_file.path for d in repo.diff()):
        with open(to_sandbox_fp, "r", encoding="utf-8") as doc:
            string = doc.read()
        string += "\n# Tags\ntags/all/families.csv\n"
        with open(to_sandbox_fp, "w", encoding="utf-8") as doc:
            doc.write(string)


if __name__ == "__main__":
    main()
