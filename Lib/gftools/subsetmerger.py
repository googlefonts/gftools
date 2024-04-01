import logging
import os
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import ufoLib2
import yaml
from fontmake.font_project import FontProject
from fontTools.designspaceLib import DesignSpaceDocument
from glyphsets import unicodes_per_glyphset
from strictyaml import HexInt, Int, Map, Optional, Seq, Str, Enum
from ufomerge import merge_ufos

from gftools.util.styles import STYLE_NAMES
from gftools.utils import download_file, open_ufo

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

SUBSET_SOURCES = {
    "Noto Sans": ("notofonts/latin-greek-cyrillic", "sources/NotoSans.glyphspackage"),
    "Noto Serif": ("notofonts/latin-greek-cyrillic", "sources/NotoSerif.glyphspackage"),
    "Noto Sans Devanagari": (
        "notofonts/devanagari",
        "sources/NotoSansDevanagari.glyphspackage",
    ),
    "Noto Serif Devanagari": (
        "notofonts/devanagari",
        "sources/NotoSerifDevanagari.glyphspackage",
    ),
    "Noto Sans Linear B": ("notofonts/linear-b", "sources/NotoSansLinearB.designspace"),
}


subsets_schema = Seq(
    Map(
        {
            "from": Enum(SUBSET_SOURCES.keys()) | Map({"repo": Str(), "path": Str()}),
            Optional("name"): Str(),
            Optional("ranges"): Seq(Map({"start": (HexInt() | Int()), "end": (HexInt() | Int())})),
            Optional("layoutHandling"): Str(),
            Optional("force"): Str(),
        }
    )
)


def prepare_minimal_subsets(subsets):
    # Turn a list of subsets into a minimal set of merges by gathering all
    # codepoints with the same "donor" font and options. This allows the
    # user to specify multiple subsets from the same font, and they will
    # be merged into a single merge operation.
    unicodes_by_donor = defaultdict(set)
    for subset in subsets:
        # Resolved named subsets to a set of Unicode using glyphsets data
        if "name" in subset:
            unicodes = unicodes_per_glyphset(subset["name"])
            if not unicodes:
                raise ValueError("No glyphs found for subset " + subset["name"])
        else:
            unicodes = []
            for r in subset["ranges"]:
                for cp in range(r["start"], r["end"] + 1):
                    unicodes.append(cp)
        key = (
            yaml.dump(subset["from"]),
            subset.get("layoutHandling"),
            subset.get("force"),
        )
        unicodes_by_donor[key] |= set(unicodes)

    # Now rebuild the subset dictionary, but this time with the codepoints
    # amalgamated into minimal sets.
    newsubsets = []
    for (donor, layouthandling, force), unicodes in unicodes_by_donor.items():
        newsubsets.append({"from": yaml.safe_load(donor), "unicodes": list(unicodes)})
        if layouthandling:
            newsubsets[-1]["layoutHandling"] = layouthandling
        if force:
            newsubsets[-1]["force"] = force
    return newsubsets


class SubsetMerger:
    def __init__(
        self, input_ds, output_ds, subsets, googlefonts=False, cache="../subset-files", json=False
    ):
        self.input = input_ds
        self.output = output_ds
        self.subsets = prepare_minimal_subsets(subsets)
        self.googlefonts = googlefonts
        self.json = json
        self.cache_dir = cache
        self.subset_instances = {}

    def add_subsets(self):
        """Adds the specified subsets to the designspace file and saves it to the output path"""
        ds = DesignSpaceDocument.fromfile(self.input)
        outpath = Path(self.output).parent
        added_subsets = False
        for master in ds.sources:
            newpath = os.path.join(outpath, os.path.basename(master.path))
            target_ufo = open_ufo(master.path)

            master.path = newpath

            for subset in self.subsets:
                added_subsets |= self.add_subset(target_ufo, ds, master, subset)

            if self.json or master.path.endswith(".json"):
                if not master.path.endswith(".json"):
                    master.path += ".json"
                    if master.filename:
                        master.filename += ".json"
                target_ufo.json_dump(open(master.path, "wb"))
            else:
                target_ufo.save(master.path, overwrite=True)

        if not added_subsets:
            raise ValueError("Could not match *any* subsets for this font")

        for instance in ds.instances:
            instance.filename = instance.path = os.path.join(
                outpath, os.path.basename(instance.filename)
            )

        ds.write(self.output)

    def add_subset(self, target_ufo, ds, ds_source, subset):
        # First, we find a donor UFO that matches the location of the
        # UFO to merge.
        location = dict(ds_source.location)
        for axis in ds.axes:
            location[axis.name] = axis.map_backward(location[axis.name])
        source_ufo = self.obtain_upstream(subset["from"], location)
        if not source_ufo:
            return False
        existing_handling = "skip"
        if subset.get("force"):
            existing_handling = "replace"
        layout_handling = subset.get("layoutHandling", "subset")
        logger.info(
            f"Merge {subset['from']} from {source_ufo} into {ds_source.filename} with {existing_handling} and {layout_handling}"
        )
        merge_ufos(
            target_ufo,
            source_ufo,
            codepoints=subset["unicodes"],
            existing_handling=existing_handling,
            layout_handling=layout_handling,
        )
        return True

    def obtain_upstream(self, upstream, location):
        # Either the upstream is a string, in which case we try looking
        # it up in the SUBSET_SOURCES table, or it's a dict, in which
        # case it's a repository / path pair.
        if isinstance(upstream, str):
            if upstream not in SUBSET_SOURCES:
                raise ValueError("Unknown subsetting font %s" % upstream)
            repo, path = SUBSET_SOURCES[upstream]
            font_name = upstream
        else:
            repo = upstream["repo"]
            path = upstream["path"]
            font_name = "%s/%s" % (repo, path)
        path = os.path.join(self.cache_dir, repo, path)

        self.download_for_subsetting(repo)

        # We're doing a UFO-UFO merge, so Glyphs files will need to be converted
        if path.endswith((".glyphs", ".glyphspackage")):
            ds_path = re.sub(r".glyphs(package)?", ".designspace", path)
            if os.path.exists(ds_path):
                path = ds_path
            else:
                logger.info("Building UFO file for subset font " + font_name)
                path = self.glyphs_to_ufo(path)

        # Now we have an appropriate designspace containing the subset;
        # find the actual UFO that corresponds to the location we are
        # trying to add to.
        source_ds = DesignSpaceDocument.fromfile(path)
        source_ufo = self.find_source_for_location(source_ds, location, font_name)
        if source_ufo:
            return open_ufo(source_ufo.path)
        return None

    def glyphs_to_ufo(self, source, directory=None):
        source = Path(source)
        if directory is None:
            directory = source.resolve().parent
        output = str(Path(directory) / source.with_suffix(".designspace").name)
        FontProject().run_from_glyphs(
            str(source.resolve()),
            **{
                "format": ["ufo"],
                "output": ["ufo"],
                "output_dir": directory,
                "master_dir": directory,
                "designspace_path": output,
            },
        )
        if self.googlefonts:
            ds = DesignSpaceDocument.fromfile(output)
            ds.instances = [i for i in ds.instances if i.styleName in STYLE_NAMES]
            ds.write(output)

        return str(output)

    def find_source_for_location(self, source_ds, location, font_name):
        source_mappings = {ax.name: ax.map_forward for ax in source_ds.axes}
        target = None

        # Assume a source is good for this location unless proved otherwise.
        # This is useful for merging single-master donors into a multiple
        # master font.
        for source in source_ds.sources:
            match = True
            for axis, loc in location.items():
                if (
                    axis in source.location
                    and axis in source_mappings
                    and source.location[axis] != source_mappings[axis](loc)
                ):
                    match = False
            if match:
                target = source
                break

        if not target:
            logger.info(
                f"Couldn't find a master from {font_name} for location {location}, trying instances"
            )
            # We didn't find an exact match in the masters; maybe we will
            # be able to interpolate an instance which matches.
            for instance in source_ds.instances:
                if all(
                    axis in instance.location
                    and axis in source_mappings
                    and instance.location[axis] == source_mappings[axis](loc)
                    for axis, loc in location.items()
                ):
                    self.generate_subset_instances(source_ds, font_name, instance)
                    target = instance
                    break

        if target:
            logger.info(f"Adding subset from {font_name} for location {location}")
            return target

        raise ValueError(
            f"Could not find master in {font_name} for location {location}"
        )
        return None

    def generate_subset_instances(self, source_ds, font_name, instance):
        # Instance generation takes ages, cache which ones we've already
        # done on this run.
        if source_ds in self.subset_instances:
            return

        logger.info(f"Generate UFO instances for {font_name}")
        ufos = FontProject().interpolate_instance_ufos(source_ds, include=instance.name)
        self.subset_instances[source_ds] = ufos

        # We won't return an individual instance; instead we update the
        # path in the donor's designspace object so that it can be taken from there
        for instance, ufo in zip(source_ds.instances, ufos):
            instance.path = os.path.join(
                os.path.dirname(source_ds.path), instance.filename
            )

    def download_for_subsetting(self, fullrepo):
        dest = os.path.join(self.cache_dir, fullrepo)
        if os.path.exists(dest):
            return
        user, repo = fullrepo.split("/")
        os.makedirs(os.path.join(self.cache_dir, user), exist_ok=True)
        repo_zipball = f"https://github.com/{fullrepo}/archive/refs/heads/main.zip"
        logger.info(f"Downloading {fullrepo}")
        repo_zip = ZipFile(download_file(repo_zipball))
        with TemporaryDirectory() as d:
            repo_zip.extractall(d)
            shutil.move(os.path.join(d, repo + "-main"), dest)
