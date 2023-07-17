from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass
import os
from gftools.utils import read_proto
import gftools.fonts_public_pb2 as fonts_pb2
import requests  # type: ignore[import]
from enum import Enum
from io import TextIOWrapper
import pygit2
import subprocess


def _get_google_fonts_remote(repo):
    for remote in repo.remotes:
        if "google/fonts.git" in remote.url:
            return remote.name
    raise ValueError("Cannot find remote with url https://www.github.com/google/fonts")


def branch_matches_google_fonts_main(path):
    repo = pygit2.Repository(path)
    remote_name = _get_google_fonts_remote(repo)

    # fetch latest remote data from branch main
    subprocess.run(["git", "fetch", remote_name, "main"])

    # Check local is in sync with remote
    diff = repo.diff(repo.head, f"{remote_name}/main")
    if diff.stats.files_changed != 0:
        raise ValueError(
            "Your local branch is not in sync with the google/fonts "
            "main branch. Please pull or remove any commits."
        )
    return True


class PushCategory(Enum):
    NEW = "New"
    UPGRADE = "Upgrade"
    OTHER = "Other"
    DESIGNER_PROFILE = "Designer profile"
    AXIS_REGISTRY = "Axis Registry"
    KNOWLEDGE = "Knowledge"
    METADATA = "Metadata / Description / License"
    SAMPLE_TEXTS = "Sample texts"
    BLOCKED = "Blocked"
    DELETED = "Deleted"

    def values():  # type: ignore[misc]
        return [i.value for i in PushCategory]

    def from_string(string: str):  # type: ignore[misc]
        return next((i for i in PushCategory if i.value == string), None)


class PushStatus(Enum):
    PR_GF = "PR GF"
    IN_DEV = "In Dev / PR Merged"
    IN_SANDBOX = "In Sandbox"
    LIVE = "Live"

    def from_string(string: str):  # type: ignore[misc]
        return next((i for i in PushStatus if i.value == string), None)


class PushList(Enum):
    TO_SANDBOX = "to_sandbox"
    TO_PRODUCTION = "to_production"
    BLOCKED = "blocked"

    def from_string(string: str):  # type: ignore[misc]
        return next((i for i in PushList if i.value == string), None)


FAMILY_FILE_SUFFIXES = frozenset(
    [".ttf", ".otf", ".html", ".pb", ".txt", ".yaml", ".png"]
)


GOOGLE_FONTS_TRAFFIC_JAM_QUERY = """
{
  organization(login: "google") {
    projectV2(number: 74) {
      id
      title
      items(first: 100, after: "%s") {
        totalCount
        edges {
          cursor
        }
        nodes {
          id
          status: fieldValueByName(name: "Status") {
            ... on ProjectV2ItemFieldSingleSelectValue {
              name
            }
          }
          list: fieldValueByName(name: "List") {
            ... on ProjectV2ItemFieldSingleSelectValue {
              name
            }
          }
          type
          content {
            ... on PullRequest {
              id
              files(first: 100) {
                nodes {
                  path
                }
              }
              url
              labels(first: 10) {
                nodes {
                  name
                }
              }
            }
          }
        }
      }
    }
  }
}
"""


@dataclass
class PushItem:
    path: Path
    category: PushCategory
    status: PushStatus
    url: str
    push_list: PushList = None

    def __hash__(self) -> int:
        return hash(self.path)

    def __eq__(self, other):
        return self.path == other.path

    def exists(self) -> bool:
        path = google_path_to_repo_path(self.path)
        return path.exists()

    def is_family(self) -> bool:
        return any(
            t
            for t in ("ofl", "apache", "ufl")
            if t in self.path.parts
            if "article" not in str(self.path)
        )

    def family_name(self) -> str:
        assert self.is_family()
        metadata_file = self.path / "METADATA.pb"
        assert metadata_file.exists(), f"no metadata for {self.path}"
        return read_proto(metadata_file, fonts_pb2.FamilyProto()).name

    def to_json(self) -> dict[str, str]:
        category = None if not self.category else self.category.value
        status = None if not self.status else self.status.value
        url = None if not self.url else self.url
        return {
            "path": str(self.path.as_posix()),
            "category": category,
            "status": status,
            "url": url,
        }


class PushItems(list):
    def __add__(self, other):
        from copy import deepcopy

        new = deepcopy(self)
        for i in other:
            new.add(i)
        return new

    def __sub__(self, other):
        subbed = [i for i in self if i not in other]
        new = PushItems()
        for i in subbed:
            new.add(i)
        return new

    def to_sandbox(self):
        return PushItems([i for i in self if i.push_list == PushList.TO_SANDBOX])

    def to_production(self):
        return PushItems([i for i in self if i.push_list == PushList.TO_PRODUCTION])

    def live(self):
        return PushItems([i for i in self if i.status == PushStatus.LIVE])

    def add(self, item: PushItem):
        # noto font projects projects often contain an article/ dir, we remove this.
        # Same for legacy VF projects which may have a static/ dir.
        if "article" in item.path.parts or "static" in item.path.parts:
            if item.path.is_dir():
                item.path = item.path.parent
            else:
                item.path = item.path.parent.parent

        # for font families, we only want the dir e.g ofl/mavenpro/MavenPro[wght].ttf --> ofl/mavenpro
        elif (
            any(d in item.path.parts for d in ("ofl", "ufl", "apache", "designers"))
            and item.path.suffix in FAMILY_FILE_SUFFIXES
        ):
            item.path = item.path.parent

        # for lang and axisregistry .textproto files, we need a transformed path
        elif (
            any(d in item.path.parts for d in ("lang", "axisregistry"))
            and item.path.suffix == ".textproto"
        ):
            item.path = repo_path_to_google_path(item.path)

        # don't include any axisreg or lang file which don't end in textproto
        elif (
            any(d in item.path.parts for d in ("lang", "axisregistry"))
            and item.path.suffix != ".textproto"
        ):
            return

        # Skip if path if it's a parent dir e.g ofl/ apache/ axisregistry/
        if len(item.path.parts) == 1:
            return

        # Pop any existing item which has the same path. We always want the latest
        existing_idx = next(
            (idx for idx, i in enumerate(self) if i.path == item.path), None
        )
        if existing_idx != None:
            self.pop(existing_idx)

        # Pop any push items which are a child of the item's path
        to_pop = None
        for idx, i in enumerate(self):
            if str(i.path.parent) in str(i.path) or i.path == item.path:
                to_pop = idx
                break
        if to_pop:
            self.pop(to_pop)

        self.append(item)

    def missing_paths(self) -> list[Path]:
        res = []
        for item in self:
            if item.category == PushCategory.DELETED:
                continue
            path = item.path
            if any(p in ("lang", "axisregistry") for p in path.parts):
                path = google_path_to_repo_path(path)
            if not path.exists():
                res.append(path)
        return res

    def to_server_file(self, fp: str | Path):
        from collections import defaultdict

        bins = defaultdict(set)
        for item in self:
            if item.category == PushCategory.BLOCKED:
                continue
            bins[item.category.value].add(item)

        res = []
        for tag in PushCategory.values():
            if tag not in bins:
                continue
            res.append(f"# {tag}")
            for item in sorted(bins[tag], key=lambda k: k.path):
                if item.exists():
                    res.append(f"{item.path.as_posix()} # {item.url}")
                else:
                    if item.url:
                        res.append(f"# Deleted: {item.path.as_posix()} # {item.url}")
                    else:
                        res.append(f"# Deleted: {item.path.as_posix()}")
            res.append("")
        if isinstance(fp, str):
            doc: TextIOWrapper = open(fp, "w")
        else:
            doc: TextIOWrapper = fp  # type: ignore[no-redef]
        doc.write("\n".join(res))

    @classmethod
    def from_server_file(
        cls,
        fp: str | Path | TextIOWrapper,
        status: PushStatus = None,
        push_list: PushList = None,
    ):
        if isinstance(fp, (str, Path)):
            doc = open(fp)
        else:
            doc = fp
        results = cls()

        lines = doc.read().split("\n")
        category = PushCategory.OTHER
        deleted = False
        for line in lines:
            if not line:
                continue

            if line.startswith("# Deleted"):
                line = line.replace("# Deleted: ", "")
                deleted = True

            if line.startswith("#"):
                category = PushCategory.from_string(line[1:].strip())

            elif "#" in line:
                path, url = line.split("#")
                item = PushItem(
                    Path(path.strip()),
                    category if not deleted else PushCategory.DELETED,
                    status,
                    url.strip(),
                    push_list,
                )
                results.add(item)
            # some paths may not contain a PR, still add them
            else:
                item = PushItem(
                    Path(line.strip()),
                    category if not deleted else PushCategory.DELETED,
                    status,
                    "",
                    push_list,
                )
                results.add(item)
            deleted = False
        return results

    @classmethod
    def from_traffic_jam(cls):
        from gftools.gfgithub import GitHubClient

        g = GitHubClient("google", "fonts")
        last_item = ""
        data = g._run_graphql(GOOGLE_FONTS_TRAFFIC_JAM_QUERY % last_item, {})
        board_items = data["data"]["organization"]["projectV2"]["items"]["nodes"]

        # paginate through items in board
        last_item = data["data"]["organization"]["projectV2"]["items"]["edges"][-1][
            "cursor"
        ]
        item_count = data["data"]["organization"]["projectV2"]["items"]["totalCount"]
        while len(board_items) < item_count:
            data = g._run_graphql(GOOGLE_FONTS_TRAFFIC_JAM_QUERY % last_item, {})
            board_items += data["data"]["organization"]["projectV2"]["items"]["nodes"]
            last_item = data["data"]["organization"]["projectV2"]["items"]["edges"][-1][
                "cursor"
            ]
        # sort items by pr number
        board_items.sort(key=lambda k: k["content"]["url"])

        results = cls()
        for item in board_items:
            status = item.get("status", {}).get("name", None)
            if status:
                status = PushStatus.from_string(status)

            push_list = item.get("list", None)
            if push_list:
                push_list = PushList.from_string(push_list.get("name", None))

            if "labels" not in item["content"]:
                print("PR missing labels. Skipping")
                continue
            labels = [i["name"] for i in item["content"]["labels"]["nodes"]]

            files = [Path(i["path"]) for i in item["content"]["files"]["nodes"]]
            url = item["content"]["url"]

            # get category
            if "--- blocked" in labels:
                cat = PushCategory.BLOCKED
            elif "I Font Upgrade" in labels or "I Small Fix" in labels:
                cat = PushCategory.UPGRADE
            elif "I New Font" in labels:
                cat = PushCategory.NEW
            elif "I Description/Metadata/OFL" in labels:
                cat = PushCategory.METADATA
            elif "I Designer profile" in labels:
                cat = PushCategory.DESIGNER_PROFILE
            elif "I Knowledge" in labels:
                cat = PushCategory.KNOWLEDGE
            elif "I Axis Registry" in labels:
                cat = PushCategory.AXIS_REGISTRY
            elif "I Lang" in labels:
                cat = PushCategory.SAMPLE_TEXTS
            else:
                cat = PushCategory.OTHER

            for f in files:
                results.add(PushItem(Path(f), cat, status, url, push_list))
        return results


# The internal Google fonts team store the axisregistry and lang directories
# in a different location. The two functions below tranform paths to
# whichever representation you need.
def repo_path_to_google_path(fp: Path):
    """lang/Lib/gflanguages/data/languages/.*.textproto --> lang/languages/.*.textproto"""
    # we rename lang paths due to: https://github.com/google/fonts/pull/4679
    if "gflanguages" in fp.parts:
        return Path("lang") / fp.relative_to("lang/Lib/gflanguages/data")
    # https://github.com/google/fonts/pull/5147
    elif "axisregistry" in fp.parts:
        return Path("axisregistry") / fp.name
    return fp


def google_path_to_repo_path(fp: Path) -> Path:
    """lang/languages/.*.textproto --> lang/Lib/gflanguages/data/languages/.*.textproto"""
    if "lang" in fp.parts:
        return Path("lang/Lib/gflanguages/data/") / fp.relative_to("lang")
    elif "axisregistry" in fp.parts:
        return fp.parent / "Lib" / "axisregistry" / "data" / fp.name
    return fp


def lint_server_files(fp: Path):
    template = "{}: Following paths are not valid:\n{}\n\n"
    footnote = (
        "lang and axisregistry dir paths need to be transformed.\n"
        "See https://github.com/googlefonts/gftools/issues/603"
    )

    prod_path = fp / "to_production.txt"
    production_file = PushItems.from_server_file(prod_path, PushStatus.IN_SANDBOX)
    prod_missing = "\n".join(map(str, production_file.missing_paths()))
    prod_msg = template.format("to_production.txt", prod_missing)

    sandbox_path = fp / "to_sandbox.txt"
    sandbox_file = PushItems.from_server_file(sandbox_path, PushStatus.IN_DEV)
    sandbox_missing = "\n".join(map(str, sandbox_file.missing_paths()))
    sandbox_msg = template.format("to_sandbox.txt", sandbox_missing)

    if prod_missing and sandbox_missing:
        raise ValueError(prod_msg + sandbox_msg + footnote)
    elif prod_missing:
        raise ValueError(prod_msg + footnote)
    elif sandbox_missing:
        raise ValueError(sandbox_msg + footnote)
    else:
        print("Server files have valid paths")


# TODO refactor below server code once backend team have implemented a
# tracking field to help us track prs through the servers


SANDBOX_URL = "https://fonts.sandbox.google.com/metadata/fonts"
PRODUCTION_URL = "https://fonts.google.com/metadata/fonts"

PUSH_STATUS_TEMPLATE = """
***{} Status***
New families:
{}

Existing families, last pushed:
{}
"""


def gf_server_metadata(url: str):
    """Get family json data from a Google Fonts metadata url"""
    # can't do requests.get("url").json() since request text starts with ")]}'"
    info = requests.get(url).json()
    return {i["family"]: i for i in info["familyMetadataList"]}


def server_push_status(fp: Path, url: str):
    family_names = [
        i.family_name()
        for i in PushItems.from_server_file(fp, None, None)
        if i.is_family()
    ]

    gf_meta = gf_server_metadata(url)

    new_families = [f for f in family_names if f not in gf_meta]
    existing_families = [f for f in family_names if f in gf_meta]

    gf_families = sorted(
        [gf_meta[f] for f in existing_families], key=lambda k: k["lastModified"]
    )
    existing_families = [f"{f['family']}: {f['lastModified']}" for f in gf_families]
    return new_families, existing_families


def server_push_report(name: str, fp: Path, server_url: str):
    new_families, existing_families = server_push_status(fp, server_url)
    new = "\n".join(new_families) if new_families else "N/A"
    existing = "\n".join(existing_families) if existing_families else "N/A"
    print(PUSH_STATUS_TEMPLATE.format(name, new, existing))


def push_report(fp: Path):
    prod_path = fp / "to_production.txt"
    server_push_report("Production", prod_path, PRODUCTION_URL)

    sandbox_path = fp / "to_sandbox.txt"
    server_push_report("Sandbox", sandbox_path, SANDBOX_URL)
