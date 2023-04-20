"""
This module implements gftools/bin/gftools-packager.py

Tool to take files from a font family project upstream git repository
to the google/fonts GitHub repository structure, taking care of all the details.

Documentation at gftools/docs/gftools-packager/README.md
"""
import sys
import argparse
import os
import shutil
from tempfile import TemporaryDirectory
import zipfile
import subprocess
import typing
from collections import OrderedDict
import traceback
from io import StringIO, BytesIO
import pygit2  # type: ignore
import functools
from hashlib import sha1
import humanize
from fontTools.ttLib import TTFont  # type: ignore
from gflanguages import LoadLanguages
from gftools.util import google_fonts as fonts
from gftools.github import GitHubClient
from gftools.utils import download_file
from gftools.packager.git import (
    git_push,
    shallow_clone_git,
    find_github_remote,
    get_root_commit,
    git_tree_walk,
    git_fetch_main,
    git_copy_dir,
)
from gftools.packager.constants import (
    ALLOWED_FILES,
    GITHUB_REPO_SSH_URL,
    LICENSE_DIRS,
    GIT_NEW_BRANCH_PREFIX,
)
from gftools.packager.exceptions import UserAbortError, ProgramAbortError
from gftools.packager.upstream import (
    UpstreamConfig,
    get_upstream_info,
)

# ignore type because mypy error: Module 'google.protobuf' has no
# attribute 'text_format'
from google.protobuf import text_format  # type: ignore

# Getting many mypy errors here like: Lib/gftools/fonts_public_pb2.py:253:
#     error: Unexpected keyword argument "serialized_options" for "Descriptor"
# The "type: ignore" annotation didn't help.
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    fonts_pb2: typing.Any
else:
    import gftools.fonts_public_pb2 as fonts_pb2


def _write_file_to_package(basedir: str, filename: str, data: bytes) -> None:
    full_name = os.path.realpath(os.path.join(basedir, filename))

    # Can't just let write the file anywhere!
    full_directory = os.path.join(os.path.realpath(basedir), "")
    if os.path.commonprefix([full_name, full_directory]) != full_directory:
        raise Exception(f'Target is not in package directory: "{filename}".')

    os.makedirs(os.path.dirname(full_name), exist_ok=True)
    with open(full_name, "wb") as file:
        file.write(data)


def _file_in_package(basedir, filename):
    full_name = os.path.join(basedir, filename)
    return os.path.isfile(full_name)


def _is_allowed_file(filename: str, no_allowlist: bool = False):
    # there are two places where .ttf files are allowed to go
    # we don't do filename/basename validation here, that's
    # a job for font bakery
    if filename.endswith(".ttf") and os.path.dirname(filename) in ["", "static"]:
        return True  # using this!
    if filename not in ALLOWED_FILES and not no_allowlist:  # this is the default
        return False
    return True


SKIP_NOT_PERMITTED = "Target is not a permitted filename (see --no_allowlist):"
SKIP_SOURCE_NOT_FOUND = "Source not found in upstream:"
SKIP_SOURCE_NOT_BLOB = "Source is not a blob (blob=file):"
SKIP_COPY_EXCEPTION = "Can't copy:"


def _copy_upstream_files_from_git(
    branch: str,
    files: dict,
    repo: pygit2.Repository,
    write_file_to_package: typing.Callable[[str, bytes], None],
    no_allowlist: bool = False,
) -> OrderedDict:

    skipped: "OrderedDict[str, typing.List[str]]" = OrderedDict(
        [
            (SKIP_NOT_PERMITTED, []),
            (SKIP_SOURCE_NOT_FOUND, []),
            (SKIP_SOURCE_NOT_BLOB, []),
            (SKIP_COPY_EXCEPTION, []),
        ]
    )
    for source, target in files.items():
        # else: allow, write_file_to_package will raise errors if target is bad
        if not _is_allowed_file(target, no_allowlist):
            skipped[SKIP_NOT_PERMITTED].append(target)
            continue

        try:
            source_object = repo.revparse_single(f"{branch}:{source}")
        except KeyError:
            skipped[SKIP_SOURCE_NOT_FOUND].append(source)
            continue

        if source_object.type != pygit2.GIT_OBJ_BLOB:
            skipped[SKIP_SOURCE_NOT_BLOB].append(
                f"{source} (type is {source_object.type_str})"
            )
            continue

        try:
            write_file_to_package(target, source_object.data)
        except Exception as e:
            # i.e. file exists
            skipped[SKIP_COPY_EXCEPTION].append(f"{target} ERROR: {e}")
    # Clean up empty entries in skipped.
    # using list() because we can't delete from a dict during iterated
    for key in list(skipped):
        if not skipped[key]:
            del skipped[key]
    # If skipped is empty all went smooth.
    return skipped


def _copy_upstream_files_from_dir(
    source_dir: str,
    files: dict,
    write_file_to_package: typing.Callable[[str, bytes], None],
    no_allowlist: bool = False,
) -> OrderedDict:

    skipped: "OrderedDict[str, typing.List[str]]" = OrderedDict(
        [
            (SKIP_NOT_PERMITTED, []),
            (SKIP_SOURCE_NOT_FOUND, []),
            (SKIP_SOURCE_NOT_BLOB, []),
            (SKIP_COPY_EXCEPTION, []),
        ]
    )
    for source, target in files.items():
        # else: allow, write_file_to_package will raise errors if target is bad
        if not _is_allowed_file(target, no_allowlist):
            skipped[SKIP_NOT_PERMITTED].append(target)
            continue

        try:
            with open(os.path.join(source_dir, source), "rb") as f:
                source_data = f.read()
        except FileNotFoundError:
            skipped[SKIP_SOURCE_NOT_FOUND].append(source)
            continue
        except Exception as err:
            # e.g. IsADirectoryError
            skipped[SKIP_SOURCE_NOT_BLOB].append(f"{source} ({type(err).__name__})")
            continue

        try:
            write_file_to_package(target, source_data)
        except Exception as e:
            # i.e. file exists
            skipped[SKIP_COPY_EXCEPTION].append(f"{target} ERROR: {e}")

    # Clean up empty entries in skipped.
    # using list() because we can't delete from a dict during iterated
    for key in list(skipped):
        if not skipped[key]:
            del skipped[key]
    # If skipped is empty all went smooth.
    return skipped


def _create_or_update_metadata_pb(
    upstream_conf: UpstreamConfig,
    tmp_package_family_dir: str,
    upstream_commit_sha: str = None,
    upstream_archive_url: str = None,
) -> None:
    metadata_file_name = os.path.join(tmp_package_family_dir, "METADATA.pb")
    try:
        subprocess.run(
            ["gftools", "add-font", tmp_package_family_dir],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as e:
        print(str(e.stderr, "utf-8"), file=sys.stderr)
        raise e

    metadata = fonts_pb2.FamilyProto()

    with open(metadata_file_name, "rb") as fb:
        text_format.Parse(fb.read(), metadata)

    upstream_conf.fill_metadata(metadata)
    if upstream_commit_sha:
        metadata.source.commit = upstream_commit_sha
    if upstream_archive_url:
        metadata.source.archive_url = upstream_archive_url

    language_comments = fonts.LanguageComments(LoadLanguages())
    fonts.WriteProto(metadata, metadata_file_name, comments=language_comments)


def _create_package_content(
    package_target_dir: str,
    repos_dir: str,
    upstream_conf: UpstreamConfig,
    license_dir: str,
    gf_dir_content: dict,
    allow_build: bool,
    no_allowlist: bool = False,
) -> str:
    print(f"Creating package with \n{upstream_conf.format()}")
    upstream_commit_sha = None

    family_dir = os.path.join(license_dir, upstream_conf.normalized_family_name)
    package_family_dir = os.path.join(package_target_dir, family_dir)
    # putting state into functions, could be done with classes/methods as well
    write_file_to_package = functools.partial(
        _write_file_to_package, package_family_dir
    )
    file_in_package = functools.partial(_file_in_package, package_family_dir)
    # Get and add upstream files!
    upstream_dir_target = (
        (
            f'{upstream_conf.get("repository_url")}'
            f'__{upstream_conf.get("branch")}'
            # Despite of '.' and '/' I'd expect the other replacements
            # not so important in this case.
        )
        .replace("://", "_")
        .replace("/", "_")
        .replace(".", "_")
        .replace("\\", "_")
    )

    if upstream_conf.get("archive"):
        print("Downloading release archive...")
        with TemporaryDirectory() as tmp:
            archive_path = os.path.join(tmp, "archive.zip")
            download_file(upstream_conf.get("archive"), archive_path)
            with zipfile.ZipFile(archive_path, "r") as zip_ref:
                zip_ref.extractall(tmp)
            print("DONE downloading and unzipping!")
            skipped = _copy_upstream_files_from_dir(
                tmp,
                upstream_conf.get("files"),
                write_file_to_package,
                no_allowlist=no_allowlist,
            )
            upstream_archive_url = upstream_conf.get("archive")
    else:
        upstream_archive_url = None
        local_repo_path_marker = "local://"
        if upstream_conf.get("repository_url").startswith(local_repo_path_marker):
            print(
                f'WARNING using "local://" hack for repository_url: {upstream_conf.get("repository_url")}'
            )
            local_path = upstream_conf.get("repository_url")[
                len(local_repo_path_marker) :
            ]
            upstream_dir = os.path.expanduser(local_path)
        else:
            upstream_dir = os.path.join(repos_dir, upstream_dir_target)
            if not os.path.exists(upstream_dir):
                # for super families it's likely that we can reuse the same clone
                # of the repository for all members
                shallow_clone_git(
                    upstream_dir,
                    upstream_conf.get("repository_url"),
                    upstream_conf.get("branch"),
                )
        repo = pygit2.Repository(upstream_dir)

        upstream_commit = repo.revparse_single(upstream_conf.get("branch"))
        upstream_commit_sha = upstream_commit.hex

        # Copy all files from upstream_conf.get('files') to package_family_dir
        # We are strict about what to allow, unexpected files
        # are not copied. Instead print a warning an suggest filing an
        # issue if the file is legitimate. A flag to explicitly
        # skip the allowlist check (--no_allowlist)
        # enables making packages even when new, yet unknown files are required).
        # Do we have a Font Bakery check for expected/allowed files? Would
        # be a good complement.
        skipped = _copy_upstream_files_from_git(
            upstream_conf.get("branch"),
            upstream_conf.get("files"),
            repo,
            write_file_to_package,
            no_allowlist=no_allowlist,
        )
    if skipped:
        message = ["Some files from upstream_conf could not be copied."]
        for reason, items in skipped.items():
            message.append(reason)
            for item in items:
                message.append(f" - {item}")
        # The allowlist can be ignored using the flag no_allowlist flag,
        # but the rest should be fixed in the files map, because it's
        # obviously wrong, not working, configuration.
        raise ProgramAbortError("\n".join(message))

    # Get and add all files from google/fonts
    for name, entry in gf_dir_content.items():
        # not copying old TTFs, directories and files that are already there
        if name.endswith(".ttf") or entry["type"] != "blob" or file_in_package(name):
            continue
        file_sha = gf_dir_content[name]["oid"]
        response = GitHubClient("google", "fonts").get_blob(file_sha)
        write_file_to_package(name, response.content)

    # create/update METADATA.pb
    _create_or_update_metadata_pb(
        upstream_conf, package_family_dir, upstream_commit_sha, upstream_archive_url
    )

    # create/update upstream.yaml
    # Remove keys that are also in METADATA.pb googlefonts/gftools#233
    # and also clear all comments.
    stripped = upstream_conf.stripped()
    stripped.save(os.path.join(package_family_dir, "upstream.yaml"), force=True)
    print(f'DONE Creating package for {upstream_conf.get("name")}!')
    return family_dir


def _check_git_target(target: str) -> None:
    try:
        repo = repo = pygit2.Repository(target)
    except Exception as e:
        raise ProgramAbortError(
            f'Can\'t open "{target}" as git repository. ' f"{e} ({type(e).__name__})."
        )
    repo_owner = "google"
    repo_name = "fonts"
    repo_name_with_owner = f"{repo_owner}/{repo_name}"
    remote_name_or_none = find_github_remote(repo, repo_owner, repo_name, "main")
    if remote_name_or_none is None:
        # NOTE: we could ask the user if we should add the missing remote.
        # This makes especially sense if the repository is a fork of
        # google/fonts and essentially has the same history/object database.
        # It would be very uncommon, probably unintended, if the repo is not
        # related to the google/fonts repo and fetching from that remote would
        # have to download a lot of new data, as well as probably create
        # confusing situations for the user when dealing with GitHub PRs etc.
        print(
            f'The git repository at target "{target}" has no remote for '
            f"GitHub {repo_name_with_owner}.\n"
            "You can add it by running:\n"
            f"$ cd {target}\n"
            f"$ git remote add googlefonts {GITHUB_REPO_SSH_URL(repo_name_with_owner=repo_name_with_owner)}.git\n"
            "For more context, run:\n"
            "$ git remote help"
        )

        raise ProgramAbortError(
            "The target git repository has no remote for GitHub google/fonts."
        )


def _check_directory_target(target: str) -> None:
    if not os.path.isdir(target):
        raise ProgramAbortError(f'Target "{target}" is not a directory.')


def _make_pr(
    repo: pygit2.Repository,
    local_branch_name: str,
    pr_upstream: str,
    push_upstream: str,
    pr_title: str,
    pr_message_body: str,
):
    print("Making a Pull Request …")
    if not push_upstream:
        push_upstream = pr_upstream

    push_owner, _push_repo = push_upstream.split("/")
    pr_owner, pr_repo = pr_upstream.split("/")
    url = GITHUB_REPO_SSH_URL(repo_name_with_owner=push_upstream)

    remote_branch_name = local_branch_name
    # We must only allow force pushing/general pushing to branch names that
    # this tool *likely* created! Otherwise, we may end up force pushing
    # to `main` branch! Hence: we expect a prefix for remote_branch_name indicating
    # this tool created it.
    if remote_branch_name.find(GIT_NEW_BRANCH_PREFIX) != 0:
        remote_branch_name = (
            f"{GIT_NEW_BRANCH_PREFIX}" f'{remote_branch_name.replace(os.sep, "_")}'
        )

    print(
        "git push:\n"
        f"  url is {url}\n"
        f"  local branch name is {local_branch_name}\n"
        f"  remote branch name is {remote_branch_name}\n"
    )
    # Always force push?
    # If force == False and we update an existing remote:
    #   _pygit2.GitError: cannot push non-fastforwardable reference
    # But I don't use the --force flag here, because I believe this is
    # very much the standard case, i.e. that we update existing PRs.
    git_push(repo, url, local_branch_name, remote_branch_name, force=True)
    print("DONE git push!")

    pr_head = f"{push_owner}:{remote_branch_name}"
    pr_base_branch = "main"  # currently we always do PRs to main
    # _updateUpstream(prRemoteName, prRemoteRef))
    # // NOTE: at this point the PUSH was already successful, so the branch
    # // of the PR exists or if it existed it has changed.
    client = GitHubClient(pr_owner, pr_repo)
    open_prs = client.open_prs(pr_head, pr_base_branch)

    if not len(open_prs):
        # No open PRs, creating …
        result = client.create_pr(pr_title, pr_message_body, pr_head, pr_base_branch)
        print(f'Created a PR #{result["number"]} {result["html_url"]}')
    else:
        # found open PR
        pr_issue_number = open_prs[0]["number"]
        pr_comment_body = f"Updated\n\n## {pr_title}\n\n---\n{pr_message_body}"
        result = client.create_issue_comment(pr_issue_number, pr_comment_body)
        print(f'Created a comment in PR #{pr_issue_number} {result["html_url"]}')


def _get_change_info_from_diff(
    repo: pygit2.Repository, root_tree: pygit2.Tree, tip_tree: pygit2.Tree
) -> typing.Dict:
    # I probably also want the changed files between root_commit and tip commit
    diff = repo.diff(root_tree, tip_tree)
    all_touched_files = set()
    for delta in diff.deltas:
        # possible status chars:
        #   GIT_DELTA_ADDED:      A
        #   GIT_DELTA_DELETED:    D
        #   GIT_DELTA_MODIFIED:   M
        #   GIT_DELTA_RENAMED:    R
        #   GIT_DELTA_COPIED:     C
        #   GIT_DELTA_IGNORED:    I
        #   GIT_DELTA_UNTRACKED:  ?
        #   GIT_DELTA_TYPECHANGE: T
        #   GIT_DELTA_UNREADABLE: X
        #   default:              ' '
        if delta.status_char() == "D":
            all_touched_files.add(delta.old_file.path)
        else:
            all_touched_files.add(delta.new_file.path)
    touched_family_dirs = set()
    for filename in all_touched_files:
        for dirname in LICENSE_DIRS:
            if filename.startswith(f"{dirname}{os.path.sep}"):
                # items are e.g. ('ofl', 'gelasio')
                touched_family_dirs.add(tuple(filename.split(os.path.sep)[:2]))
                break
    family_changes_dict = {}
    for dir_path_tuple in touched_family_dirs:
        family_tree: pygit2.Tree = tip_tree
        for pathpart in dir_path_tuple:
            family_tree = family_tree / pathpart

        metadata_blob: pygit2.Blob = family_tree / "METADATA.pb"
        metadata = fonts_pb2.FamilyProto()
        text_format.Parse(metadata_blob.data, metadata)

        # get the version
        first_font_file_name = metadata.fonts[0].filename
        first_font_blob: pygit2.Blob = family_tree / first_font_file_name
        first_font_file = BytesIO(first_font_blob.data)
        ttFont = TTFont(first_font_file)
        version: typing.Union[None, str] = None
        NAME_ID_VERSION = 5
        for entry in ttFont["name"].names:
            if entry.nameID == NAME_ID_VERSION:
                # just taking the first instance
                version = entry.string.decode(entry.getEncoding())
                if version:
                    break

        # repoNameWithOwner
        prefix = "https://github.com/"
        suffix = ".git"
        repoNameWithOwner: typing.Union[None, str] = None
        if metadata.source.repository_url.startswith(prefix):
            repoNameWithOwner = "/".join(
                metadata.source.repository_url[len(prefix) :].split("/")[0:2]
            )
            if repoNameWithOwner.endswith(suffix):
                repoNameWithOwner = repoNameWithOwner[: -len(suffix)]
        commit_url: typing.Union[None, str] = None
        if repoNameWithOwner:
            commit_url = f"https://github.com/{repoNameWithOwner}/commit/{metadata.source.commit}"

        family_changes_dict["/".join(dir_path_tuple)] = {
            "family_name": metadata.name,
            "repository": metadata.source.repository_url,
            "commit": metadata.source.commit,
            "version": version or "(unknown version)",
            "repoNameWithOwner": repoNameWithOwner,
            "commit_url": commit_url,
        }
    return family_changes_dict


def _title_message_from_diff(
    repo: pygit2.Repository, root_tree: pygit2.Tree, tip_tree: pygit2.Tree
) -> typing.Tuple[str, str]:
    family_changes_dict = _get_change_info_from_diff(repo, root_tree, tip_tree)
    title = []
    body = []
    for _, fam_entry in family_changes_dict.items():
        title.append(f'{fam_entry["family_name"]}: {fam_entry["version"]} added')
        commit = fam_entry["commit_url"] or fam_entry["commit"]
        body.append(
            f'* {fam_entry["family_name"]} '
            f'{fam_entry["version"]} taken from the upstream repo '
            f'{fam_entry["repository"]} at commit {commit}.'
        )
    return "; ".join(title), "\n".join(body)


def _git_make_commit(
    repo: pygit2.Repository,
    add_commit: bool,
    force: bool,
    local_branch: str,
    remote_name: str,
    base_remote_branch: str,
    tmp_package_family_dir: str,
    family_dir: str,
):
    base_commit = None
    if add_commit:
        try:
            base_commit = repo.branches.local[local_branch].peel()
        except KeyError:
            pass

    if not base_commit:
        # fetch! make sure we're on the actual gf main HEAD
        git_fetch_main(repo, remote_name)
        # base_commit = repo.revparse_single(f'refs/remotes/{base_remote_branch}')
        # same but maybe better readable:
        base_commit = repo.branches.remote[base_remote_branch].peel()

    # Maybe I can start with the commit tree here ...
    treeBuilder = repo.TreeBuilder(base_commit.tree)
    git_copy_dir(repo, treeBuilder, tmp_package_family_dir, family_dir)

    # create the commit
    user_name = list(repo.config.get_multivar("user.name"))[0]
    user_email = list(repo.config.get_multivar("user.email"))[0]
    author = pygit2.Signature(user_name, user_email)
    committer = pygit2.Signature(user_name, user_email)

    new_tree_id = treeBuilder.write()
    new_tree: pygit2.Tree = repo.get(new_tree_id)
    title, body = _title_message_from_diff(repo, base_commit.tree, new_tree)

    commit_id = repo.create_commit(
        None,
        author,
        committer,
        f"[gftools-packager] {title}\n\n{body}",
        new_tree_id,
        [base_commit.id],  # parents
    )

    commit = repo.get(commit_id)
    # create branch or add to an existing one if add_commit
    try:
        repo.branches.local.create(local_branch, commit, force=add_commit or force)
    except pygit2.AlreadyExistsError:
        raise UserAbortError(
            f"Can't override existing branch {local_branch}. "
            "Use --branch to specify another branch name. "
            "Use --force to allow explicitly."
        )

    # only for reporting
    target_label = f"git branch {local_branch}"
    package_contents = []
    for root, dirs, files in git_tree_walk(family_dir, commit.tree):
        for filename in files:
            entry_name = os.path.join(root, filename)
            filesize = commit.tree[entry_name].size
            package_contents.append((entry_name, filesize))
    _print_package_report(target_label, package_contents)


def _package_to_git(
    tmp_package_family_dir: str,
    target: str,
    family_dir: str,
    branch: str,
    force: bool,
    add_commit: bool,
) -> None:

    repo = pygit2.Repository(target)
    # we checked that it exists earlier!
    remote_name = find_github_remote(repo, "google", "fonts", "main")
    base_remote_branch = f"{remote_name}/main"
    if remote_name is None:
        raise Exception("No remote found for google/fonts main.")

    _git_make_commit(
        repo,
        add_commit,
        force,
        branch,
        remote_name,
        base_remote_branch,
        tmp_package_family_dir,
        family_dir,
    )


def _dispatch_git(
    target: str, target_branch: str, pr_upstream: str, push_upstream: str
) -> None:
    repo = pygit2.Repository(target)
    # we checked that it exists earlier!
    remote_name = find_github_remote(repo, "google", "fonts", "main")
    base_remote_branch = f"{remote_name}/main"
    if remote_name is None:
        raise Exception("No remote found for google/fonts main.")

    git_branch: pygit2.Branch = repo.branches.local[target_branch]
    tip_commit: pygit2.Commit = git_branch.peel()
    root_commit: pygit2.Commit = get_root_commit(repo, base_remote_branch, tip_commit)
    pr_title, _ = _title_message_from_diff(repo, root_commit.tree, tip_commit.tree)
    if not pr_title:
        # Happens e.g. if we have a bunch of commits that revert themselves,
        # to me this happened in development, in a for production use very unlikely
        # situation.
        # But can also happen if we PR commits that don't do changes in family
        # dirs. In these cases the PR author should probably come up with a
        # better title than this placeholder an change it in the GitHub web-GUI.
        pr_title = "(UNKNOWN gftools-packager: found no family changes)"

    current_commit = tip_commit
    messages = []
    while current_commit.id != root_commit.id:
        messages.append(f" {current_commit.short_id}: {current_commit.message}")
        current_commit = current_commit.parents[0]
    pr_message_body = "\n\n".join(reversed(messages))

    _make_pr(repo, target_branch, pr_upstream, push_upstream, pr_title, pr_message_body)


def _package_to_dir(
    tmp_package_family_dir: str,
    target: str,
    family_dir: str,
    force: bool,
):
    # target is a directory:
    target_family_dir = os.path.join(target, family_dir)
    if os.path.exists(target_family_dir):
        if not force:
            raise UserAbortError(
                "Can't override existing directory "
                f"{target_family_dir}. "
                "Use --force to allow explicitly."
            )
        shutil.rmtree(target_family_dir)
    else:  # not exists
        os.makedirs(os.path.dirname(target_family_dir), exist_ok=True)
    shutil.move(tmp_package_family_dir, target_family_dir)

    # only for reporting
    target_label = f"directory {target}"
    package_contents = []
    for root, dirs, files in os.walk(target_family_dir):
        for filename in files:
            full_path = os.path.join(root, filename)
            entry_name = os.path.relpath(full_path, target)
            filesize = os.path.getsize(full_path)
            package_contents.append((entry_name, filesize))
    print(f"Package Directory: {target_family_dir}")
    _print_package_report(target_label, package_contents)


def _branch_name_from_family_dirs(family_dirs: typing.List[str]) -> str:
    if len(family_dirs) == 1:
        return f'{GIT_NEW_BRANCH_PREFIX}{family_dirs[0].replace(os.sep, "_")}'

    by_licensedir: typing.Dict[str, typing.List[str]] = {}
    for f in family_dirs:
        license_dir = os.path.dirname(f)
        if license_dir not in by_licensedir:
            by_licensedir[license_dir] = []
        by_licensedir[license_dir].append(os.path.basename(f))

    # All the sorting is to achieve the same branch name, when
    # family_dirs comes in a different order but with the same content.
    particles = []
    for license_dir, families in by_licensedir.items():
        particles.append(f'{license_dir}_{"-".join(sorted(families))}')

    # Could be like (in an extreme case):
    # gftools_packager_apache_arimo-cherrycreamsoda_ofl_acme-balsamiqsans-librebarcode39extendedtext
    full_branch_name = f'{GIT_NEW_BRANCH_PREFIX}{"_".join(sorted(particles))}'
    # I don't know hard limits here
    max_len = 60
    if len(full_branch_name) <= max_len:
        return full_branch_name
    hash_hex_ini = sha1(full_branch_name.encode("utf-8")).hexdigest()[:10]
    # This is the shortened version from above:
    # gftools_packager_apache_arimo-cherrycreamsoda_ofl_d79615d347
    return f"{full_branch_name[:max_len-11]}_{hash_hex_ini}"


def _file_or_family_is_file(file_or_family: str) -> bool:
    return file_or_family.endswith(".yaml") or file_or_family.endswith(
        ".yml"
    )  # .yml is common, too


def make_package(args: argparse.Namespace):
    is_git = args.subcommand == "package-git"
    # Basic early checks. Raises if target does not qualify.
    if is_git:
        _check_git_target(args.gf_git)
    else:
        _check_directory_target(args.directory)

    family_dirs: typing.List[str] = []
    with TemporaryDirectory() as tmp_dir:
        tmp_package_dir = os.path.join(tmp_dir, "packages")
        os.makedirs(tmp_package_dir, exist_ok=True)
        tmp_repos_dir = os.path.join(tmp_dir, "repos")
        os.makedirs(tmp_repos_dir, exist_ok=True)

        for file_or_family in args.file_or_families:
            if _file_or_family_is_file(file_or_family):
                file = file_or_family
                family_name = None
            else:
                file = None
                family_name = file_or_family
            (
                upstream_conf,
                license_dir,
                gf_dir_content,
            ) = get_upstream_info(file, family_name)
            assert isinstance(upstream_conf, UpstreamConfig)
            assert isinstance(license_dir, str)
            try:
                family_dir = _create_package_content(
                    tmp_package_dir,
                    tmp_repos_dir,
                    upstream_conf,
                    license_dir,
                    gf_dir_content,
                    False,
                    args.no_allowlist,
                )
                family_dirs.append(family_dir)
            except Exception:
                error_io = StringIO()
                traceback.print_exc(file=error_io)
                error_io.seek(0)
                upstream_yaml_backup_filename = upstream_conf.save_backup()
                print(
                    f"Upstream conf caused an error:"
                    f"\n-----\n\n{error_io.read()}\n-----\n"
                    f"Upstream conf has been saved to: {upstream_yaml_backup_filename}"
                )
                raise UserAbortError()
        if not family_dirs:
            print("No families to package.")
        # done with collecting data for all file_or_families

        if is_git and not args.branch:
            args.branch = _branch_name_from_family_dirs(family_dirs)

        for i, family_dir in enumerate(family_dirs):
            tmp_package_family_dir = os.path.join(tmp_package_dir, family_dir)
            # NOTE: if there are any files outside of family_dir that need moving
            # that is not yet supported! The reason is, there's no case for this
            # yet. So, if _create_package_content is changed to put files outside
            # of family_dir, these targets will have to follow and implement it.
            if is_git:
                if i > 0:
                    args.add_commit = True
                _package_to_git(
                    tmp_package_family_dir,
                    args.gf_git,
                    family_dir,
                    args.branch,
                    args.force,
                    args.add_commit,
                )
            else:
                _package_to_dir(
                    tmp_package_family_dir, args.directory, family_dir, args.force
                )

    if is_git and args.pr:
        _dispatch_git(args.gf_git, args.branch, args.pr_upstream, args.push_upstream)


def _print_package_report(
    target_label: str, package_contents: typing.List[typing.Tuple[str, int]]
) -> None:
    print(f"Created files in {target_label}:")
    for entry_name, filesize in package_contents:
        filesize_str = filesize
        print(f"   {entry_name} {humanize.naturalsize(filesize_str)}")
