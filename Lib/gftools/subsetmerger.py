import logging
import os
import re
import shutil
import typing
from collections import defaultdict
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Union
from zipfile import ZipFile

import ufoLib2
import yaml
from fontmake.font_project import FontProject
from fontTools.designspaceLib import (
    DesignSpaceDocument,
    InstanceDescriptor,
    SourceDescriptor,
)
from glyphsets import unicodes_per_glyphset
from glyphsLib.builder.constants import WIDTH_CLASS_TO_VALUE
from strictyaml import Enum, HexInt, Int, Map, Optional, Seq, Str
from ufomerge import merge_ufos

from gftools.gfgithub import GitHubClient
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
            "from": Str() | Map({"repo": Str(), "path": Str()}),
            Optional("name"): Str(),
            Optional("ranges"): Seq(
                Map({"start": (HexInt() | Int()), "end": (HexInt() | Int())})
            ),
            Optional("layoutHandling"): Str(),
            Optional("kernHandling"): Str(),
            Optional("force"): Str(),
            Optional("exclude_glyphs"): Seq(Str()),
            Optional("exclude_codepoints"): Seq(Str()),
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
        unicodes = []
        # Resolved named subsets to a set of Unicode using glyphsets data
        if "name" in subset:
            unicodes = unicodes_per_glyphset(subset["name"])
            if not unicodes:
                raise ValueError("No glyphs found for subset " + subset["name"])
        elif "ranges" in subset:
            for r in subset["ranges"]:
                for cp in range(r["start"], r["end"] + 1):
                    unicodes.append(cp)

        # Parse in manual exclusions
        excluded_codepoints = set()
        if exclude_inline := subset.get("exclude_codepoints"):
            for raw_value in exclude_inline:
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
            for glyph_name in exclude_inline:
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
        if not unicodes_incl:
            del newsubsets[-1]["unicodes"]
        if layouthandling:
            newsubsets[-1]["layoutHandling"] = layouthandling
        if force:
            newsubsets[-1]["force"] = force
    return newsubsets


# This is all complete overkill, but it really helps to reason about the
# source matching code.
@dataclass
class BaseDescriptor:
    ds: DesignSpaceDocument
    master: SourceDescriptor
    ufo: ufoLib2.Font

    @property
    def userspace_location(self) -> dict[str, Any]:
        """Returns the location of the master in user space"""
        return {
            axis.tag: axis.map_backward(self.master.location[axis.name])
            for axis in self.ds.axes
        }

    @property
    def filename(self) -> str:
        """Returns the filename of the master or UFO"""
        if self.master.filename:
            return self.master.filename
        return os.path.basename(self.master.path)

    @property
    def name(self) -> str:
        """Returns the name of the master"""
        return self.master.name or self.filename


@dataclass
class InputDescriptor(BaseDescriptor):
    pass


@dataclass
class DonorMasterDescriptor(BaseDescriptor):
    pass


@dataclass
class DonorInstanceDescriptor:
    ds: DesignSpaceDocument
    instance: InstanceDescriptor

    @property
    def userspace_location(self) -> dict[str, Any]:
        """Returns the location of the instance in user space"""
        return {
            axis.tag: axis.map_backward(self.instance.location[axis.name])
            for axis in self.ds.axes
        }

    @property
    def filename(self) -> str:
        """Returns the filename of the instance or UFO"""
        if self.instance.filename:
            return self.instance.filename
        return os.path.basename(self.instance.path)

    @property
    def name(self) -> str:
        """Returns the name of the instance"""
        return self.instance.name or self.filename

    @cached_property
    def ufo(self) -> ufoLib2.Font:
        logger.info(
            f"Generate UFO instance for {self.instance.familyName} {self.instance.name}"
        )
        self.instance.path = str(
            Path(self.ds.path).resolve().parent / Path(self.instance.filename).name
        )

        ufos = FontProject().interpolate_instance_ufos(
            self.ds, include=self.instance.name
        )
        return next(ufos)


def is_compatible(
    descriptor: Union[DonorInstanceDescriptor, DonorMasterDescriptor],
    input_descriptor: InputDescriptor,
) -> bool:
    input_userspace_location = input_descriptor.userspace_location
    my_userspace_location = descriptor.userspace_location
    common_axis_tags = set(input_userspace_location.keys()).intersection(
        set(my_userspace_location.keys())
    )
    # Assume a source is good for this location unless proved otherwise.
    # This is useful for merging single-master donors into a multiple
    # master font.
    for axis_tag in common_axis_tags:
        if input_userspace_location[axis_tag] != my_userspace_location[axis_tag]:
            logger.debug(
                f"Master {descriptor.filename} is not compatible with {input_descriptor.filename} on axis {axis_tag}: "
                f"{input_userspace_location[axis_tag]} != {my_userspace_location[axis_tag]}"
            )
            return False
    return True


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
        Path(output_ds).parent.mkdir(parents=True, exist_ok=True)
        self.subsets = prepare_minimal_subsets(subsets)
        self.googlefonts = googlefonts
        self.json = json
        self.cache_dir = cache
        self.subset_instances = {}
        self.allow_sparse = allow_sparse

    def add_subsets(self):
        """Adds the specified subsets to the designspace file and saves it to the output path"""

        if self.input.endswith(".ufo"):
            # Create a dummy designspace file for a single UFO
            input_ds = ufo_to_ds(self.input)
        else:
            input_ds = DesignSpaceDocument.fromfile(self.input)
        outpath = Path(self.output).parent
        added_subsets = False
        for input_master in input_ds.sources:
            newpath = os.path.join(outpath, os.path.basename(input_master.path))
            target_ufo = open_ufo(input_master.path)
            assert target_ufo is not None, (
                "Could not open UFO at %s" % input_master.path
            )
            input_master.path = newpath

            if input_master.layerName is not None:
                continue

            input_descriptor = InputDescriptor(input_ds, input_master, target_ufo)

            for subset in self.subsets:
                added_subsets |= self.add_subset(input_descriptor, subset)

            if self.json or input_master.path.endswith(".json"):
                if not input_master.path.endswith(".json"):
                    input_master.path += ".json"
                    if input_master.filename:
                        input_master.filename += ".json"
                target_ufo.json_dump(open(input_master.path, "wb"))
            else:
                target_ufo.save(input_master.path, overwrite=True)

        if not added_subsets:
            raise ValueError("Could not match *any* subsets for this font")

        for instance in input_ds.instances:
            instance.filename = instance.path = os.path.join(
                outpath, os.path.basename(instance.filename)
            )

        input_ds.write(self.output)

    def add_subset(self, input_descriptor: InputDescriptor, subset) -> bool:
        # First, we find a donor UFO that matches the location of the
        # UFO to merge.
        donor_ufo = self.obtain_upstream(subset["from"], input_descriptor)
        if not donor_ufo:
            return False
        existing_handling = "skip"
        if subset.get("force"):
            existing_handling = "replace"
        layout_handling = subset.get("layoutHandling", "subset")
        kern_handling = subset.get("kernHandling", "conservative")
        logger.info(
            f"Merge {subset['from']} from {donor_ufo} into {input_descriptor.filename} with {existing_handling} and {layout_handling}"
        )
        merge_ufos(
            input_descriptor.ufo,
            donor_ufo,
            exclude_glyphs=subset.get("exclude_glyphs", []),
            codepoints=subset.get("unicodes", None),
            existing_handling=existing_handling,
            layout_handling=layout_handling,
            kern_handling=kern_handling,
            include_dir=Path(donor_ufo.path).parent,
        )
        return True

    def obtain_upstream(
        self, upstream: Union[str, dict[str, Any]], input_descriptor: InputDescriptor
    ) -> typing.Optional[ufoLib2.Font]:
        # Either the upstream is a string, in which case we try looking
        # it up in the SUBSET_SOURCES table, or it's a dict, in which
        # case it's a repository / path pair.

        if isinstance(upstream, str) and upstream not in SUBSET_SOURCES:
            # Maybe it's a path to a local DS/Glyphs file?
            if os.path.exists(upstream):
                path = upstream
                font_name = os.path.basename(upstream)
            else:
                raise ValueError("Unknown subsetting font %s" % upstream)
        else:
            if isinstance(upstream, str):
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

        if os.path.exists(path):
            logger.info("Subset files present on disk, skipping download")
        else:
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
        donor_ds = DesignSpaceDocument.fromfile(path)
        return self.find_source_for_location(donor_ds, input_descriptor, font_name)

    def glyphs_to_ufo(
        self, source_str: str, directory: typing.Optional[Path] = None
    ) -> str:
        source = Path(source_str)
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

    def find_source_for_location(
        self,
        donor_ds: DesignSpaceDocument,
        input_descriptor: InputDescriptor,
        font_name: str,
    ) -> typing.Optional[ufoLib2.Font]:
        for source in donor_ds.sources:
            donor_descriptor = DonorMasterDescriptor(
                donor_ds, source, open_ufo(source.path)
            )
            if is_compatible(donor_descriptor, input_descriptor):
                logger.info(
                    f"Adding master {donor_descriptor.filename or donor_descriptor.name} for location {input_descriptor.userspace_location}"
                )
                return donor_descriptor.ufo

        logger.info(
            f"Couldn't find a master from {font_name} for location {input_descriptor.userspace_location}, trying instances"
        )
        # We didn't find an exact match in the masters; maybe we will
        # be able to interpolate an instance which matches.
        for instance in donor_ds.instances:
            instance_descriptor = DonorInstanceDescriptor(donor_ds, instance)
            if is_compatible(instance_descriptor, input_descriptor):
                logger.info(
                    f"Adding instance {instance_descriptor.filename or input_descriptor.name} for location {input_descriptor.userspace_location}"
                )

                return instance_descriptor.ufo

        raise ValueError(
            f"Could not find master in {font_name} for location {input_descriptor.userspace_location}"
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


def ufo_to_ds(ufo_path: str) -> DesignSpaceDocument:
    """Converts a UFO to a designspace file"""
    ds = DesignSpaceDocument()
    ufo = open_ufo(ufo_path)
    assert isinstance(ufo, ufoLib2.Font)
    location = {
        "Weight": (ufo.info.openTypeOS2WeightClass or 400),
        "Width": WIDTH_CLASS_TO_VALUE[(ufo.info.openTypeOS2WidthClass or 5)],
    }
    ds.addSourceDescriptor(
        filename=os.path.basename(ufo_path), path=ufo_path, location=location
    )
    ds.addAxisDescriptor(
        tag="wght",
        name="Weight",
        minimum=100,
        maximum=900,
        default=400,
    )
    ds.addAxisDescriptor(
        tag="wdth",
        name="Width",
        minimum=WIDTH_CLASS_TO_VALUE[1],
        maximum=WIDTH_CLASS_TO_VALUE[9],
        default=WIDTH_CLASS_TO_VALUE[5],
    )
    ds.addInstanceDescriptor(
        path=ufo_path,
        name="instance",
        location=location,
        filename=os.path.basename(ufo_path),
    )
    return ds
