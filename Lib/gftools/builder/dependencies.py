"""
Similar to pip freeze, but only listing the installed dependencies for the selected package.

E.g.:
    $ python -m gftools.builder.dependencies fonttools[ufo]
    # Installed requirements for 'fonttools[ufo]' (5 in total):

    appdirs==1.4.4
    fonttools==4.24.4
    fs==2.4.13
    pytz==2021.1
    six==1.16.0

Credit to Cosimo Lupo (anthrotype) for starting this as a gist:
https://gist.github.com/anthrotype/531a425c8a0ba5ee975bc2ec8add7b82
"""

from collections import deque, defaultdict
import re
from typing import (
    Generator,
    Iterable,
    DefaultDict,
    Dict,
    Set,
    Tuple,
)
from fontTools.ttLib import TTFont, newTable

try:
    import importlib.metadata as importlib_metadata
except ImportError:
    import importlib_metadata  # type: ignore

from packaging.requirements import Requirement


# list of packages that are considered 'unsafe' in a requirements file
DENYLIST = frozenset(["setuptools"])

GFTOOLS_DEPENDENCIES_KEY = "com.github.googlefonts.gftools.deps"


def _normalize(name: str) -> str:
    # https://www.python.org/dev/peps/pep-0503/#id4
    return re.sub(r"[-_.]+", "-", name).lower()


def _evaluate_extras(req: Requirement, extras: Set[str]) -> bool:
    if not req.marker:
        # no environment marker, matches anything
        return True
    if not extras:
        # no extra requested: still evaluate against the default environment,
        # using an empty placeholder to ignore any 'extra' marker
        extras = {""}
    return any(req.marker.evaluate({"extra": e}) for e in extras)


def get_installed_distributions(
    excluded: Set[str] = frozenset(),
) -> Dict[str, importlib_metadata.Distribution]:
    """Return a map of all installed distributions keyed by name, minus excluded ones."""
    # In importlib.metadata in python<3.10, attempting to use the 'name' property
    # getter on a PathDistribution object raises AttributeError, so we get the name
    # ourselves from the metadata dictionary as dist.metadata["Name"]
    return {
        name: dist
        for name, dist in (
            (_normalize(dist.metadata["Name"]), dist)
            for dist in importlib_metadata.distributions()
        )
        if name not in excluded
    }


def get_provided_extras(dist_name) -> Set[str]:
    """Return the set of extras provided by the given distribution package."""
    metadata = importlib_metadata.metadata(dist_name)
    if "Provides-Extra" in metadata:
        return {_normalize(e) for e in metadata.get_all("Provides-Extra")}
    return set()


def get_installed_requirements(
    dist_name: str,
    extras: Set[str] = frozenset(),
    excluded: Set[str] = DENYLIST,
) -> Generator[Tuple[str, str], None, None]:
    """Yield (name, version) of a distribution package and all its dependencies.

    Parse the installed packages' metadata, and traverse the dependency graph starting
    at 'dist_name'. Skip packages that are not installed, explicitly excluded (e.g.
    setuptools), or which don't match the requested set of 'extras'.
    """
    installed = get_installed_distributions(excluded)

    visited: DefaultDict[str, Set[str]] = defaultdict(set)
    frontier = deque([(_normalize(dist_name), extras)])

    while frontier:
        dist_name, extras = frontier.popleft()
        if dist_name not in installed:
            continue

        dist = installed[dist_name]

        if dist_name not in visited:
            yield (dist_name, dist.version)

        for req_spec in dist.requires or ():  # can be None
            req = Requirement(req_spec)
            # skip optional dependencies that don't match the requested extras
            if not _evaluate_extras(req, extras):
                continue
            req_name = _normalize(req.name)
            req_extras = {_normalize(extra) for extra in req.extras}

            if req_name not in visited:
                frontier.append((req_name, req_extras))
            else:
                # readd to the queue to traverse unvisited optional branches
                unvisited = req_extras - visited[req_name]
                if unvisited:
                    frontier.append((req_name, unvisited))

        visited[dist_name] |= extras


def format_requirements(requirements: Iterable[Tuple[str, str]]) -> str:
    return "".join(f"{name}=={version}\n" for name, version in sorted(requirements))


def write_font_requirements(ttfont: TTFont, dist_name: str):
    if "Debg" in ttfont:
        debg = ttfont["Debg"]
    else:
        debg = newTable("Debg")
        debg.data = {}
    requirements = get_installed_requirements(dist_name)
    debg.data["com.github.googlefonts.gftools.deps"] = format_requirements(
        requirements
    ).splitlines()
    ttfont["Debg"] = debg


def read_font_requirements(ttfont: TTFont):
    debg_table = ttfont["Debg"].data
    return "\n".join(debg_table[GFTOOLS_DEPENDENCIES_KEY])


def main():
    import sys

    try:
        req_spec = sys.argv[1]
    except IndexError:
        sys.exit("usage: python -m gftools.builder.dependencies PACKAGE_NAME")

    req = Requirement(req_spec)
    extras = {_normalize(extra) for extra in req.extras}

    result = list(get_installed_requirements(req.name, extras=extras))

    print(f"# Installed requirements for '{req_spec}' ({len(result)} in total):\n")
    print(format_requirements(result))


if __name__ == "__main__":
    main()
