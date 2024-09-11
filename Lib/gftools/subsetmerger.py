from __future__ import annotations

import logging
import os
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from zipfile import ZipFile

import ufoLib2
import yaml
from fontmake.font_project import FontProject
from fontTools.designspaceLib import DesignSpaceDocument
from gftools.gfgithub import GitHubClient
from glyphsets import unicodes_per_glyphset
from strictyaml import HexInt, Int, Map, Optional, Seq, Str, Enum
from ufomerge import merge_ufos

from gftools.util.styles import STYLE_NAMES
from gftools.utils import download_file, open_ufo, parse_codepoint

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

FALLBACK_BRANCH_NAME = "main"

SUBSET_SOURCES: dict[str, tuple[str, str]] = {
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
            Optional("ranges"): Seq(
                Map({"start": (HexInt() | Int()), "end": (HexInt() | Int())})
            ),
            Optional("layoutHandling"): Str(),
            Optional("force"): Str(),
            Optional("exclude_glyphs"): Str(),
            Optional("exclude_codepoints"): Str(),
            Optional("exclude_glyphs_file"): Str(),
            Optional("exclude_codepoints_file"): Str(),
        }
    )
)


def prepare_minimal_subsets(subsets):
    # Turn a list of subsets into a minimal set of merges by gathering all
    # codepoints with the same "donor" font and options. This allows the
    # user to specify multiple subsets from the same font, and they will
    # be merged into a single merge operation.
    incl_excl_by_donor: dict[
        tuple[str, str, str],
        tuple[
            # Unicodes to include
            set[int],
            # Glyph names to exclude
            set[str],
        ],
    ] = defaultdict(lambda: (set(), set()))
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

        # Parse in manual exclusions
        excluded_codepoints = set()
        if exclude_inline := subset.get("exclude_codepoints"):
            for raw_value in exclude_inline.split():
                raw_value = raw_value.strip()
                if raw_value == "":
                    continue
                excluded_codepoints.add(parse_codepoint(raw_value))
        if exclude_file := subset.get("exclude_codepoints_file"):
            for line in Path(exclude_file).read_text().splitlines():
                line = line.strip()
                if line != "" and not line.startswith(("#", "//")):
                    continue
                # Remove in-line comments
                line = line.split("#", 1)[0]
                line = line.split("//", 1)[0]
                line = line.rstrip()
                excluded_codepoints.add(parse_codepoint(line))

        # Filter unicodes by excluded_codepoints
        unicodes = [
            unicode for unicode in unicodes if unicode not in excluded_codepoints
        ]

        # Load excluded glyphs by name
        exclude_glyphs = set()
        if exclude_inline := subset.get("exclude_glyphs"):
            for glyph_name in exclude_inline.split():
                glyph_name = glyph_name.strip()
                if glyph_name == "":
                    continue
                exclude_glyphs.add(glyph_name)
        if exclude_file := subset.get("exclude_glyphs_file"):
            for line in Path(exclude_file).read_text().splitlines():
                line = line.strip()
                if line != "" and not line.startswith(("#", "//")):
                    continue
                # Remove in-line comments
                line = line.split("#", 1)[0]
                line = line.split("//", 1)[0]
                line = line.rstrip()
                exclude_glyphs.add(line)

        # Update incl_excl_by_donor
        key = (
            yaml.dump(subset["from"]),
            subset.get("layoutHandling"),
            subset.get("force"),
        )
        unicodes_incl, glyph_names_excl = incl_excl_by_donor[key]
        unicodes_incl |= set(unicodes)
        glyph_names_excl |= exclude_glyphs

    # Now rebuild the subset dictionary, but this time with the codepoints
    # amalgamated into minimal sets.
    newsubsets = []
    for (donor, layouthandling, force), (
        unicodes_incl,
        glyph_names_excl,
    ) in incl_excl_by_donor.items():
        newsubsets.append(
            {
                "from": yaml.safe_load(donor),
                "unicodes": list(unicodes_incl),
                "exclude_glyphs": list(glyph_names_excl),
            }
        )
        if layouthandling:
            newsubsets[-1]["layoutHandling"] = layouthandling
        if force:
            newsubsets[-1]["force"] = force
    return newsubsets


class SubsetMerger:
    def __init__(
        self,
        input_ds,
        output_ds,
        subsets,
        googlefonts=False,
        cache="../subset-files",
        json=False,
        allow_sparse=False,
    ):
        self.input = input_ds
        self.output = output_ds
        self.subsets = prepare_minimal_subsets(subsets)
        self.googlefonts = googlefonts
        self.json = json
        self.cache_dir = cache
        self.subset_instances = {}
        self.allow_sparse = allow_sparse

    def add_subsets(self):
        """Adds the specified subsets to the designspace file and saves it to the output path"""
        ds = DesignSpaceDocument.fromfile(self.input)
        outpath = Path(self.output).parent
        added_subsets = False
        for master in ds.sources:
            newpath = os.path.join(outpath, os.path.basename(master.path))
            target_ufo = open_ufo(master.path)
            master.path = newpath

            if master.layerName is not None:
                continue

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

    def add_subset(self, target_ufo, ds, ds_source, subset) -> bool:
        # First, we find a donor UFO that matches the location of the
        # UFO to merge.
        location = dict(ds_source.location)
        newlocation = {}
        for axis in ds.axes:
            # We specify our location in terms of axis tags, because the
            # axes in the donor designspace file may have been renamed.
            newlocation[axis.tag] = axis.map_backward(location[axis.name])
        source_ufo = self.obtain_upstream(subset["from"], newlocation)
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
            exclude_glyphs=subset["exclude_glyphs"],
            codepoints=subset["unicodes"],
            existing_handling=existing_handling,
            layout_handling=layout_handling,
        )
        return True

    def obtain_upstream(
        self, upstream: str | dict[str, Any], location
    ) -> ufoLib2.Font | None:
        # Either the upstream is a string, in which case we try looking
        # it up in the SUBSET_SOURCES table, or it's a dict, in which
        # case it's a repository / path pair.
        if isinstance(upstream, str):
            if upstream not in SUBSET_SOURCES:
                raise ValueError("Unknown subsetting font %s" % upstream)
            repo, path = SUBSET_SOURCES[upstream]
            ref = FALLBACK_BRANCH_NAME
            font_name = f"{upstream}/{ref}"
        else:
            repo: str = upstream["repo"]
            parts = repo.split("@", 1)
            if len(parts) == 1:
                # Repo was already just the slug, use fallback ref
                ref = FALLBACK_BRANCH_NAME
            else:
                # Guaranteed to be 2 parts
                repo, ref = parts
                if ref == "latest":
                    # Resolve latest release's tag name
                    ref = GitHubClient.from_url(
                        f"https://github.com/{repo}"
                    ).get_latest_release_tag()
            path = upstream["path"]
            font_name = f"{repo}/{ref}/{path}"
        path = os.path.join(self.cache_dir, repo, ref, path)

        self.download_for_subsetting(repo, ref)

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

    def glyphs_to_ufo(self, source: str, directory: Path | None = None) -> str:
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
        # Our location is now specified in terms of tags
        newlocation = {}

        # Fill out the location with default values of axes we don't know about
        for axis in source_ds.axes:
            if axis.tag in location:
                newlocation[axis.name] = location[axis.tag]
            else:
                newlocation[axis.name] = axis.default
        for source in source_ds.sources:
            match = True
            for axis, loc in newlocation.items():
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
            logger.info(
                f"Adding subset {target.filename or target.name} for location {newlocation}"
            )
            return target

        if (
            self.allow_sparse
            and {axis.tag: axis.default for axis in source_ds.axes} != location
        ):
            logger.info(
                f"Could not find exact match for location {newlocation} in {font_name}, but allowing sparse"
            )
            return None

        raise ValueError(
            f"Could not find master in {font_name} for location {newlocation}"
        )

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
        for instance, _ufo in zip(source_ds.instances, ufos):
            instance.path = os.path.join(
                os.path.dirname(source_ds.path), instance.filename
            )

    def download_for_subsetting(self, fullrepo: str, ref: str) -> None:
        """Downloads a GitHub repository at a given reference"""
        dest = os.path.join(self.cache_dir, f"{fullrepo}/{ref}")
        if os.path.exists(dest):
            # Assume sources exist & are up-to-date (we have no good way of
            # checking this); do nothing
            logger.info("Subset files present on disk, skipping download")
            return
        # Make the parent folder to dest but not dest itself. This means that
        # the shutil.move at the end of this function won't create
        # dest/repo-ref, instead having dest contain the contents of repo-ref
        os.makedirs(os.path.join(self.cache_dir, fullrepo), exist_ok=True)

        # This URL scheme doesn't appear to be 100% official for tags &
        # branches, but it seems to accept any valid git reference
        # See https://stackoverflow.com/a/13636954 and
        # https://docs.github.com/en/repositories/working-with-files/using-files/downloading-source-code-archives#source-code-archive-urls
        repo_zipball = f"https://github.com/{fullrepo}/archive/{ref}.zip"
        logger.info(f"Downloading {fullrepo} {ref}")

        repo_zip = ZipFile(download_file(repo_zipball))
        _user, repo = fullrepo.split("/", 1)
        # If the tag name began with a "v" and looked like a version (i.e. has a
        # digit immediately afterwards), the "v" is stripped by GitHub. We have
        # to match this behaviour to get the correct name of the top-level
        # directory within the zip file
        if re.match(r"^v\d", ref):
            ref = ref[1:]
        with TemporaryDirectory() as temp_dir:
            repo_zip.extractall(temp_dir)
            shutil.move(os.path.join(temp_dir, f"{repo}-{ref}"), dest)
