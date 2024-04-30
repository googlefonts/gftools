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
    SampleText,
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
    DEV_LANG_URL = config["urls"]["dev_lang"]
    DEV_SAMPLE_TEXT_URL = config["urls"]["dev_sample_text"]
    SANDBOX_FAMILY_DOWNLOAD = config["urls"]["sandbox_family_download"]
    SANDBOX_META_URL = config["urls"]["sandbox_meta"]
    SANDBOX_VERSIONS_URL = config["urls"]["sandbox_versions"]
    SANDBOX_LANG_URL = config["urls"]["sandbox_lang"]
    SANDBOX_SAMPLE_TEXT_URL = config["urls"]["sandbox_sample_text"]
    PRODUCTION_META_URL = config["urls"]["production_meta"]
    PRODUCTION_VERSIONS_URL = config["urls"]["production_versions"]
    PRODUCTION_LANG_URL = config["urls"]["production_lang"]
    PRODUCTION_SAMPLE_TEXT_URL = config["urls"]["production_sample_text"]

else:
    DEV_FAMILY_DOWNLOAD = os.environ.get("DEV_FAMILY_DOWNLOAD")
    DEV_META_URL = os.environ.get("DEV_META_URL")
    DEV_VERSIONS_URL = os.environ.get("DEV_VERSIONS_URL")
    DEV_LANG_URL = os.environ.get("DEV_LANG_URL")
    DEV_SAMPLE_TEXT_URL = os.environ.get("DEV_SAMPLE_TEXT_URL")
    SANDBOX_FAMILY_DOWNLOAD = os.environ.get("SANDBOX_FAMILY_DOWNLOAD")
    SANDBOX_META_URL = os.environ.get("SANDBOX_META_URL")
    SANDBOX_VERSIONS_URL = os.environ.get("SANDBOX_VERSIONS_URL")
    SANDBOX_LANG_URL = os.environ.get("SANDBOX_LANG_URL")
    SANDBOX_SAMPLE_TEXT_URL = os.environ.get("SANDBOX_SAMPLE_TEXT_URL")
    PRODUCTION_META_URL = os.environ.get("PRODUCTION_META_URL")
    PRODUCTION_VERSIONS_URL = os.environ.get("PRODUCTION_VERSIONS_URL")
    PRODUCTION_LANG_URL = os.environ.get("PRODUCTION_LANG_URL")
    PRODUCTION_SAMPLE_TEXT_URL = os.environ.get("PRODUCTION_SAMPLE_TEXT_URL")


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


def sample_text(lang: str, url: str = PRODUCTION_SAMPLE_TEXT_URL):
    def sample(family, lang):
        resp = requests.get(url.format(family=family, lang=lang))
        if resp.status_code != 200:
            raise ValueError(
                f"Language '{lang}' is either mispelled or not supported. "
                "Also check if the endpoint still exists."
            )
        data = json.loads(resp.text[5:])
        if lang in data["sampleText"]["languages"]:
            return data["sampleText"]
        return None

    # This approach only seems to work for characters inside the Basic
    # Multi-lingual Plane. We use this approach first since Noto doesn't
    # fully cover the BMP yet and it lacks Latin African fonts.
    res = sample("Adobe+Blank", lang)
    if res:
        return res
    noto = requests.get(PRODUCTION_LANG_URL).json()
    supported_families = noto["langToNotoFamilies"].get(lang)
    if not supported_families:
        return None
    family = supported_families[0].replace(" ", "+")
    return sample(family, lang)


class GFServer(Itemer):
    def __init__(
        self,
        name: str,
        url: str = PRODUCTION_META_URL,
        dl_url: str = PROD_FAMILY_DOWNLOAD,
        version_url: str = PRODUCTION_VERSIONS_URL,
        sample_text_url: str = PRODUCTION_SAMPLE_TEXT_URL,
    ):
        self.name = name
        self.url = url
        self.dl_url = dl_url
        self.version_url = version_url
        self.sample_text_url = sample_text_url
        self.families: dict[str, Family] = {}
        self.designers: dict[str, Designer] = {}
        self.metadata: dict[str, FamilyMeta] = {}
        self.axisregistry: dict[str, Axis] = {}
        self.sample_text: dict[str, SampleText] = {}
        self.family_versions = json.loads(requests.get(self.version_url).text[5:])
        self.family_versions = {
            i["name"]: i["fontVersions"][0]["version"]
            for i in self.family_versions["familyVersions"]
        }

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
    
    def update_sample_text(self, lang: str):
        data = sample_text(lang, self.sample_text_url)
        self.sample_text[lang] = SampleText.from_gf_json(lang, data)

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
            GFServers.DEV, DEV_META_URL, DEV_FAMILY_DOWNLOAD, DEV_VERSIONS_URL, DEV_SAMPLE_TEXT_URL
        )
        self.sandbox = GFServer(
            GFServers.SANDBOX,
            SANDBOX_META_URL,
            SANDBOX_FAMILY_DOWNLOAD,
            SANDBOX_VERSIONS_URL,
            SANDBOX_SAMPLE_TEXT_URL,
        )
        self.production = GFServer(
            GFServers.PRODUCTION,
            PRODUCTION_META_URL,
            PROD_FAMILY_DOWNLOAD,
            PRODUCTION_VERSIONS_URL,
            PRODUCTION_SAMPLE_TEXT_URL
        )
        self.fp = None

    def __iter__(self):
        for server in GFServers.SERVERS:
            yield getattr(self, server)

    def update_all(self):
        for server in self:
            server.update_all(self.last_checked)
        self.last_checked = datetime.now().isoformat().split("T")[0]

    def update(self, family_name):
        for server in self:
            server.update(family_name)

    def compare_item(self, item: Items):
        res = item.to_json()
        for server in self:
            res[f"In {server.name}"] = server.compare_push_item(item)
        return res

    def save(self, fp: "str | Path"):
        from copy import deepcopy

        cp = deepcopy(self)
        # do not save family_versions data. We want to request this each time
        if hasattr(cp, "family_versions"):
            delattr(cp, "family_versions")
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
                elif item_type == "sample_text":
                    server.sample_text = {k: SampleText(**v) for k, v in item_value.items()}
                else:
                    setattr(server, item_type, item_value)
        return inst
