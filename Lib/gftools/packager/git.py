# This module contains generic (non-GF specific) routines for
# driving pygit2 to do various git-tree-related tasks.

import pygit2
import os
import subprocess
from pathlib import PurePath
import typing
from .constants import GITHUB_REPO_SSH_URL


def _git_tree_iterate(path, tree, topdown):
    dirs = []
    files = []
    for e in tree:
        if e.type == pygit2.GIT_OBJ_TREE:
            dirs.append(e.name)
        elif e.type == pygit2.GIT_OBJ_BLOB:
            files.append(e.name)
    if topdown:
        yield path and os.path.join(*path) or ".", dirs, files
    # note, if topdown, caller can manipulate dirs
    for name in dirs:
        path.append(name)
        yield from _git_tree_iterate(path, tree[name], topdown)
        path.pop()
    if not topdown:
        yield path and os.path.join(*path) or ".", dirs, files


def git_tree_walk(path, tree, topdown=True):
    yield from _git_tree_iterate(path.split(os.sep), tree[path], topdown)


def shallow_clone_git(target_dir, git_url, branch_or_tag="main"):
    """
    getting this as a shallow copy, because for some files we want to
    search in the filesystem.

    branch_or_tag: as used in `git clone -b`

    NOTE: libgit2 and hence pygit2 doesn't support shallow clones yet,
    but that's the most lightweight way to get the whole directory
    structure.
    """

    # I don't understand why git clone doesn't take this more explicit form.
    # But, I recommended it in the docs, so here's a little fix.
    if branch_or_tag.startswith("tags/"):
        branch_or_tag = branch_or_tag[len("tags/") :]

    return subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--bare",
            "-b",
            branch_or_tag,
            git_url,
            target_dir,
        ],
        check=True,
        stdout=subprocess.PIPE,
    )


def git_push(
    repo: pygit2.Repository,
    url: str,
    local_branch_name: str,
    remote_branch_name: str,
    force: bool,
):
    full_local_ref = (
        local_branch_name
        if local_branch_name.find("refs/") == 0
        else f"refs/heads/{local_branch_name}"
    )
    full_remote_ref = f"refs/heads/{remote_branch_name}"
    ref_spec = f"{full_local_ref}:{full_remote_ref}"
    if force:
        # ref_spec for force pushing must include a + at the start.
        ref_spec = f"+{ref_spec}"

    # NOTE: pushing using pygit2 is currently not working on MacOS, this is
    # related to SSH issues. Here's a traceback:
    #                   https://github.com/googlefonts/gftools/issues/238
    # Since we did it already once with `git clone --depth 1`, this is also
    # being worked around by using the CLI git directly.
    #
    # callbacks = PYGit2RemoteCallbacks()
    # with _create_tmp_remote(repo, url) as remote:
    #   # https://www.pygit2.org/remotes.html#pygit2.Remote.push
    #   # When the remote has a githook installed, that denies the reference
    #   # this function will return successfully. Thus it is strongly recommended
    #   # to install a callback, that implements RemoteCallbacks.push_update_reference()
    #   # and check the passed parameters for successfull operations.
    #
    #
    #   remote.push([ref_spec], callbacks=callbacks)
    subprocess.run(
        ["git", "push", url, ref_spec],
        cwd=repo.path,
        check=True,
        stdout=subprocess.PIPE,
    )

    # if callbacks.rejected_push_message is not None:
    #  raise Exception(callbacks.rejected_push_message)


def get_root_commit(
    repo: pygit2.Repository, base_remote_branch: str, tip_commit: pygit2.Commit
) -> pygit2.Commit:
    for root_commit in repo.walk(
        tip_commit.id, pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_TIME
    ):
        try:
            # If it doesn't raise KeyError i.e. root_commit is contained in
            # our base_remote_branch and not part of the PR.
            return repo.branches.remote.with_commit(root_commit)[
                base_remote_branch
            ].peel()
        except KeyError:
            continue
        break


def _git_get_path(tree: pygit2.Tree, path: str) -> pygit2.Object:
    last = tree
    for pathpart in PurePath(path).parts:
        last = last / pathpart
    return last


def find_github_remote(
    repo: pygit2.Repository,
    owner: str,
    name: str,
    branch: typing.Union[str, None] = None,
) -> typing.Union[str, None]:
    """
    Find a remote-name that is a good fit for the GitHub owner and repo-name.
    A good fit is when we can use it to fetch/push from/to GitHubs repository
    to/from the `branch` if branch is given or any branch if `branch` is None.

    Returns remote-name or None
    """
    searched_repo = f"{owner}/{name}"
    # If we plan to also push to these, it is important which
    # remote url we choose, esp. because of authentication methods.
    # I'd try to pick remotes after the order below, e.g. first the
    # ssh based urls, then the https url, because human users will
    # likely have a working ssh setup if they are pushing to github,
    # An environment like the FBD can have complete control over the
    # remotes it uses.
    # If more control is needed we'll have to add it.
    accepted_remote_urls = [
        GITHUB_REPO_SSH_URL(repo_name_with_owner=searched_repo),  # ssh
        f"ssh://git@github.com/{searched_repo}",  # ssh
        f"https://github.com/{searched_repo}.git",  # token (auth not needed for fetch)
    ]
    candidates = dict()  # url->remote

    # NOTE: a shallow cloned repository has no remotes.
    for remote in repo.remotes:
        if remote.url not in accepted_remote_urls or remote.url in candidates:
            continue
        # To be honest, we'll likely encounter the (default) first refspec case
        # in almost all matching remotes.
        accepted_refspecs = {f"+refs/heads/*:refs/remotes/{remote.name}/*"}
        if branch:
            accepted_refspecs.add(
                f"+refs/heads/{branch}:refs/remotes/{remote.name}/{branch}"
            )
        for refspec in remote.fetch_refspecs:
            if refspec in accepted_refspecs:
                # Could ask the user here if this remote should be used
                # but actually, the most common case will be that there's just
                # one that is good, and we're picking below from the ordered list
                # of accepted_remote_urls.
                candidates[remote.url] = remote
            # else Skipping refspec is probably insufficient.

    for url in accepted_remote_urls:
        if url in candidates:
            return candidates[url].name
    return None


class PYGit2RemoteCallbacks(pygit2.RemoteCallbacks):
    # this will be set if a push was rejected
    rejected_push_message: typing.Union[str, None] = None

    def push_update_reference(self, refname, message):

        """Push update reference callback. Override with your own function to
        report the remote’s acceptance or rejection of reference updates.

        refnamestr

            The name of the reference (on the remote).
        messagestr

            Rejection message from the remote. If None, the update was accepted.
        """
        if message is not None:
            self.rejected_push_message = (
                f"Update to reference {refname} got " f"rejected with message {message}"
            )

    def credentials(self, url, username_from_url, allowed_types):
        if allowed_types & pygit2.credentials.GIT_CREDENTIAL_USERNAME:
            print("GIT_CREDENTIAL_USERNAME")
            return pygit2.Username("git")
        elif allowed_types & pygit2.credentials.GIT_CREDENTIAL_SSH_KEY:
            # https://github.com/libgit2/pygit2/issues/428#issuecomment-55775298
            # "The username for connecting to GitHub over SSH is 'git'."

            # I filed https://github.com/libgit2/pygit2/issues/1013
            # because using just:
            #      return pygit2.Keypair(username_from_url, pubkey, privkey, '')
            # didn't work, there's also the example how I tried.

            # It's probably also what the user (the git command of the user)
            # does in this case and uses ssh-agent to do the auth
            #   return pygit2.Keypair(username_from_url, None, None, '')
            # There's a better readable shortcut (does the same):
            # If "git clone ..." works with an ssh remote, this should work
            # as well, no need to put configuration anywhere.
            return pygit2.KeypairFromAgent(username_from_url)
        else:
            return False

    # def sideband_progress(self, data):
    #   print(f'sideband_progress: {data}')
    #
    # # this works!
    # def transfer_progress(self, tp):
    #   print('transfer_progress:\n'
    #         f'  received_bytes {tp.received_bytes}\n'
    #         f'  indexed_objects {tp.indexed_objects}\n'
    #         f'  received_objects {tp.received_objects}')


def git_fetch_main(repo: pygit2.Repository, remote_name: str) -> None:

    # perform a fetch
    print(f"Start fetching {remote_name}/main")
    # fetch(refspecs=None, message=None, callbacks=None, prune=0)
    # using just 'main' instead of 'refs/heads/main' works as well

    # This fails on MacOS, just as any oother pygit2 network interaction.
    # remote = repo.remotes[remote_name]
    # stats = remote.fetch(['refs/heads/main'], callbacks=PYGit2RemoteCallbacks())

    subprocess.run(
        ["git", "fetch", remote_name, "main"],
        cwd=repo.path,
        check=True,
        stdout=subprocess.PIPE,
    )

    print("DONE fetch")  # {_sizeof_fmt(stats.received_bytes)} '
    # f'{stats.indexed_objects} receive dobjects!')


def _git_write_file(
    repo: pygit2.Repository, tree_builder: pygit2.TreeBuilder, file_path: str, data: str
) -> None:
    blob_id = repo.create_blob(data)
    return _git_makedirs_write(
        repo, tree_builder, PurePath(file_path).parts, blob_id, pygit2.GIT_FILEMODE_BLOB
    )


def _git_makedirs_write(
    repo: pygit2.Repository,
    tree_builder: pygit2.TreeBuilder,
    path: typing.Tuple[str, ...],
    git_obj_id: str,
    git_obj_filemode: int,
) -> None:
    name, rest_path = path[0], path[1:]
    if not rest_path:
        tree_builder.insert(name, git_obj_id, git_obj_filemode)
        return

    child_tree = tree_builder.get(name)
    try:
        child_tree_builder = repo.TreeBuilder(child_tree)
    except TypeError:
        # will raise TypeError if license_dir_tree is None i.e. not exisiting
        # but also if child_tree is not a pygit2.GIT_FILEMODE_TREE

        # os.makedirs(name, exists_ok=True) would raise FileExistsError if
        # it is tasked to create a directory where a file already exists
        # It seems unlikely that we want to override existing files here
        # so I copy that behavior.
        if child_tree is not None:
            # FileExistsError is an OSError so it's probably misused here
            raise FileExistsError(
                f"The git entry {name} exists as f{child_tree.type_str}."
            )
        child_tree_builder = repo.TreeBuilder()

    _git_makedirs_write(
        repo, child_tree_builder, rest_path, git_obj_id, git_obj_filemode
    )
    child_tree_id = child_tree_builder.write()
    tree_builder.insert(name, child_tree_id, pygit2.GIT_FILEMODE_TREE)


def git_copy_dir(
    repo: pygit2.Repository,
    tree_builder: pygit2.TreeBuilder,
    source_dir: str,
    target_dir: str,
) -> None:
    # This is a new tree, i.e. not based on an existing tree.
    tree_id = _git_tree_from_dir(repo, source_dir)

    # Here we insert into an existing tree.
    _git_makedirs_write(
        repo,
        tree_builder,
        PurePath(target_dir).parts,
        tree_id,
        pygit2.GIT_FILEMODE_TREE,
    )


def _git_tree_from_dir(repo: pygit2.Repository, tmp_package_family_dir: str) -> str:
    trees: typing.Dict[str, str] = {}
    for root, dirs, files in os.walk(tmp_package_family_dir, topdown=False):
        # if root == tmp_package_family_dir: rel_dir = '.'
        rel_dir = os.path.relpath(root, tmp_package_family_dir)
        treebuilder = repo.TreeBuilder()
        for filename in files:
            with open(os.path.join(root, filename), "rb") as f:
                blob_id = repo.create_blob(f.read())
            treebuilder.insert(filename, blob_id, pygit2.GIT_FILEMODE_BLOB)
        for dirname in dirs:
            path = dirname if rel_dir == "." else os.path.join(rel_dir, dirname)
            tree_id = trees[path]
            treebuilder.insert(dirname, tree_id, pygit2.GIT_FILEMODE_TREE)
        # store for use in later iteration, note, we're going bottom up
        trees[rel_dir] = treebuilder.write()
    return trees["."]
