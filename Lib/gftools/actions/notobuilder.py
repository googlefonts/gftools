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
        self.config["vfDir"] = "../fonts/unhinted/variable-ttf"
        self.config["otDir"] = "../fonts/unhinted/otf"
        self.config["ttDir"] = "../fonts/unhinted/ttf"
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
            self.outputs.add(hinted)
        except Exception as e:
            self.logger.error("Couldn't autohint %s: %s" % (filename, e))

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

        for ds_file in self.config["sources"]:
            ds = designspaceLib.DesignSpaceDocument.fromfile(ds_file)
            for subset in self.config["includeSubsets"]:
                if len(ds.sources) == 1:
                    self.add_subset(ds.sources[0], subset, mapping="Regular")
                else:
                    for master in ds.sources:
                        self.add_subset(ds.sources[0], subset)

        super().build()

    def add_subset(self, ds_source, subset, mapping=None):
        if mapping is None:
            raise NotImplementedError
        if "name" in subset:
            # Resolve to glyphset
            unicodes = CodepointsInSubset(subset["name"])
        else:
            unicodes = []
            for r in subset["ranges"]:
                for cp in range(r["start"], r["end"] + 1):
                    unicodes.append(cp)
        source_ufo = self.obtain_noto_ufo(subset["from"], mapping)
        target_ufo = ufoLib2.Font.open(ds_source.path)
        merge_ufos(
            target_ufo, source_ufo, codepoints=unicodes, existing_handling="skip",
        )
        target_ufo.save(ds_source.path, overwrite=True)

    def obtain_noto_ufo(self, font_name, mapping):
        if font_name == "Noto Sans":
            self.clone_for_subsetting("latin-greek-cyrillic")
            path = "../subset-files/latin-greek-cyrillic/sources/NotoSans-MM.glyphs"
        if font_name == "Noto Sans Devanagari":
            self.clone_for_subsetting("devanagari")
            path = "../subset-files/devanagari/sources/NotoSansDevanagari.glyphs"

        if path.endswith(".glyphs"):
            # Check if UFO already exists
            path = self.glyphs_to_ufo(path)
        source_ds = designspaceLib.DesignSpaceDocument.fromfile(path)
        regs = [
            source.path
            for source in source_ds.sources
            if source.name.endswith("Regular")
        ]
        if not regs:
            regs = [source_ds.sources[0].path]
        return ufoLib2.Font.open(regs[0])

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
