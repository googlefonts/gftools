from fontTools.misc.cliTools import makeOutputFileName
from fontTools.ttLib import TTFont
import types
import yaml
import argparse


def loads(string):
    """
    name->setName: ["Hello world", 0, 3, 1, 0x409]
    OS/2->sTypoAscender: 1200
    -->
    {
        ("name", "setName): ["Hello world", 0, 3, 1, 0x409],
        ("OS/2", "sTypoAscender"): 1200,
    }
    """
    config = yaml.safe_load(string)
    res = {}
    for k, v in config.items():
        path = k.split("->")
        res[tuple(path)] = v
    return res


def load_config(fp):
    with open(fp, encoding="utf-8") as doc:
        return loads(doc.read())


def hasmethod(obj, name):
    return hasattr(obj, name) and type(getattr(obj, name)) == types.MethodType


def update_all(obj, config):
    for path, value in config.items():
        update(obj, path, value)


def update(obj, path, val):
    if len(path) == 0:
        return
    key = path[0]

    if len(path) == 1:
        if isinstance(key, str) and hasmethod(obj, key):
            getattr(obj, key)(*val)
        elif isinstance(key, str) and hasattr(obj, key):
            setattr(obj, key, val)
        else:
            obj[path[0]] = val
        return

    if isinstance(key, str) and hasattr(obj, key):
        update(getattr(obj, key), path[1:])
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
        update(obj[key], path[1:], val)
        if is_tuple:
            obj[key] = tuple(obj[key])


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("font", type=TTFont)
    parser.add_argument("config")
    parser.add_argument("-o", "--out", default=None)
    args = parser.parse_args(args)

    config = load_config(args.config)
    update_all(args.font, config)

    if not args.out:
        args.out = makeOutputFileName(args.font.reader.file.name)
    args.font.save(args.out)


if __name__ == "__main__":
    main()
