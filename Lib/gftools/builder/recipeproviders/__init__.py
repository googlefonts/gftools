from dataclasses import dataclass
import importlib
import inspect
from typing import List
from gftools.builder.file import File

filecache = {}


def get_file(path):
    if path not in filecache:
        filecache[path] = File(path)
    return filecache[path]


@dataclass
class RecipeProviderBase:
    config: dict
    builder: "gftools.builder.GFBuilder"

    def write_recipe(self):
        raise NotImplementedError

    @property
    def sources(self) -> List[File]:
        return [get_file(str(p)) for p in self.config["sources"]]


def get_provider(provider: str):
    # First try gftools.builder.recipeproviders.X
    try:
        mod = importlib.import_module("gftools.builder.recipeproviders." + provider)
    except ModuleNotFoundError:
        # Then try X
        try:
            mod = importlib.import_module(provider)
        except ModuleNotFoundError:
            raise ValueError(f"Cannot find recipe provider {provider}")
    classes = [
        (name, cls)
        for name, cls in inspect.getmembers(mod, inspect.isclass)
        if "RecipeProviderBase" not in name
        and issubclass(cls, RecipeProviderBase)
        and provider in cls.__module__
    ]
    if len(classes) > 1:
        raise ValueError(
            "Multiple recipe providers found in module %s: %s"
            % (provider, [x[0] for x in classes])
        )
    return classes[0][1]
