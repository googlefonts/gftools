import json
import logging
import os
from configparser import ConfigParser
from datetime import datetime
from functools import cache
from pathlib import Path

import requests # type: ignore
from gftools.push.items import Axis, AxisFallback, Designer, Family, FamilyMeta, Itemer, Items
from gftools.utils import (
    PROD_FAMILY_DOWNLOAD,
)

log = logging.getLogger("gftools.servers")



# This module uses api endpoints which shouldn't be public. Ask
# Marc Foley for the .gf_push_config.ini file. Place this file in your
# home directory. Environment variables can also be used instead.
config = ConfigParser()
config.read(os.path.join(os.path.expanduser("~"), ".gf_push_config.ini"))

SANDBOX_META_URL = os.environ.get("SANDBOX_META_URL") or config["urls"]["sandbox_meta"]
PRODUCTION_META_URL = (
    os.environ.get("PRODUCTION_META_URL") or config["urls"]["production_meta"]
)
DEV_META_URL = os.environ.get("DEV_META_URL") or config["urls"]["dev_meta"]
SANDBOX_FAMILY_DOWNLOAD = (
    os.environ.get("SANDBOX_FAMILY_DOWNLOAD")
    or config["urls"]["sandbox_family_download"]
)
DEV_FAMILY_DOWNLOAD = (
    os.environ.get("DEV_FAMILY_DOWNLOAD") or config["urls"]["dev_family_download"]
)


@cache
def gf_server_metadata(url: str):
    """Get family json data from a Google Fonts metadata url"""
    # can't do requests.get("url").json() since request text starts with ")]}'"
    info = requests.get(url).json()

    return {i["family"]: i for i in info["familyMetadataList"]}


@cache
def gf_server_family_metadata(url: str, family: str):
    """Get metadata for family on a server"""
    # can't do requests.get("url").json() since request text starts with ")]}'"
    url = url + f"/{family.replace(' ', '%20')}"
    r = requests.get(url)
    if r.status_code != 200:
        return None
    text = r.text
    info = json.loads(text[4:])
    return info


class GFServer(Itemer):
    def __init__(self, name: str, url: str=PRODUCTION_META_URL, dl_url: str=PROD_FAMILY_DOWNLOAD):
        self.name = name
        self.url = url
        self.dl_url = dl_url
        self.families: dict[str, Family] = {}
        self.designers: dict[str, Designer] = {}
        self.metadata: dict[str, FamilyMeta] = {}
        self.axisregistry: dict[str, Axis] = {}

    def compare_push_item(self, item: Items):
        server_item = self.find_item(item)
        return server_item == item

    def find_item(self, item):
        if isinstance(item, Family):
            server_item = self.families.get(item.name)
        elif isinstance(item, Designer):
            server_item = self.designers.get(item.name)
        elif isinstance(item, Axis):
            server_item = self.axisregistry.get(item.tag)
        elif isinstance(item, FamilyMeta):
            server_item = self.metadata.get(item.name)
        else:
            return None
        return server_item

    def update_axis_registry(self, axis_data):
        for axis in axis_data:
            self.axisregistry[axis["tag"]] = Axis.from_gf_json(axis)

    def update_family(self, name: str):
        family = Family.from_gf(name, dl_url=self.dl_url)
        if family:
            self.families[name] = family
            return True
        return False

    def update_family_designers(self, name: str):
        meta = gf_server_family_metadata(self.url, name)
        for designer in meta["designers"]:
            self.designers[designer["name"]] = Designer.from_gf_json(designer)

    def update_metadata(self, name: str):
        meta = gf_server_family_metadata(self.url, name)
        self.metadata[meta["family"]] = FamilyMeta.from_gf_json(meta)

    def update(self, last_checked: str):
        meta = requests.get(self.url).json()
        self.update_axis_registry(meta["axisRegistry"])

        families_data = meta["familyMetadataList"]
        for family_data in families_data:
            family_name = family_data["family"]
            last_modified = family_data["lastModified"]
            if last_modified > last_checked:
                log.info(f"Updating {family_name}")
                if self.update_family(family_name):
                    self.update_family_designers(family_name)
                    self.update_metadata(family_name)


class GFServers(Itemer):

    DEV = "dev"
    SANDBOX = "sandbox"
    PRODUCTION = "production"
    SERVERS = (DEV, SANDBOX, PRODUCTION)

    def __init__(self):
        self.last_checked = datetime.fromordinal(1).isoformat().split("T")[0]
        self.dev = GFServer(GFServers.DEV, DEV_META_URL, DEV_FAMILY_DOWNLOAD)
        self.sandbox = GFServer(GFServers.SANDBOX, SANDBOX_META_URL, SANDBOX_FAMILY_DOWNLOAD)
        self.production = GFServer(
            GFServers.PRODUCTION, PRODUCTION_META_URL, PROD_FAMILY_DOWNLOAD
        )

    def __iter__(self):
        for server in GFServers.SERVERS:
            yield getattr(self, server)

    def update(self):
        for server in self:
            server.update(self.last_checked)
        self.last_checked = datetime.now().isoformat().split("T")[0]

    def compare_item(self, item: Items):
        res = item.to_json()
        for server in self:
            res[f"In {server.name}"] = server.compare_push_item(item)
        return res

    def save(self, fp: str | Path):
        data = self.to_json()
        json.dump(data, open(fp, "w"), indent=4)

    @classmethod
    def open(cls, fp: str | Path):
        data = json.load(open(fp))
        return cls.from_dict(data)
    
    @classmethod
    def from_dict(cls, data):
        inst = cls()
        inst.last_checked = data["last_checked"]
        for server_name in GFServers.SERVERS:
            server = getattr(inst, server_name)

            for item_type, item_value in data[server_name].items():
                if item_type == "families":
                    server.families = {k: Family(**v) for k, v in item_value.items()}
                elif item_type == "designers":
                    server.designers = {k: Designer(**v) for k, v in item_value.items()}
                elif item_type == "metadata":
                    server.metadata = {
                        k: FamilyMeta(**v) for k, v in item_value.items()
                    }
                elif item_type == "axisregistry":
                    server.axisregistry = {k: Axis(**v) for k, v in item_value.items()}
                    for _, v in server.axisregistry.items():
                        v.fallback = [AxisFallback(**a) for a in v.fallback]
                else:
                    setattr(server, item_type, item_value)
        return inst
