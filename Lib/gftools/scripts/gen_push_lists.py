#!/usr/bin/env python3
"""
Generate the to_production.txt and to_sandbox.txt server files in a local
google/fonts repository.

to_production.txt file tells the engineers which directories need to be pushed
to the production server. Likewise, the to_sandbox.txt file is for directories
to be pushed to the sandbox server.

In order for this script to work, the traffic jam must be kept up to date and
pull requests must use labels.

Usage:
gftools gen-push-lists /path/to/google/fonts
"""
import sys
import os
import subprocess
from gftools.push.trafficjam import (
    PushItems,
    PushStatus,
    PushList,
)
from gftools.push.utils import branch_matches_google_fonts_main
from pathlib import Path
from gftools.utils import is_google_fonts_repo
from contextlib import contextmanager
import pygit2


@contextmanager
def in_google_fonts_repo(gf_path):
    cwd = os.getcwd()
    try:
        os.chdir(gf_path)
        yield True
    finally:
        os.chdir(cwd)


# "tags/all/families.csv" and the axisregistry/lang directories are not
# PushCategory members (see gftools.push.trafficjam.PushItems.to_server_file),
# and axisregistry/lang releases usually land without a Traffic Jam PR at
# all, so they never show up in PushItems.from_traffic_jam() either. Instead
# of a static reminder on every run, we look at what actually changed in git
# between the last time these two files were generated (and committed) and
# now, and only surface a section when there's something to report.
TAGS_PATH = "tags/all/families.csv"
AXIS_LANG_DIRS = ("lang", "axisregistry")
SERVER_FILENAMES = ("to_sandbox.txt", "to_production.txt")


def _last_generated_commit(gf_path):
    """Hash of the last commit that touched to_sandbox.txt or
    to_production.txt, i.e. the last time this script's output was
    committed. None if neither file has ever been committed (fresh repo)."""
    result = subprocess.run(
        ["git", "log", "-1", "--format=%H", "--", *SERVER_FILENAMES],
        cwd=str(gf_path),
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() or None


def _changed_paths_since(repo, since_commit_hash, prefixes):
    """Paths that changed between since_commit_hash and HEAD, restricted to
    the given top-level prefixes (e.g. "lang", "axisregistry")."""
    try:
        old_commit = repo.revparse_single(since_commit_hash)
    except KeyError:
        # since_commit_hash isn't reachable anymore (rebase/squash, etc.)
        return set()
    new_commit = repo.head.peel()
    diff = repo.diff(old_commit, new_commit)
    changed = set()
    for delta in diff.deltas:
        path = delta.new_file.path or delta.old_file.path
        if any(path == p or path.startswith(f"{p}/") for p in prefixes):
            changed.add(path)
    return changed


def _build_dynamic_footer(gf_path):
    since = _last_generated_commit(gf_path)
    if since is None:
        # Nothing to compare against yet (e.g. first ever run) -- we can't
        # tell what's "new", so don't guess.
        return ""

    repo = pygit2.Repository(str(gf_path))
    tags_changed = _changed_paths_since(repo, since, [TAGS_PATH])
    axis_lang_changed = _changed_paths_since(repo, since, list(AXIS_LANG_DIRS))

    lines = []
    if tags_changed:
        lines += ["", "# Tags", TAGS_PATH]

    if axis_lang_changed:
        lines += ["", "# Axis registry / Lang", "# To complete if there is a new release"]
        for path in sorted(axis_lang_changed):
            lines.append(f"# {path} # No PR / Process automated")

    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def _apply_dynamic_footer(fp, footer):
    with open(fp, "r", encoding="utf-8") as doc:
        content = doc.read()
    # Strip a previously-appended footer first, so re-running the script
    # doesn't keep piling up duplicate/stale sections.
    cut_points = [
        i
        for i in (content.find("\n# Tags\n"), content.find("\n# Axis registry / Lang\n"))
        if i != -1
    ]
    if cut_points:
        content = content[: min(cut_points)]
    if footer:
        content = content.rstrip("\n") + "\n" + footer
    with open(fp, "w", encoding="utf-8") as doc:
        doc.write(content)


def main(args=None):
    if len(sys.argv) != 3:
        print("Usage: gftools gen-push-lists /path/to/google/fonts")
        sys.exit()

    gf_path = Path(sys.argv[2])
    if not is_google_fonts_repo(gf_path):
        raise ValueError(f"'{gf_path}' is not a valid google/fonts repo")

    with in_google_fonts_repo(gf_path):
        branch_matches_google_fonts_main(gf_path)
        to_sandbox_fp = os.path.join(gf_path, "to_sandbox.txt")
        to_production_fp = os.path.join(gf_path, "to_production.txt")

        # get existing push items
        board_items = PushItems.from_traffic_jam()
        sandbox_file = PushItems.from_server_file(
            to_sandbox_fp, PushStatus.IN_DEV, PushList.TO_SANDBOX
        )
        production_file = PushItems.from_server_file(
            to_production_fp, PushStatus.IN_SANDBOX, PushList.TO_PRODUCTION
        )

        sandbox_board = board_items.to_sandbox()
        production_board = board_items.to_production()
        live_board = board_items.live()

        to_sandbox = (sandbox_file + sandbox_board) - production_board
        to_production = (production_file + production_board) - live_board

        to_sandbox.to_server_file(to_sandbox_fp)
        to_production.to_server_file(to_production_fp)

        footer = _build_dynamic_footer(gf_path)
        _apply_dynamic_footer(to_sandbox_fp, footer)
        _apply_dynamic_footer(to_production_fp, footer)


if __name__ == "__main__":
    main()
