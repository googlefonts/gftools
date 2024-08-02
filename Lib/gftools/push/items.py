from __future__ import annotations
import logging
from abc import ABC
from dataclasses import dataclass

from fontTools.ttLib import TTFont, TTLibError  # type: ignore
from gftools.designers_pb2 import DesignerInfoProto
from gftools.fonts_public_pb2 import FamilyProto
from gftools.push.utils import google_path_to_repo_path
from gftools.util.google_fonts import ReadProto
from gftools.utils import (
    font_version,
    download_family_from_Google_Fonts,
    PROD_FAMILY_DOWNLOAD,
)
import zipfile
from bs4 import BeautifulSoup  # type: ignore
from pathlib import Path
from axisregistry.axes_pb2 import AxisProto
from google.protobuf.json_format import MessageToDict  # type: ignore
from typing import Optional
import re


log = logging.getLogger("gftools.push")


def jsonify(item):
    if item == None:
        return item
    if isinstance(item, (bool, int, float, str)):
        return item
    elif isinstance(item, dict):
        return {k: jsonify(v) for k, v in item.items()}
    elif isinstance(item, (tuple, list)):
        return [jsonify(i) for i in item]
    if hasattr(item, "to_json"):
        return item.to_json()
    return item


class Itemer(ABC):
    def to_json(self):
        return jsonify(self.__dict__)


@dataclass
class Family(Itemer):
    name: str
    version: str

    @classmethod
    def from_ttfont(cls, fp: "str | Path"):
        ttFont = TTFont(fp)
        name = ttFont["name"].getBestFamilyName()
        version = font_version(ttFont)
        return cls(name, version)

    @classmethod
    def from_fp(cls, fp: "str | Path"):
        ttf = list(fp.glob("*.ttf"))[0]  # type: ignore
        return cls.from_ttfont(ttf)

    @classmethod
    def from_gf_json(cls, data, dl_url: str = PROD_FAMILY_DOWNLOAD):
        return cls.from_gf(data["family"], dl_url)

    @classmethod
    def from_gf(cls, name: str, dl_url: str = PROD_FAMILY_DOWNLOAD):
        try:
            fonts = download_family_from_Google_Fonts(name, dl_url=dl_url)
            ttFont = TTFont(fonts[0])
            version = font_version(ttFont)
            name = ttFont["name"].getBestFamilyName()
            return cls(name, version)
        except (zipfile.BadZipFile, TTLibError):
            return None


@dataclass
class AxisFallback(Itemer):
    name: str
    value: float


@dataclass
class Axis(Itemer):
    tag: str
    display_name: str
    min_value: float
    default_value: float
    max_value: float
    precision: float
    fallback: list[AxisFallback]
    fallback_only: bool
    description: str

    @classmethod
    def from_gf_json(cls, axis):
        return cls(
            tag=axis["tag"],
            display_name=axis["displayName"],
            min_value=axis["min"],
            default_value=axis["defaultValue"],
            max_value=axis["max"],
            precision=axis["precision"],
            fallback=[
                AxisFallback(name=f["name"], value=f["value"])
                for f in axis["fallbacks"]
            ],
            fallback_only=axis["fallbackOnly"],
            description=axis["description"],
        )

    @classmethod
    def from_fp(cls, fp: Path):
        log.info("Getting axis data")

        fp = google_path_to_repo_path(fp)
        data = MessageToDict(ReadProto(AxisProto(), fp))

        return cls(
            tag=data["tag"],
            display_name=data["displayName"],
            min_value=data["minValue"],
            default_value=data["defaultValue"],
            max_value=data["maxValue"],
            precision=data["precision"],
            fallback=[
                AxisFallback(name=f["name"], value=f["value"]) for f in data["fallback"]
            ],
            fallback_only=data["fallbackOnly"],
            description=data["description"],
        )

    def to_json(self):
        d = self.__dict__
        d["fallback"] = [f.__dict__ for f in self.fallback]
        return d


@dataclass
class FamilyMeta(Itemer):
    name: str
    designer: list[str]
    license: str
    category: str
    subsets: list[str]
    stroke: str
    classifications: list[str]
    description: str
    primary_script: Optional[str] = None
    article: str = None
    minisite_url: str = None

    @classmethod
    def from_fp(cls, fp: Path):
        meta_fp = fp / "METADATA.pb"
        data = ReadProto(FamilyProto(), meta_fp)
        stroke = (
            data.category[0]
            if not data.stroke
            else data.stroke.replace(" ", "_").upper()
        )
        article_fp = fp / "article" / "ARTICLE.en_us.html"
        if article_fp.exists():
            article = parse_html(open(article_fp, encoding="utf-8").read())
        else:
            article = None

        description_fp = fp / "DESCRIPTION.en_us.html"
        if description_fp.exists():
            description = parse_html(open(description_fp, encoding="utf8").read())
        else:
            description = None
        return cls(
            name=data.name,
            designer=data.designer.split(", "),
            license=data.license.lower(),
            category=data.category[0],
            subsets=sorted([s for s in data.subsets if s != "menu"]),
            stroke=stroke,
            classifications=[c.lower() for c in data.classifications],
            description=description,
            primary_script=None if data.primary_script == "" else data.primary_script,
            article=article,
            minisite_url=None if data.minisite_url == "" else data.minisite_url,
        )

    @classmethod
    def from_gf_json(cls, meta):
        stroke = (
            None if meta["stroke"] == None else meta["stroke"].replace(" ", "_").upper()
        )
        if meta["article"]:
            article = parse_html(meta["article"][0])
        else:
            article = None
        return cls(
            name=meta["family"],
            designer=[i["name"].strip() for i in meta["designers"]],
            license=meta["license"].lower(),
            category=meta["category"].replace(" ", "_").upper(),
            subsets=sorted(list(meta["coverage"].keys())),
            stroke=stroke,
            classifications=[c.lower() for c in meta["classifications"]],
            description=None if article else parse_html(meta["description"]),
            primary_script=(
                None if meta["primaryScript"] == "" else meta["primaryScript"]
            ),
            article=article,
            minisite_url=None if meta["minisiteUrl"] == "" else meta["minisiteUrl"],
        )


def parse_html(string: str):
    if not string:
        return None
    text = BeautifulSoup(string, features="lxml").text
    return re.sub("\s+", " ", text).strip()


@dataclass
class Designer(Itemer):
    name: str
    bio: str

    @classmethod
    def from_gf_json(cls, data):
        return cls(data["name"], parse_html(data["bio"]))

    @classmethod
    def from_fp(cls, fp):
        meta = ReadProto(DesignerInfoProto(), fp / "info.pb")
        name = meta.designer
        bio_fp = fp / "bio.html"
        if not bio_fp.exists():
            return cls(name, None)
        with open(bio_fp, encoding="utf8") as doc:
            bio = doc.read()
            return cls(name, parse_html(bio))


Items = "Axis | Designer | Family | FamilyMeta"
