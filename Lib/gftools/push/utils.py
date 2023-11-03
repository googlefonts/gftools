import subprocess
from pathlib import Path

import pygit2  # type: ignore


def _get_google_fonts_remote(repo):
    for remote in repo.remotes:
        if "google/fonts.git" in remote.url:
            return remote.name
    raise ValueError("Cannot find remote with url https://www.github.com/google/fonts")


def branch_matches_google_fonts_main(path):
    repo = pygit2.Repository(path)
    remote_name = _get_google_fonts_remote(repo)

    # fetch latest remote data from branch main
    subprocess.run(["git", "fetch", remote_name, "main"])

    # Check local is in sync with remote
    diff = repo.diff(repo.head, f"{remote_name}/main")
    if diff.stats.files_changed != 0:
        raise ValueError(
            "Your local branch is not in sync with the google/fonts "
            "main branch. Please pull or remove any commits."
        )
    return True


# The internal Google fonts team store the axisregistry and lang directories
# in a different location. The two functions below tranform paths to
# whichever representation you need.
def repo_path_to_google_path(fp: Path):
    """lang/Lib/gflanguages/data/languages/.*.textproto --> lang/languages/.*.textproto"""
    # we rename lang paths due to: https://github.com/google/fonts/pull/4679
    if "gflanguages" in fp.parts:
        return Path("lang") / fp.relative_to("lang/Lib/gflanguages/data")
    # https://github.com/google/fonts/pull/5147
    elif "axisregistry" in fp.parts:
        return Path("axisregistry") / fp.name
    return fp


def google_path_to_repo_path(fp: Path) -> Path:
    """lang/languages/.*.textproto --> lang/Lib/gflanguages/data/languages/.*.textproto"""
    if "lang" in fp.parts and "site-packages" not in fp.parts:
        return Path("lang/Lib/gflanguages/data/") / fp.relative_to("lang")
    elif "axisregistry" in fp.parts and "site-packages" not in fp.parts:
        return fp.parent / "Lib" / "axisregistry" / "data" / fp.name
    return fp
