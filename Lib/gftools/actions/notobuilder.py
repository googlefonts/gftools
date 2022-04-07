"""Build a Noto font from one or more source files.

By default, places unhinted TTF, hinted TTF, OTF and (if possible) variable
fonts into the ``fonts/`` directory; merges in requested subsets at the UFO
level and places *those* fonts in the ``fonts/full/`` directory.

Example:

    python3 -m gftools.actions.notobuilder src/config.yaml
"""
import logging
import os
import re
import sys
import shutil
import tempfile
from pathlib import Path

import pygit2
import ufoLib2
from fontTools import designspaceLib
from glyphsets.codepoints import CodepointsInSubset
from strictyaml import HexInt, Map, Optional, Seq, Str

from gftools.builder import GFBuilder
from gftools.builder.autohint import autohint
from gftools.builder.schema import schema
from gftools.ufomerge import merge_ufos

# Add our keys to schema
subsets_schema = Seq(
    Map(
        {
            "from": Str(),
            Optional("name"): Str(),
            Optional("ranges"): Seq(Map({"start": HexInt(), "end": HexInt()})),
        }
    )
)
_newschema = schema._validator
_newschema[Optional("includeSubsets")] = subsets_schema


class NotoBuilder(GFBuilder):
    schema = Map(_newschema)

    def __init__(self, config):
        self.config = self.load_config(config)
        if os.path.dirname(config):
            os.chdir(os.path.dirname(config))
        family_dir = self.get_family_name().replace(" ", "")
        self.config["vfDir"] = "../fonts/%s/unhinted/variable-ttf" % family_dir
        self.config["otDir"] = "../fonts/%s/unhinted/otf" % family_dir
        self.config["ttDir"] = "../fonts/%s/unhinted/ttf" % family_dir
        self.config["buildWebfont"] = False
        self.config["autohintTTF"] = False  # We take care of it ourselves
        self.outputs = set()
        self.logger = logging.getLogger("GFBuilder")
        self.fill_config_defaults()

    def get_family_name(self, source=None):
        if not source:
            source = self.config["sources"][0]
        source, _ = os.path.splitext(os.path.basename(source))
        fname = re.sub(r"([a-z])([A-Z])", r"\1 \2", source)
        fname = re.sub("-?MM$", "", fname)
        return fname

    def post_process_ttf(self, filename):
        super().post_process_ttf(filename)
        self.outputs.add(filename)
        hinted_dir = self.config["ttDir"].replace("unhinted", "hinted")
        os.makedirs(hinted_dir, exist_ok=True)
        hinted = filename.replace("unhinted", "hinted")
        try:
            autohint(filename, hinted, add_script=True)
        except Exception as e:
            self.logger.error("Couldn't autohint %s: %s" % (filename, e))
            # We just copy it and pretend.
            shutil.copy(filename, hinted)
        self.outputs.add(hinted)

    def post_process(self, filename):
        super().post_process(filename)
        self.outputs.add(filename)

    def build_variable(self):
        try:
            super().build_variable()
        except Exception as e:
            self.logger.error("Couldn't build variable font: %s" % e)

    def glyphs_to_ufo(self, source, directory=None):
        source = Path(source)
        if directory is None:
            directory = source.resolve().parent
        self.run_fontmake(
            str(source.resolve()),
            {
                "format": ["ufo"],
                "output_dir": directory,
                "master_dir": directory,
                "designspace_path": Path(directory)
                / source.with_suffix(".designspace").name,
            },
        )
        return str(Path(directory) / source.with_suffix(".designspace").name)

    def build(self):
        # First convert to Designspace/UFO
        for ix, source in enumerate(self.config["sources"]):
            if source.endswith(".glyphs"):
                self.config["sources"][ix] = self.glyphs_to_ufo(source)

        # Do a basic build first
        super().build()

        # Merge UFOs
        if not "includeSubsets" in self.config:
            return

        for key in ["vfDir", "otDir", "ttDir"]:
            self.config[key] = self.config[key].replace("unhinted", "full")

        new_builder_sources = []
        temporaries = []

        for ds_file in self.config["sources"]:
            new_ds_file_dir = tempfile.TemporaryDirectory()
            temporaries.append(new_ds_file_dir)
            ds = designspaceLib.DesignSpaceDocument.fromfile(ds_file)
            for master in ds.sources:
                # Save a copy to temporary UFO
                newpath = os.path.join(new_ds_file_dir.name, os.path.basename(master.path))
                original_ufo = ufoLib2.Font.open(master.path)
                original_ufo.save(newpath, overwrite=True)

                master.path = newpath

                for subset in self.config["includeSubsets"]:
                    self.add_subset(ds, master, subset)
            # # Set instance filenames to temporary
            for instance in ds.instances:
                instance.filename = instance.path = os.path.join(new_ds_file_dir.name, os.path.basename(instance.filename))

            # Save new designspace to temporary
            new_ds_file = os.path.join(new_ds_file_dir.name, os.path.basename(ds_file))
            ds.write(new_ds_file)

            new_builder_sources.append(new_ds_file)

        self.config["sources"] = new_builder_sources

        super().build()
        # Temporaries should get cleaned here.

    def add_subset(self, ds, ds_source, subset):
        if "name" in subset:
            # Resolve to glyphset
            unicodes = CodepointsInSubset(subset["name"])
        else:
            unicodes = []
            for r in subset["ranges"]:
                for cp in range(r["start"], r["end"] + 1):
                    unicodes.append(cp)
        location = dict(ds_source.location)
        for axis in ds.axes:
            location[axis.name] = axis.map_backward(location[axis.name])
        source_ufo = self.obtain_noto_ufo(subset["from"], location)
        target_ufo = ufoLib2.Font.open(ds_source.path)
        merge_ufos(
            target_ufo, source_ufo, codepoints=unicodes, existing_handling="skip",
        )
        target_ufo.save(ds_source.path, overwrite=True)

    def obtain_noto_ufo(self, font_name, location):
        if font_name == "Noto Sans":
            self.clone_for_subsetting("latin-greek-cyrillic")
            path = "../subset-files/latin-greek-cyrillic/sources/NotoSans-MM.glyphs"
        if font_name == "Noto Serif":
            self.clone_for_subsetting("latin-greek-cyrillic")
            path = "../subset-files/latin-greek-cyrillic/sources/NotoSerif-MM.glyphs"
        if font_name == "Noto Sans Devanagari":
            self.clone_for_subsetting("devanagari")
            path = "../subset-files/devanagari/sources/NotoSansDevanagari.glyphs"

        if path.endswith(".glyphs"):
            ds_path = path.replace(".glyphs", ".designspace")
            if os.path.exists(ds_path):
                path = ds_path
            else:
                self.logger.info("Building UFO file for subset font "+font_name)
                path = self.glyphs_to_ufo(path)
        source_ds = designspaceLib.DesignSpaceDocument.fromfile(path)

        # Find a source for this location
        return ufoLib2.Font.open(self.find_source(source_ds, location, font_name).path)

    def find_source(self, source_ds, location, font_name):
        source_mappings = {
            ax.name: ax.map_forward for ax in source_ds.axes
        }
        target = None
        for source in source_ds.sources:
            match = True
            for axis, loc in location.items():
                if axis in source.location and axis in source_mappings and source.location[axis] != source_mappings[axis](loc):
                    match = False
            if match:
                target = source
                break
        if target:
            self.logger.info(f"Adding subset from {target} for location {location}")
            return target
        self.logger.error(f"Could not find master in {font_name} for location {location}")
        raise ValueError("Could not add subset")

    def clone_for_subsetting(self, repo):
        dest = "../subset-files/" + repo
        if os.path.exists(dest):
            return
        if not os.path.exists("../subset-files"):
            os.mkdir("../subset-files")
        print(f"Cloning notofonts/{repo}")
        pygit2.clone_repository(f"https://github.com/notofonts/{repo}", dest)




if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build a Noto font")
    parser.add_argument("config", metavar="YAML", help="config files")
    parser.add_argument("--verbose", "-v", action="store_true", help="verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)
    builder = NotoBuilder(args.config)
    builder.build()
    print("Produced the following files:")
    for o in builder.outputs:
        print("* " + o)
