from pathlib import Path
from typing import List
from gftools.builder.operations import OperationBase

FONTC_PATH = "FONTC_PATH_NOT_SET"


# should only be called once, from main, before doing anything else. This is a
# relatively non-invasive way to smuggle this value into FontcOperationBase
def set_global_fontc_path(path: Path):
    global FONTC_PATH
    FONTC_PATH = path


class FontcOperationBase(OperationBase):
    @property
    def variables(self):
        vars = super().variables
        vars["fontc_path"] = FONTC_PATH
        args = vars.get("args")
        if args:
            vars["args"] = rewrite_fontmake_args_for_fontc(args)

        return vars


def rewrite_fontmake_args_for_fontc(args: str) -> str:
    out_args = []
    arg_list = args.split()
    # reverse so we can pop in order
    arg_list.reverse()
    while arg_list:
        out_args.append(rewrite_one_arg(arg_list))
    return " ".join(out_args)


# remove next arg from the front of the list and return its fontc equivalent
def rewrite_one_arg(args: List[str]) -> str:
    next_ = args.pop()
    if next_ == "--filter":
        filter_ = args.pop()
        # this means 'retain filters defined in UFO', which... do we even support
        # that in fontc?
        if filter_ == "...":
            pass
        elif filter_ == "FlattenComponentsFilter":
            return "--flatten-components"
        elif filter_ == "DecomposeTransformedComponentsFilter":
            return "--decompose-transformed-components"
        else:
            # glue the filter back together for better reporting below
            next_ = f"{next_} {filter_}"
    else:
        raise ValueError(f"unknown fontmake arg '{next_}'")
    return ""
