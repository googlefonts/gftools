"""functionality for running fontc via gftools

This mostly exists so that we can keep as much of the fontc logic in one place,
and not need to dirty up anything else.
"""

from argparse import Namespace
from pathlib import Path
from typing import Union

from gftools.builder.operations.fontc import set_global_fontc_path


class FontcArgs:
    simple_output_path: Union[Path, None]
    fontc_bin_path: Union[Path, None]
    single_source: Union[str, None]

    # init with 'None' returns a default obj where everything is None
    def __init__(self, args: Union[Namespace, None]) -> None:
        if not args:
            return None
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

    # update the config dictionary based on our special needs
    def modify_config(self, config: dict):
        if self.fontc_bin_path or self.simple_output_path:
            # we stash this flag here to pass it down to the recipe provider
            config["use_fontc"] = self.fontc_bin_path
            config["buildWebfont"] = False
            config["buildSmallCap"] = False
            # override config to turn not build instances if we're variable
            if config.get("buildVariable", True):
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
        if self.single_source:
            filtered_sources = [s for s in config["sources"] if self.single_source in s]
            n_sources = len(filtered_sources)
            if n_sources != 1:
                raise ValueError(
                    f"--exerimental-single-source {self.single_source} must match exactly one of {config['sources']} (matched {n_sources}) "
                )
            config["sources"] = filtered_sources


def abspath(path: Union[Path, None]) -> Union[Path, None]:
    return path.resolve() if path else None
