"""
This script is used to set values in a font file's tables using a YAML-like file.
The configuration file should be formatted as follows:

    OS/2->sTypoAscender: 1200 # Set a value in the OS/2 table
    name->setName: ["Hello world", 0, 3, 1, 0x409] # A method call on the name table
    head->macStyle: |= 0x01  # or with the current value

Unlike standard YAML, this script allows duplicate keys:

    name->setName: ["Hello world", 0, 3, 1, 0x409]
    name->setName: ["Cheese", 1, 3, 1, 0x409]

"""

import argparse
import re
import types

import ruamel.yaml
from fontTools.misc.cliTools import makeOutputFileName
from fontTools.ttLib import TTFont
from ruamel.yaml.constructor import SafeConstructor


# This bit of magic turns the top level dictionary into a list of
# (key, value) pairs, so that we can allow duplicate keys.
# This is helpful to allow us to call the same method (e.g. name->setName)
# multiple times with different arguments.
def construct_yaml_map(self, node):
    if self.deep_construct:
        data = {}
        yield data

        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=True)
            val = self.construct_object(value_node, deep=True)
            data[key] = val
    else:
        data = []
        yield data

        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=True)
            val = self.construct_object(value_node, deep=True)
            data.append((key, val))


SafeConstructor.add_constructor("tag:yaml.org,2002:map", construct_yaml_map)
yaml = ruamel.yaml.YAML(typ="safe")
yaml.allow_duplicate_keys = True


def load_config(fp):
    """
    name->setName: ["Hello world", 0, 3, 1, 0x409]
    OS/2->sTypoAscender: 1200
    -->
    [
        ("name", "setName): ["Hello world", 0, 3, 1, 0x409],
        ("OS/2", "sTypoAscender"): 1200,
    ]
    """
    with open(fp, encoding="utf-8") as doc:
        config = yaml.load(doc)
    return [(tuple(path.split("->")), value) for path, value in config]


def hasmethod(obj, name):
    return hasattr(obj, name) and type(getattr(obj, name)) == types.MethodType


def set_all(obj, config):
    for path, value in config:
        setter(obj, path, value)


def getter(obj, path):
    if len(path) == 0:
        return obj
    key = path[0]
    if hasmethod(obj, key):
        return getattr(obj, key)(*path[1])
    if isinstance(key, str) and hasattr(obj, key):
        return getter(getattr(obj, key), path[1:])
    if isinstance(obj, (list, dict, tuple, TTFont)):
        return getter(obj[key], path[1:])
    return obj


def setter(obj, path, val):
    if len(path) == 0:
        return
    key = path[0]

    if len(path) == 1:
        if isinstance(key, str) and hasmethod(obj, key):
            getattr(obj, key)(*val)
        elif isinstance(key, str) and hasattr(obj, key):
            if isinstance(val, str) and (m := re.match(r"\|=\s*(.*)", val)):
                setattr(obj, key, getattr(obj, key) | int(m.group(1), 0))
            else:
                setattr(obj, key, val)
        elif isinstance(val, str) and (m := re.match(r"\|=\s*(.*)", val)):
            obj[key] = obj[key] | int(m.group(1), 0)
        else:
            obj[path[0]] = val
        return

    if isinstance(key, str) and hasattr(obj, key):
        setter(getattr(obj, key), path[1:], val)
    elif isinstance(obj, (list, dict, tuple, TTFont)):
        is_tuple = False
        # convert numeric keys if needed
        try:
            obj[key]
        except:
            key = str(key)
            obj[key]
        # convert tuples to lists and then reconvert back using backtracking
        if isinstance(obj[key], tuple):
            is_tuple = True
            obj[key] = list(obj[key])
        setter(obj[key], path[1:], val)
        if is_tuple:
            obj[key] = tuple(obj[key])


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("font", type=TTFont)
    parser.add_argument("config")
    parser.add_argument("-o", "--out", default=None)
    args = parser.parse_args(args)

    config = load_config(args.config)
    set_all(args.font, config)

    if not args.out:
        args.out = makeOutputFileName(args.font.reader.file.name)
    args.font.save(args.out)


if __name__ == "__main__":
    main()
