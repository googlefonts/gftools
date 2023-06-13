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
from gftools.push import PushItems, PushStatus


def main(args=None):
    if len(sys.argv) != 3:
        print("Usage: gftools gen-push-lists /path/to/google/fonts")
        sys.exit()

    gf_path = sys.argv[2]
    to_sandbox_fp = os.path.join(gf_path, "to_sandbox.txt")
    to_production_fp = os.path.join(gf_path, "to_production.txt")

    board_items = PushItems.from_traffic_jam()

    sandbox_file = PushItems.from_server_file(to_sandbox_fp, PushStatus.IN_DEV)
    for item in board_items:
        if item.status == PushStatus.IN_DEV:
            sandbox_file.add(item)
    sandbox_file.to_server_file(to_sandbox_fp)

    production_file = PushItems.from_server_file(to_production_fp, PushStatus.IN_SANDBOX)
    for item in board_items:
        if item.status == PushStatus.IN_SANDBOX:
            production_file.add(item)
    production_file.to_server_file(to_production_fp)


if __name__ == "__main__":
    main()
