#!/usr/bin/env python3
"""
Set ufo attributes for a collection of ufos

Usage:

# set openTypeOS2TypoAscender for a collection of ufos:
gftools ufo-setter --ufos ufo1.ufo ufo2.ufo --attribs info.openTypeOS2TypoAscender=700 

# set panose for a ufo:
gftools ufo-setter --ufos ufo1.ufo ufo2.ufo --attribs info.openTypeOS2Panose=[0,0,0,0,0,0,0,0,0,0]

# Set typo vertical metrics for a collection of ufos:
gftools ufo-setter --ufos ufo1.ufo ufo2.ufo ufo3.ufo --attribs \
    info.openTypeOS2TypoAscender=1000 \
    info.openTypeOS2TypoDescender=-250 \
    info.openTypeOS2TypoLineGap=0
"""
# TODO this could be generalised for all font formats
import argparse
from defcon import Font
import json


def parse_attributes(items):
    res = {}
    for item in items:
        k, v = item.split("=")
        res[k] = v
    return res


def set_ufo_attrib(obj, path, val):
    # use dfs to access nested attributes
    stack = [(obj, path)]
    while stack:
        item, path = stack.pop()
        if len(path) == 1:
            try:
                parsed_val = json.loads(val)
            except:
                parsed_val = val
            setattr(item, path[0], parsed_val)
            return
        current = path.pop(0)
        if hasattr(item, current):
            sub_item = getattr(item, current)
            stack.append((sub_item, path))
        elif current in item:
            sub_item = item[current]
            stack.append(sub_item, path)
        else:
            raise ValueError(f"{current} is not a valid attribute of {item}")
    return True


def main(args=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--ufos", nargs="+", help="path to ufos", required=True)
    parser.add_argument("--attribs", nargs="+", help="Attributes to set", required=True)
    args = parser.parse_args(args)

    attribs = parse_attributes(args.attribs)
    ufos = [Font(fp) for fp in args.ufos]
    for ufo in ufos:
        for attrib_name, attrib_value in attribs.items():
            set_ufo_attrib(ufo, attrib_name.split("."), attrib_value)
        ufo.save()


if __name__ == "__main__":
    main()
