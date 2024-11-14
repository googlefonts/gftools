"""functionality for running fontc via gftools

gftools has a few special flags that allow it to use fontc, an alternative
font compiler (https://github.com/googlefonts/fontc).

This module exists to keep the logic related to fontc in one place, and not
dirty up everything else.
"""

from argparse import Namespace
from pathlib import Path
from typing import Union
import time

from gftools.builder.file import File
from gftools.builder.operations.fontc import set_global_fontc_path


class FontcArgs:
    # init with 'None' returns a default obj where everything is None
    def __init__(self, args: Union[Namespace, None]) -> None:
        if not args:
            self.simple_output_path = None
            self.fontc_bin_path = None
            self.single_source = None
            return
        self.simple_output_path = abspath(args.experimental_simple_output)
        self.fontc_bin_path = abspath(args.experimental_fontc)
        self.single_source = args.experimental_single_source
        if self.fontc_bin_path:
            if not self.fontc_bin_path.is_file():
                raise ValueError(f"fontc does not exist at {self.fontc_bin_path}")
            set_global_fontc_path(self.fontc_bin_path)

    @property
    def use_fontc(self) -> bool:
        return self.fontc_bin_path is not None

    def build_file_name(self) -> str:
        if self.fontc_bin_path or self.simple_output_path:
            # if we're running for fontc we want uniquely named build files,
            # to ensure they don't collide
            return f"build-{time.time_ns()}.ninja"
        else:
            # otherwise just ues the default name
            return "build.ninja"

    # update the config dictionary based on our special needs
    def modify_config(self, config: dict):
        if self.single_source:
            filtered_sources = [s for s in config["sources"] if self.single_source in s]
            n_sources = len(filtered_sources)
            if n_sources != 1:
                raise ValueError(
                    f"--exerimental-single-source {self.single_source} must match exactly one of {config['sources']} (matched {n_sources}) "
                )
            config["sources"] = filtered_sources

        if self.fontc_bin_path or self.simple_output_path:
            # we stash this flag here to pass it down to the recipe provider
            config["use_fontc"] = self.fontc_bin_path
            config["buildWebfont"] = False
            config["buildSmallCap"] = False
            config["splitItalic"] = False
            config["cleanUp"] = True
            # disable running ttfautohint, because we had a segfault
            config["autohintTTF"] = False
            # set --no-production-names, because it's easier to debug
            extra_args = config.get("extraFontmakeArgs") or ""
            extra_args += " --no-production-names --drop-implied-oncurves"
            config["extraFontmakeArgs"] = extra_args
            # override config to turn not build instances if we're variable
            if self.will_build_variable_font(config):
                config["buildStatic"] = False
            # if the font doesn't explicitly request CFF, just build TT outlines
            # if the font _only_ wants CFF outlines, we will try to build them
            # ( but fail on fontc for now) (but is this even a thing?)
            elif config.get("buildTTF", True):
                config["buildOTF"] = False
        if self.simple_output_path:
            output_dir = str(self.simple_output_path)
            # we dump everything into one dir in this case
            config["outputDir"] = str(output_dir)
            config["ttDir"] = str(output_dir)
            config["otDir"] = str(output_dir)
            config["vfDir"] = str(output_dir)

    def will_build_variable_font(self, config: dict) -> bool:
        # if config explicitly says dont build variable, believe it
        if not config.get("buildVariable", True):
            return False

        source = File(config["sources"][0])
        return source.is_variable


def abspath(path: Union[Path, None]) -> Union[Path, None]:
    return path.resolve() if path else None
