"""Helper functions for creating/checking the server push files."""
import requests
from pathlib import Path
from dataclasses import dataclass
from gftools.utils import read_proto
import gftools.fonts_public_pb2 as fonts_pb2


SANDBOX_URL = "https://fonts.sandbox.google.com/metadata/fonts"
PRODUCTION_URL = "https://fonts.google.com/metadata/fonts"

PUSH_STATUS_TEMPLATE = """
***{} Status***
New families:
{}

Existing families, last pushed:
{}
"""


@dataclass
class PushItem:
    path: Path
    type: str

    def to_json(self):
        return {"path": str(self.path), "type": self.type}


def parse_server_file(fp):
    results = []
    with open(fp) as doc:
        lines = doc.read().split("\n")
        category = "Unknown"
        for line in lines:
            if not line:
                continue
            if line.startswith("#"):
                category = line[1:].strip()
            elif "#" in line:
                line = line.split("#")[0].strip()
            else:
                item = PushItem(Path(line), category)
                results.append(item)
    return results


def is_family_dir(path):
    return any(t for t in ("ofl", "apache", "ufl") if t in path.parts)


def family_dir_name(path):
    metadata_file = path / "METADATA.pb"
    assert metadata_file.exists()
    return read_proto(metadata_file, fonts_pb2.FamilyProto()).name


def gf_server_metadata(url):
    """Get family json data from a Google Fonts metadata url"""
    # can't do requests.get("url").json() since request text starts with ")]}'"
    info = requests.get(url).json()
    return {i["family"]: i for i in info["familyMetadataList"]}


def server_push_status(fp, url):
    dirs = [fp.parent / p.path for p in parse_server_file(fp)]
    family_dirs = [d for d in dirs if is_family_dir(d)]
    family_names = [family_dir_name(d) for d in family_dirs]

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


def missing_paths(fp):
    paths = [fp.parent / p.path for p in parse_server_file(fp)]
    axis_files = [p for p in paths if p.name.endswith("textproto")]
    dirs = [p for p in paths if p not in axis_files]

    missing_dirs = [p for p in dirs if not p.is_dir()]
    missing_axis_files = [p for p in axis_files if not p.is_file()]
    return missing_dirs + missing_axis_files


def lint_server_files(fp):
    template = "{}: Following paths are not valid:\n{}\n\n"
    prod_path = fp / "to_production.txt"
    prod_missing = "\n".join(map(str, missing_paths(prod_path)))
    prod_msg = template.format("to_production.txt", prod_missing)

    sandbox_path = fp / "to_sandbox.txt"
    sandbox_missing = "\n".join(map(str, missing_paths(sandbox_path)))
    sandbox_msg = template.format("to_sandbox.txt", sandbox_missing)

    if prod_missing and sandbox_missing:
        raise ValueError(prod_msg + sandbox_msg)
    elif prod_missing:
        raise ValueError(prod_msg)
    elif sandbox_missing:
        raise ValueError(sandbox_msg)
    else:
        print("Server files have valid paths")
