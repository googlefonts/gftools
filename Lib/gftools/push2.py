from pathlib import Path
from dataclasses import dataclass
import os
from gftools.utils import read_proto
import gftools.fonts_public_pb2 as fonts_pb2
import requests


CATEGORIES = (
    "New",
    "Upgrade",
    "Other",
    "Designer profile",
    "Axis Registry",
    "Knowledge",
    "Metadata / Description / License",
    "Sample texts"
)


FAMILY_FILE_SUFFIXES = frozenset([".ttf", ".otf", ".html", ".pb", ".txt"])


GOOGLE_FONTS_TRAFFIC_JAM_QUERY = """
{
  organization(login: "google") {
    projectV2(number: 74) {
      id
      title
      items(last: 40) {
        nodes {
          id
          status: fieldValueByName(name: "Status") {
            ... on ProjectV2ItemFieldSingleSelectValue {
              name
            }
          }
          type
          content {
            ... on PullRequest {
              id
              files(first: 10) {
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
    type: str
    status: str
    url: str

    def __hash__(self):
        return hash((self.path, self.type, self.status, self.url))
    
    def exists(self):
        return self.path.exists
    
    def is_family(self):
        return any(t for t in ("ofl", "apache", "ufl") if t in self.path.parts if "article" not in str(self.path))

    def family_name(self):
        assert self.is_family()
        metadata_file = self.path / "METADATA.pb"
        assert metadata_file.exists(), f"no metadata for {self.path}"
        return read_proto(metadata_file, fonts_pb2.FamilyProto()).name


class PushItems(list):

    def add(self, item):
        """..."""
        # noto font projects projects often contain an article/ dir, we remove this
        if "article" in item.path.parts:
            item.path = item.path.parent
        
        # for font families, we only want the dir e.g ofl/mavenpro/MavenPro[wght].ttf --> ofl/mavenpro
        elif any(d in item.path.parts for d in ("ofl", "ufl", "apache")) \
          and item.path.suffix in FAMILY_FILE_SUFFIXES:
            item.path = item.path.parent

        # for lang and axisregistry .textproto files, we need a transformed path
        elif any(d in item.path.parts for d in ("lang", "axisregistry")) \
          and item.path.suffix == ".textproto":
            item.path = repo_path_to_google_path(item.path)
        
        # don't include any axisreg or lang file which don't end in textproto
        elif any(d in item.path.parts for d in ("lang", "axisregistry")) \
          and item.path.suffix != ".textproto":
            return
        
        # Skip if path if it's a parent dir e.g ofl/ apache/ axisregistry/
        if len(item.path.parts) == 1:
            return

        # Skip if path is a parent of an existing path
        if any(str(item.path) in str(p.path) for p in self):
            return
        
        # Pop any push items which are a child of the item's path
        to_pop = None
        for idx, i in enumerate(self):
            if str(i.path) in str(item.path):
                to_pop = idx
                break
        if to_pop:
            self.pop(to_pop)
        self.append(item)
    
    def missing_paths(self):
        res = []
        for item in self:
            path = item.path
            if any(p in ("lang", "axisregistry") for p in path.parts):
                path = google_path_to_repo_path(path)
            if not path.exists():
                res.append(path)
        return res

    def to_server_file(self, fp):
        from collections import defaultdict
        bins = defaultdict(set)
        for item in self:
            bins[item.type].add(item)
        
        res = []
        for tag in CATEGORIES:
            if tag not in bins:
                continue
            res.append(f"# {tag}")
            for item in sorted(bins[tag], key=lambda k: k.path):
                res.append(f"{item.path} # {item.url}")
            res.append("")
        if isinstance(fp, str):
            doc = open(fp, "w")
        else:
            doc = fp
        doc.write("\n".join(res))
    
    @classmethod
    def from_server_file(cls, fp, status):
        if isinstance(fp, (str, Path)):
            doc = open(fp)
        else:
            doc = fp
        results = cls()

        lines = doc.read().split("\n")
        category = "Unknown"
        for line in lines:
            if not line:
                continue
            if line.startswith("#"):
                category = line[1:].strip()
            elif "#" in line:
                path, url = line.split("#")
                item = PushItem(Path(path.strip()), category, status, url.strip())
                results.add(item)
            # some paths may not contain a PR, still add them
            else:
                item = PushItem(Path(line.strip()), category, status, "")
                results.add(item)
        return results
    
    @classmethod
    def from_traffic_jam(cls):
        from gftools.gfgithub import GitHubClient
        g = GitHubClient("google", "fonts")
        data = g._run_graphql(GOOGLE_FONTS_TRAFFIC_JAM_QUERY, {})

        board_items = data["data"]["organization"]["projectV2"]["items"]["nodes"]
        results = cls()
        for item in board_items:
            status = item.get("status", {}).get("name", None)

            if "labels" not in item["content"]:
                print("PR missing labels. Skipping")
            labels = [i["name"] for i in item["content"]["labels"]["nodes"]]
            
            files = [Path(i["path"]) for i in item["content"]["files"]["nodes"]] 
            url = item["content"]["url"]

            # get pr state
            if "-- blocked" in labels:
                cat = "Blocked"
            if "I Font Upgrade" in labels or "I Small Fix" in labels:
                cat = "Upgrade"
            elif "I New Font" in labels:
                cat = "New"
            elif "I Description/Metadata/OFL" in labels:
                cat = "Metadata / Description / License"
            elif "I Designer profile" in labels:
                cat = "Designer profile"
            elif "I Knowledge" in labels:
                cat = "Knowledge"
            elif "I Axis Registry" in labels:
                cat = "Axis Registry"
            elif "I Lang" in labels:
                cat = "Sample texts"
            else:
                cat = "Other"

            for f in files:
                results.add(
                    PushItem(Path(f), cat, status, url)
                )
        return results


# The internal Google fonts team store the axisregistry and lang directories
# in a different location. The two functions below tranform paths to
# whichever representation you need.
def repo_path_to_google_path(fp):
    """lang/Lib/gflanguages/data/languages/.*.textproto --> lang/languages/.*.textproto"""
    # we rename lang paths due to: https://github.com/google/fonts/pull/4679
    if "gflanguages" in fp.parts:
        return Path("lang") / fp.relative_to("lang/Lib/gflanguages/data")
    # https://github.com/google/fonts/pull/5147
    elif "axisregistry" in fp.parts:
        return Path("axisregistry") / fp.name
    return fp


def google_path_to_repo_path(fp):
    """lang/languages/.*.textproto --> lang/Lib/gflanguages/data/languages/.*.textproto"""
    if "lang" in fp.parts:
        return Path("lang/Lib/gflanguages/data/") / fp.relative_to("lang")
    elif "axisregistry" in fp.parts:
        return fp.parent / "Lib" / "axisregistry" / "data" / fp.name
    return fp


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


def gf_server_metadata(url):
    """Get family json data from a Google Fonts metadata url"""
    # can't do requests.get("url").json() since request text starts with ")]}'"
    info = requests.get(url).json()
    return {i["family"]: i for i in info["familyMetadataList"]}


def server_push_status(fp, url):
    family_names = [i.family_name() for i in PushItems.from_server_file(fp, "") if i.is_family()]

    gf_meta = gf_server_metadata(url)

    new_families = [f for f in family_names if f not in gf_meta]
    existing_families = [f for f in family_names if f in gf_meta]

    gf_families = sorted(
        [gf_meta[f] for f in existing_families], key=lambda k: k["lastModified"]
    )
    existing_families = [f"{f['family']}: {f['lastModified']}" for f in gf_families]
    return new_families, existing_families


def server_push_report(name, fp, server_url):
    new_families, existing_families = server_push_status(fp, server_url)
    new = "\n".join(new_families) if new_families else "N/A"
    existing = "\n".join(existing_families) if existing_families else "N/A"
    print(PUSH_STATUS_TEMPLATE.format(name, new, existing))


def push_report(fp):
    prod_path = fp / "to_production.txt"
    server_push_report("Production", prod_path, PRODUCTION_URL)

    sandbox_path = fp / "to_sandbox.txt"
    server_push_report("Sandbox", sandbox_path, SANDBOX_URL)