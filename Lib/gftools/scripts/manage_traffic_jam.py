"""
Google Fonts Traffic Jam manager

Set the Status items in the Google Fonts Traffic Jam board.
https://github.com/orgs/google/projects/74

Users will need to have Github Hub installed.
https://hub.github.com/

"""

import subprocess
from rich.pretty import pprint
from gftools.logging import setup_logging
from gftools.argparse import GFArgumentParser
from gftools.push.utils import branch_matches_google_fonts_main
from gftools.push.servers import GFServers, Items
from gftools.push.items import Family, FamilyMeta
from gftools.push.trafficjam import (
    PushItem,
    PushItems,
    PushStatus,
    PushCategory,
    STATUS_OPTION_IDS,
)
import os
import argparse
from pathlib import Path
import tempfile
import json
import sys
import logging
from typing import Optional
from configparser import ConfigParser

log = logging.getLogger("gftools.push")

# This module uses api endpoints which shouldn't be public. Ask
# Marc Foley for the .gf_push_config.ini file. Place this file in your
# home directory. Environment variables can also be used instead.
config = ConfigParser()
config.read(os.path.join(os.path.expanduser("~"), ".gf_push_config.ini"))


DEV_URL = os.environ.get("DEV_META_URL") or config["urls"]["dev_url"]
SANDBOX_URL = os.environ.get("SANDBOX_URL") or config["urls"]["sandbox_url"]
PRODUCTION_URL = "https://fonts.google.com"


try:
    subprocess.run("gh", stdout=subprocess.DEVNULL).returncode == 0
except:
    raise SystemError(
        "GitHub CLI is not installed. https://github.com/cli/cli#installation"
    )


class ItemChecker:
    def __init__(
        self,
        push_items: PushItems,
        gf_fp: "str | Path",
        servers: GFServers,
        servers_fp: "str | Path",
    ):
        self.push_items = push_items
        self.gf_fp = gf_fp
        self.servers = servers
        self.servers_fp = servers_fp
        self.skip_pr: Optional[str] = None

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, exception_traceback):
        self.git_checkout_main()

    def user_input(self, item: PushItem):
        input_text = (
            "Bump pushlist: [y/n], block: [b] skip pr: [s], inspect: [i], quit: [q]?: "
        )
        user_input = input(input_text)

        if "*" in user_input:
            item.bump_pushlist()
            for sub_item in self.push_items:
                if sub_item.url != item.url:
                    continue
                sub_item.push_list = item.push_list
            self.skip_pr = item.url
        if "y" in user_input:
            item.bump_pushlist()
        if "b" in user_input:
            item.block()
        if "s" in user_input:
            self.skip_pr = item.url
        if "i" in user_input:
            self.vim_diff(item.item)
            self.user_input(item)
        if "q" in user_input:
            self.__exit__(None, None, None)
            sys.exit()

    def git_checkout_item(self, push_item: PushItem):
        if not push_item.merged:
            cmd = ["gh", "pr", "checkout", push_item.url.split("/")[-1], "-f"]
            subprocess.call(cmd)
        else:
            self.git_checkout_main()

    def git_checkout_main(self):
        cmd = ["git", "checkout", "main", "-f"]
        subprocess.call(cmd)

    def vim_diff(self, item: Items):
        items = [("local", item)]
        for server in self.servers:
            items.append((server.name, server.find_item(item)))

        files = []
        for server, item in items:
            tmp = tempfile.NamedTemporaryFile(suffix=server, mode="w+")
            if item:
                json.dump(item.to_json(), tmp, indent=4)
                tmp.flush()
                files.append(tmp)
        subprocess.call(["vimdiff", "-c", "windo set wrap"] + [f.name for f in files])
        for f in files:
            f.close()

    def display_item(self, push_item: PushItem):
        res = {}
        item = push_item.item
        if item:
            comparison = self.servers.compare_item(item)
            if push_item.category in [PushCategory.UPGRADE, PushCategory.NEW]:
                res.update(
                    {
                        **comparison,
                        **push_item.__dict__,
                        **{
                            "dev url": "{}/specimen/{}".format(
                                DEV_URL, item.name.replace(" ", "+")
                            ),
                            "sandbox url": "{}/specimen/{}".format(
                                SANDBOX_URL, item.name.replace(" ", "+")
                            ),
                            "prod url": "{}/specimen/{}".format(
                                PRODUCTION_URL, item.name.replace(" ", "+")
                            ),
                        },
                    }
                )
            else:
                res.update(
                    {
                        **comparison,
                        **push_item.__dict__,
                    }
                )
        else:
            res.update(push_item.__dict__)
        pprint(res)

    def update_server(self, push_item: PushItem, servers: GFServers):
        if not push_item.merged:
            return
        item = push_item.item
        if item == None:
            # Generally this is because this is something we don't
            # track; e.g. lang data
            log.debug(
                f"Cannot update server for {push_item.path} ({push_item.category})."
            )
            return
        if item == servers.production.find_item(item):
            push_item.set_server(STATUS_OPTION_IDS.LIVE)
        elif item == servers.sandbox.find_item(item):
            push_item.set_server(STATUS_OPTION_IDS.IN_SANDBOX)
        elif item == servers.dev.find_item(item):
            push_item.set_server(STATUS_OPTION_IDS.IN_DEV)

    def run(self):
        for push_item in self.push_items:
            if any(
                [
                    push_item.status == PushStatus.LIVE,
                    not push_item.exists(),
                    push_item.url == self.skip_pr,
                ]
            ):
                continue

            if push_item.category == PushCategory.OTHER:
                log.info(
                    f"No push category defined for {push_item.path} ({push_item.url}), skipping"
                )
                continue
            if isinstance(push_item.item, (Family, FamilyMeta)):
                self.servers.update(push_item.item.name)

            self.git_checkout_item(push_item)
            self.update_server(push_item, self.servers)
            self.display_item(push_item)
            self.user_input(push_item)

    def update_servers(self):
        for push_item in self.push_items:
            if any(
                [
                    push_item.status == PushStatus.LIVE,
                    not push_item.exists(),
                    push_item.url == self.skip_pr,
                ]
            ):
                continue

            if push_item.category == PushCategory.OTHER:
                log.debug(
                    f"No push category defined for {push_item.path} ({push_item.url})"
                )
                continue
            self.update_server(push_item, self.servers)


def main(args=None):
    parser = GFArgumentParser()
    parser.add_argument("fonts_repo", type=Path)
    parser.add_argument(
        "-f",
        "--filter",
        choices=(
            None,
            "lists",
            "in_dev",
            "in_sandbox",
            "upgrade",
            "new",
            "no_fonts",
            "fonts",
        ),
        default=[],
        nargs="+",
    )
    parser.add_argument(
        "-r", "--pr-range", help="Specify a range of prs to check e.g 1000-1012"
    )
    parser.add_argument("-p", "--show-open-prs", action="store_true", default=False)
    parser.add_argument(
        "-s", "--server-data", default=(Path("~") / ".gf_server_data.json").expanduser()
    )
    parser.add_argument(
        "-l",
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        default="INFO",
    )
    parser.add_argument(
        "--update-servers-only",
        "-uso",
        action="store_true",
        help="Only update each traffic jam item's server status",
    )
    args = parser.parse_args(args)

    setup_logging("manage_traffic_jam", args, __name__)

    branch_matches_google_fonts_main(args.fonts_repo)

    if not args.server_data.exists():
        log.warning(
            f"{args.server_data} not found. Generating file. This may take a while"
        )
        servers = GFServers()
    else:
        servers = GFServers.open(args.server_data)

    if "GH_TOKEN" not in os.environ:
        log.error("GH_TOKEN not found in environment variables. Please set it.")
        sys.exit(1)

    servers.servers_online()
    servers.last_pushes()
    servers.update_all()
    servers.save(args.server_data)

    os.chdir(args.fonts_repo)

    traffic_jam_data = (Path("~") / ".gf_traffic_jam_data.json").expanduser()
    push_items = PushItems.from_traffic_jam(traffic_jam_data)
    push_items.sort(
        key=lambda x: x.category in [PushCategory.NEW, PushCategory.UPGRADE]
    )
    if not args.show_open_prs:
        push_items = PushItems(i for i in push_items if i.merged == True)
    if "lists" in args.filter:
        prod_path = args.fonts_repo / "to_production.txt"
        production_file = PushItems.from_server_file(prod_path, PushStatus.IN_SANDBOX)

        sandbox_path = args.fonts_repo / "to_sandbox.txt"
        sandbox_file = PushItems.from_server_file(sandbox_path, PushStatus.IN_DEV)

        urls = [i.url for i in production_file + sandbox_file]
        push_items = PushItems(i for i in push_items if i.url in urls)
    if "in_dev" in args.filter:
        push_items = push_items.in_dev()
    if "in_sandbox" in args.filter:
        push_items = push_items.in_sandbox()
    if "upgrade" in args.filter:
        push_items = PushItems(
            i for i in push_items if i.category == PushCategory.UPGRADE
        )
    if "new" in args.filter:
        push_items = PushItems(i for i in push_items if i.category == PushCategory.NEW)
    if "no_fonts" in args.filter:
        push_items = PushItems(
            i
            for i in push_items
            if i.category not in [PushCategory.NEW, PushCategory.UPGRADE]
        )
    if "fonts" in args.filter:
        push_items = PushItems(
            i
            for i in push_items
            if i.category in [PushCategory.NEW, PushCategory.UPGRADE]
        )
    if args.pr_range:
        pr_start, pr_end = args.pr_range.split("-")
        pr_range = range(int(pr_start), int(pr_end) + 1)
        push_items = PushItems(
            i for i in push_items if int(i.url.split("/")[-1]) in pr_range
        )

    with ItemChecker(
        push_items[::-1], args.fonts_repo, servers, args.server_data
    ) as checker:
        if args.update_servers_only:
            log.info("Updating servers")
            checker.update_servers()
        else:
            checker.run()


if __name__ == "__main__":
    main(None)
