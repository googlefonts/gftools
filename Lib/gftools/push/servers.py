from __future__ import annotations
import json
import logging
import os
from configparser import ConfigParser
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import requests  # type: ignore
from gftools.push.items import (
    Axis,
    AxisFallback,
    Designer,
    Family,
    FamilyMeta,
    Itemer,
    Items,
)
from gftools.utils import (
    PROD_FAMILY_DOWNLOAD,
)

log = logging.getLogger("gftools.push")


# This module uses api endpoints which shouldn't be public. Ask
# Marc Foley for the .gf_push_config.ini file. Place this file in your
# home directory. Environment variables can also be used instead.
config_fp = os.path.join(os.path.expanduser("~"), ".gf_push_config.ini")
if os.path.exists(config_fp):
    config = ConfigParser()
    config.read(config_fp)
    DEV_FAMILY_DOWNLOAD = config["urls"]["dev_family_download"]
    DEV_META_URL = config["urls"]["dev_meta"]
    DEV_VERSIONS_URL = config["urls"]["dev_versions"]
    SANDBOX_FAMILY_DOWNLOAD = config["urls"]["sandbox_family_download"]
    SANDBOX_META_URL = config["urls"]["sandbox_meta"]
    SANDBOX_VERSIONS_URL = config["urls"]["sandbox_versions"]
    PRODUCTION_META_URL = config["urls"]["production_meta"]
    PRODUCTION_VERSIONS_URL = config["urls"]["production_versions"]

else:
    DEV_FAMILY_DOWNLOAD = os.environ.get("DEV_FAMILY_DOWNLOAD")
    DEV_META_URL = os.environ.get("DEV_META_URL")
    DEV_VERSIONS_URL = os.environ.get("DEV_VERSIONS_URL")
    SANDBOX_FAMILY_DOWNLOAD = os.environ.get("SANDBOX_FAMILY_DOWNLOAD")
    SANDBOX_META_URL = os.environ.get("SANDBOX_META_URL")
    SANDBOX_VERSIONS_URL = os.environ.get("SANDBOX_VERSIONS_URL")
    PRODUCTION_META_URL = os.environ.get("PRODUCTION_META_URL")
    PRODUCTION_VERSIONS_URL = os.environ.get("PRODUCTION_VERSIONS_URL")


@lru_cache
def gf_server_metadata(url: str):
    """Get family json data from a Google Fonts metadata url"""
    # can't do requests.get("url").json() since request text starts with ")]}'"
    info = requests.get(url).json()
    return {i["family"]: i for i in info["familyMetadataList"]}


@lru_cache
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
    def __init__(
        self,
        name: str,
        url: str = PRODUCTION_META_URL,
        dl_url: str = PROD_FAMILY_DOWNLOAD,
        version_url: str = PRODUCTION_VERSIONS_URL,
    ):
        self.name = name
        self.url = url
        self.dl_url = dl_url
        self.version_url = version_url
        self.families: dict[str, Family] = {}
        self.designers: dict[str, Designer] = {}
        self.metadata: dict[str, FamilyMeta] = {}
        self.axisregistry: dict[str, Axis] = {}
        self.family_versions_data = json.loads(requests.get(self.version_url).text[5:])
        self.family_versions = {
            i["name"]: i["fontVersions"][0]["version"]
            for i in self.family_versions_data["familyVersions"]
        }

    def is_online(self):
        req = requests.head(self.url)
        if req.status_code == 200:
            return True
        return False

    @property
    def last_push(self):
        return datetime.fromtimestamp(
            self.family_versions_data["lastUpdate"]["seconds"]
        )

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
        family_version = self.family_versions.get(name)
        if family_version:
            self.families[name] = Family(name, family_version)
            return True
        else:
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

    def update_all(self, last_checked: str):
        meta = requests.get(self.url).json()
        self.update_axis_registry(meta["axisRegistry"])

        families_data = meta["familyMetadataList"]
        for family_data in families_data:
            family_name = family_data["family"]
            # I beleive this is a test family so we'll skip it for now
            if family_name == "Roboto_old":
                continue
            last_modified = family_data["lastModified"]

            cached_family_version = self.family_versions.get(family_name)
            existing_family_version = self.families.get(family_name)
            # always ensure we repull family data if the family_version api
            # is different
            if cached_family_version and existing_family_version:
                if cached_family_version != existing_family_version.version:
                    self.update(family_name)
            elif last_modified >= last_checked:
                self.update(family_name)

    def update(self, family_name):
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
        self.dev = GFServer(
            GFServers.DEV, DEV_META_URL, DEV_FAMILY_DOWNLOAD, DEV_VERSIONS_URL
        )
        self.sandbox = GFServer(
            GFServers.SANDBOX,
            SANDBOX_META_URL,
            SANDBOX_FAMILY_DOWNLOAD,
            SANDBOX_VERSIONS_URL,
        )
        self.production = GFServer(
            GFServers.PRODUCTION,
            PRODUCTION_META_URL,
            PROD_FAMILY_DOWNLOAD,
            PRODUCTION_VERSIONS_URL,
        )
        self.fp = None

    def last_pushes(self):
        log.info(
            "Last pushes for each server:\n"
            f"Dev: {self.dev.last_push}\n"
            f"Sandbox: {self.sandbox.last_push}\n"
            f"Production: {self.production.last_push}\n"
        )

    def servers_online(self):
        for server in self:
            is_online = server.is_online()
            if not is_online:
                raise ValueError(f"Server {server.name} is offline")

    def __iter__(self):
        for server in GFServers.SERVERS:
            yield getattr(self, server)

    def update_all(self):
        for server in self:
            server.update_all(self.last_checked)
        self.last_checked = datetime.now().isoformat().split("T")[0]

    def update(self, family_name):
        for server in self:
            try:
                server.update(family_name)
            except Exception as e:
                log.error(f"Error updating {family_name} on {server.name}: {e}")

    def compare_item(self, item: Items):
        res = item.to_json()
        for server in self:
            res[f"In {server.name}"] = server.compare_push_item(item)
        return res

    def save(self, fp: "str | Path"):
        from copy import deepcopy

        cp = deepcopy(self)
        # do not save family_versions data. We want to request this each time
        for attr in ["family_versions", "family_versions_data"]:
            for server_name in ["dev", "sandbox", "production"]:
                server = getattr(cp, server_name)
                if hasattr(server, attr):
                    delattr(server, attr)
        data = cp.to_json()
        json.dump(data, open(fp, "w", encoding="utf8"), indent=4)

    @classmethod
    def open(cls, fp: "str | Path"):
        data = json.load(open(fp, encoding="utf8"))
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data):
        inst = cls()
        inst.last_checked = data["last_checked"]
        for server_name in GFServers.SERVERS:
            server = getattr(inst, server_name)

            for item_type, item_value in data[server_name].items():
                # if family_versions data is saved, skip it so we get requested
                # data instead
                if item_type in ["family_versions", "traffic_jam"]:
                    continue
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
                    for k, v in server.axisregistry.items():
                        server.axisregistry[k].fallback = [
                            AxisFallback(**a) for a in v.fallback
                        ]
                else:
                    setattr(server, item_type, item_value)
        return inst
