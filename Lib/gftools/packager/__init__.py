from __future__ import annotations

import filecmp
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
import requests
import sys
from typing import List, Optional, Tuple
from zipfile import ZipFile

import yaml
from fontTools.ttLib import TTFont
from gflanguages import LoadLanguages
import pygit2
from pygit2 import (
    GIT_RESET_HARD,
    GIT_RESET_SOFT,
    Branch,
    Repository,
    GIT_RESET_MIXED,
    TreeBuilder,
)
from pygit2.enums import FileStatus

import gftools.fonts_public_pb2 as fonts_pb2
from gftools.gfgithub import GitHubClient
from gftools.scripts.add_font import main as add_font
from gftools.util import google_fonts as fonts
from gftools.utils import (
    download_file,
    is_google_fonts_repo,
    Google_Fonts_has_family,
    has_gh_token,
)
from gftools.packager.build import build_to_directory
import sys
from gftools.push.trafficjam import TRAFFIC_JAM_ID


log = logging.getLogger("gftools.packager")
LOG_FORMAT = "%(message)s"


SOURCE_TEMPLATE = """source {
  repository_url: "https://github.com/user/repo"
 # archive_url: "https://github.com/user/repo/family.zip"
  branch: "main"
  files {
    source_file: "OFL.txt"
    dest_file: "OFL.txt"
  }
  files {
    source_file: "fonts/variable/MyFont[wght].ttf"
    dest_file: "MyFont[wght].ttf"
  }
}
"""

DISPLAY_TEMPLATE = """# stroke: "SANS_SERIF"
# classifications: "DISPLAY"
# primary_script: "Deva"
# minisite_url: "https://www.myfont.com"
"""

TEMPLATE = """name: "{name}"
designer: "UNKNOWN"
license: "OFL"
category: "SANS_SERIF"
date_added: "{date}"
{source_template}
{display_template}
subsets: "menu"
"""

PR_CHECKLIST = """
## PR Checklist:

- [ ] `minisite_url` definition in the METADATA.pb file for commissioned projects
- [ ] `tags` are added for NEW FONTS
- [ ] `primary_script` definition in the METADATA.pb file for all projects that have a primary non-Latin based language support target
- [ ] `subsets` definitions in the METADATA.pb reflect the actual subsets and languages present in the font files (in alphabetic order). For **CJK fonts**, only include one of the following subsets `chinese-hongkong`, `chinese-simplified`, `chinese-traditional`, `korean`, `japanese`.
- [ ] Fontbakery checks are reviewed and failing checks are resolved in collaboration with the upstream font development team
- [ ] Diffenator2 regression checks for revisions on all projects that are currently in production
- [ ] Designers bio info have to be present in the designer catalog (at least an issue should be opened for tracking this, if they are not)
- [ ] Check designers order in metadata.pb, since the first one of the list appears as “principal designer”
- [ ] Social media formatted visual assets for all new commissioned projects in the Drive directory, communicate with the repository Maintainer so that they can push this content to the Social Media tracker spreadsheet
- [ ] Social media content draft for all new commissioned projects in the Drive directory and Social Media tracker spreadsheet, communicate with the repository Maintainer so that they can push this content to the Social Media tracker spreadsheet
"""


ADD_TO_TRAFFIC_JAM = """
  mutation {{
    addProjectV2ItemById(
        input: {{
            projectId: "{project_id}"
            contentId: "{content_id}"
        }}
    ) {{
        item {{
        id
      }}
    }}
  }}
"""


def create_metadata(fp: Path, family_name: str, license: str = "ofl"):
    """create a family dir in google/fonts repo with a placeholder
    METADATA.pb file"""
    family_dir_name = get_family_dir(family_name)
    family_fp = Path(fp / license / family_dir_name)
    os.makedirs(family_fp, exist_ok=True)

    metadata_fp = family_fp / "METADATA.pb"
    with open(metadata_fp, "w") as doc:
        doc.write(
            TEMPLATE.format(
                name=family_name,
                date=time.strftime("%Y-%m-%d"),
                source_template=SOURCE_TEMPLATE,
                display_template=DISPLAY_TEMPLATE,
            )
        )
    return metadata_fp


def expected_source(file: str) -> str:
    """Provide a good guess at where at file is located in a repo."""
    if file.endswith(".ttf"):
        if "[" in file and "]" in file:
            return f"fonts/variable/{file}"
        else:
            return f"fonts/ttf/{file}"
    if file.endswith(".html"):
        return f"documentation/{file}"
    # License etc.
    return file


def append_source_template(metadata_fp: Path, metadata: fonts_pb2.FamilyProto):
    """Add source template to METADATA.pb file if it's missing. It needs
    to be populated by hand."""
    if len(metadata.fonts) > 0:
        files = [font.filename for font in metadata.fonts]
        if metadata.license == "OFL":
            files.append("OFL.txt")
        else:
            files.append("LICENSE.txt")
        files.append("DESCRIPTION.en_us.html")
        for file in files:
            item = fonts_pb2.SourceFileProto()
            item.source_file = expected_source(file)
            item.dest_file = file
            metadata.source.files.append(item)
        metadata.source.repository_url = "https://www.github.com/user/repo"
        metadata.source.branch = "main"
        fonts.WriteMetadata(metadata, metadata_fp, comments=None)
        return
    with open(metadata_fp, "r") as doc:
        text = doc.read()
    text += "\n" + SOURCE_TEMPLATE
    with open(metadata_fp, "w") as doc:
        doc.write(text)


def no_source_metadata(metadata: fonts_pb2.FamilyProto):
    """Check if a metadata file has source info."""
    if not metadata.source.files or not metadata.source.repository_url:
        return True
    return False


def incomplete_source_metadata(metadata: fonts_pb2.FamilyProto):
    """Check if a metadata file hasn't been completed."""
    if metadata.source.repository_url == "https://www.github.com/user/repo":
        return True
    return False


def load_metadata(fp: "Path | str"):
    """Load METADATA.pb file and merge in upstream.yaml data if they exist."""
    # upstream.yaml files are legacy since FamilyProto now contains all
    # the necceary source fields.
    if isinstance(fp, str):
        fp = Path(fp)
    metadata = fonts.ReadProto(fonts_pb2.FamilyProto(), fp)

    upstream_yaml_fp = fp.parent / "upstream.yaml"
    if upstream_yaml_fp.exists():
        log.info("Merging upstream.yaml into METADATA.pb")
        with open(upstream_yaml_fp, "r", encoding="utf-8") as doc:
            data = yaml.safe_load(doc)
            if "repository_url" in data:
                metadata.source.repository_url = data["repository_url"]
            if "archive" in data and data["archive"]:
                metadata.source.archive_url = data["archive"]
            if "branch" in data:
                metadata.source.branch = data["branch"]
            if "files" in data:
                for src, dst in data["files"].items():
                    item = fonts_pb2.SourceFileProto()
                    item.source_file = src
                    item.dest_file = dst
                    metadata.source.files.append(item)
    return metadata


def save_metadata(fp: Path, metadata: fonts_pb2.FamilyProto):
    """Save METADATA.pb file and delete old upstream.yaml file."""
    github = GitHubClient.from_url(metadata.source.repository_url)
    commit = github.get_commit(metadata.source.branch)
    git_commit = commit["sha"]
    metadata.source.commit = git_commit
    fonts.WriteMetadata(metadata, fp)

    add_font([str(fp.parent)])

    # Remove redundant upstream.yaml file
    upstream_yaml_fp = fp / "upstream.yaml"
    if upstream_yaml_fp.exists():
        log.info("Removing redundant upstream.yaml file")
        os.remove(upstream_yaml_fp)


def get_family_dir(family_name: str) -> str:
    # Maven Pro -> mavenpro
    return family_name.replace(" ", "").lower()


def find_family_in_repo(family_name: str, repo_path: Path) -> Optional[Path]:
    """Find a family dir in the google/fonts repo."""
    family_dir_name = get_family_dir(family_name)
    for license in ("ofl", "ufl", "apache"):
        fp = Path(repo_path / license / family_dir_name)
        if fp.exists():
            log.info(f"Found '{fp}'")
            return fp
    return None


def download_assets(
    metadata: fonts_pb2.FamilyProto, out: Path, latest_release: bool = False
) -> List[str]:
    """Download assets listed in the metadata's source field"""
    upstream = GitHubClient.from_url(metadata.source.repository_url)
    res = []
    # Getting files from an archive always takes precedence over a
    # repo dir
    if latest_release or metadata.source.archive_url:
        if latest_release:
            release = upstream.get_latest_release()
            metadata.source.archive_url = release["assets"][0]["browser_download_url"]
        z = download_file(metadata.source.archive_url)

        zf = ZipFile(z)
        for item in metadata.source.files:
            out_fp = Path(out / item.dest_file)
            if not out_fp.parent.exists():
                os.makedirs(out_fp.parent, exist_ok=True)
            found = False
            for file in zf.namelist():
                if file.endswith(item.source_file):
                    if found:
                        log.error(
                            f"Found '{item.source_file}' more than once in archive '{metadata.source.archive_url}'"
                        )
                        continue
                    found = True
                    with open(out_fp, "wb") as f:
                        f.write(zf.read(file))
            if not found:
                raise ValueError(
                    f"Could not find '{item.source_file}' in archive '{metadata.source.archive_url}'"
                )
            res.append(out_fp)
        return res

    for item in metadata.source.files:
        log.debug(f"Downloading {item.source_file}")
        try:
            file_content = upstream.get_content(
                f"{item.source_file}", metadata.source.branch
            )
        except requests.exceptions.HTTPError:
            raise ValueError(
                f"Could not find '{item.source_file}' in repository's "
                f"'{metadata.source.branch}' branch.\n\nPlease check the file "
                "is in the repo and the branch name is correct."
            )
        out_fp = Path(out / item.dest_file)
        if not out_fp.parent.exists():
            os.makedirs(out_fp.parent, exist_ok=True)
        with open(out_fp, "wb") as item:
            item.write(file_content.content)
        res.append(out_fp)
    return res


def assets_are_same(src: Path, dst: Path) -> bool:
    """Check if the assets in src and dst dirs are the same."""
    files_to_compare = []
    for dirpath, _, filenames in os.walk(src):
        for filename in filenames:
            if ".DS_Store" in filename:
                continue
            path = os.path.join(dirpath, filename)
            files_to_compare.append(os.path.relpath(path, src))

    match, mismatch, errors = filecmp.cmpfiles(src, dst, files_to_compare)
    log.debug(
        "repo vs upstream files:\n"
        f"matched: f{match}\n"
        f"mismatched: f{mismatch}\n"
        f"errors (don't exist): f{errors}"
    )
    if mismatch or errors:
        return False
    return True


def package_family(
    family_path: Path,
    metadata: fonts_pb2.FamilyProto,
    latest_release=False,
    build_from_source=False,
    their_venv=False,
    **kwargs,
):
    """Create a family into a google/fonts repo."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        if build_from_source:
            log.info(f"Building '{metadata.name}' from source")
            build_to_directory(tmp_dir, family_path, metadata, their_venv=their_venv)
        else:
            log.info(f"Downloading family to '{family_path}'")
            download_assets(metadata, tmp_dir, latest_release)
        if assets_are_same(tmp_dir, family_path):
            raise ValueError(f"'{family_path}' already has latest files, Aborting.")
        # rm existing fonts. Sometimes the font count will change if a family
        # increases its styles or becomes a variable font.
        for fp in family_path.iterdir():
            if fp.suffix == ".ttf":
                os.remove(fp)
        shutil.copytree(tmp_dir, family_path, dirs_exist_ok=True)
        save_metadata(family_path / "METADATA.pb", metadata)
        # Format HTML
        desc_file = family_path / "DESCRIPTION.en_us.html"
        article_file = family_path / "article" / "ARTICLE.en_us.html"
        if article_file.exists():
            # Remove description file if an article already exists
            if desc_file.exists() and not metadata.is_noto:
                os.remove(desc_file)
            about_file = article_file
        else:
            about_file = desc_file
        with open(about_file, encoding="utf-8") as fin:
            about = fin.read()
        with open(about_file, "w", encoding="utf-8") as fout:
            fout.write(about)
    return True


def _git_branch_name(family_name: str, license: str) -> str:
    license = license.lower()
    family_dir_name = get_family_dir(family_name)
    return f"gftools_packager_{license}_{family_dir_name}"


def create_git_branch(
    metadata: fonts_pb2.FamilyProto, repo: Repository, head_repo
) -> Branch:
    branch_name = _git_branch_name(metadata.name, metadata.license)
    # create a branch by from the head main branch
    is_ssh = "git@" in subprocess.check_output(
        ["git", "-C", str(repo.workdir), "remote", "-v"]
    ).decode("-utf-8")
    if is_ssh:
        repo_url = f"git@github.com:{head_repo}/fonts.git"
    else:
        repo_url = f"https://github.com/{head_repo}/fonts.git"
    result = subprocess.run(
        [
            "git",
            "-C",
            repo.workdir,
            "pull",
            repo_url,
            f"main:{branch_name}",
            "--force",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    branch = repo.branches.get(branch_name)
    if not branch:
        raise ValueError(
            "Could not create a git branch "
            + branch_name
            + ": \n"
            + result.stderr.decode("utf-8")
        )
    return branch


def git_tree_traverse(func, *args, **kwargs):
    def traverse(
        repo: Repository, treebuilder: TreeBuilder, path: str, *args, **kwargs
    ):
        path_parts = path.split("/", 1)
        if len(path_parts) == 1:  # base case
            return func(repo, treebuilder, path, *args, **kwargs)

        subtree_name, sub_path = path_parts
        tree_oid = treebuilder.write()
        tree = repo.get(tree_oid)
        try:
            entry = tree[subtree_name]
            existing_subtree = repo.get(entry.id)
            sub_treebuilder = repo.TreeBuilder(existing_subtree)
        except KeyError:
            sub_treebuilder = repo.TreeBuilder()
        subtree_oid = traverse(repo, sub_treebuilder, sub_path, *args, **kwargs)
        treebuilder.insert(subtree_name, subtree_oid, pygit2.GIT_FILEMODE_TREE)
        return treebuilder.write()

    return traverse


@git_tree_traverse
def git_add_file(
    repo: Repository, treebuilder: TreeBuilder, path: str, *args, **kwargs
):
    treebuilder.insert(path, kwargs["blob"], pygit2.GIT_FILEMODE_BLOB)
    return treebuilder.write()


@git_tree_traverse
def git_rm_file(repo: Repository, treebuilder: TreeBuilder, path: str, *args, **kwargs):
    treebuilder.remove(path)
    return treebuilder.write()


def commit_family(
    branch,
    family_path: Path,
    metadata: fonts_pb2.FamilyProto,
    repo: Repository,
    head_repo="google",
    issue_number=None,
) -> Tuple[str, str, Branch]:
    """Commit family to a new branch in the google/fonts repo."""
    log.info(
        f"Committing family to branch '{_branch_name(branch.name)}'. "
        "Please make hand modifications to the family on this branch. "
        "Be aware that hand modifying files that are included in the METADATA.pb "
        "will get overwritten if you rerun the tool."
    )

    family_name = metadata.name
    fonts = list(family_path.glob("*.ttf"))
    version = TTFont(fonts[0])["name"].getName(5, 3, 1, 0x409).toUnicode()

    title = f"{family_name}: {version} added\n\n"
    commit = f"{metadata.source.repository_url}/commit/{metadata.source.commit}"
    body = (
        f"Taken from the upstream repo {metadata.source.repository_url} at "
        f"commit {commit}."
    )
    if issue_number:
        body += f"\n\nResolves #{issue_number}"
    msg = f"{title}\n\n{body}"

    ref = branch.name
    parents = [branch.target]

    tree_builder = repo.TreeBuilder(branch.peel().tree_id)
    for fp, file_status in repo.status().items():
        fp = Path(fp)
        if family_path.relative_to(repo.workdir) not in fp.parents:
            continue

        if file_status in [FileStatus.WT_MODIFIED, FileStatus.WT_NEW]:
            blob = repo.create_blob_fromworkdir(fp)
            git_add_file(repo, tree_builder, str(fp), blob=blob)
        elif file_status == FileStatus.WT_DELETED:
            git_rm_file(repo, tree_builder, str(fp))
        else:
            raise ValueError(f"Unknown file status: {file_status}")

    tree = tree_builder.write()
    author = repo.default_signature
    repo.create_commit(ref, author, author, msg, tree, parents)
    return title, body, branch


def _branch_name(branch: str) -> str:
    # refs/heads/main -> main
    return os.path.basename(branch)


def push_family(family_path: Path, branch_name: str, head_repo: str):
    # Use subprocess since getting credentials with pygit2 is a pita
    log.info(f"Pushing '{_branch_name(branch_name)}' to '{head_repo}/fonts'")
    is_ssh = "git@" in subprocess.check_output(
        ["git", "-C", str(family_path), "remote", "-v"]
    ).decode("-utf-8")
    if is_ssh:
        repo_url = f"git@github.com:{head_repo}/fonts.git"
    else:
        repo_url = f"https://github.com/{head_repo}/fonts.git"
    subprocess.run(
        [
            "git",
            "-C",
            family_path,
            "push",
            repo_url,
            f"{branch_name}:{branch_name}",
            "--force",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def pr_family(
    branch_name: str,
    family_path: Path,
    title: str,
    body: str,
    family_name: str,
    base_repo: str = "google",
    head_repo: str = "google",
    issue_number=None,
):
    push_family(family_path, branch_name, head_repo)
    google_fonts = GitHubClient(base_repo, "fonts")
    pr_head = f"{head_repo}:{branch_name}"
    open_prs = google_fonts.open_prs(pr_head, "main")
    if not open_prs:
        body += PR_CHECKLIST
        resp = google_fonts.create_pr(title, body, pr_head, "main")
        log.info(f"Created PR '{resp['html_url']}'")
        # Add PR label
        # fetch open prs again since we've just created one
        open_prs = google_fonts.open_prs(pr_head, "main")
        if Google_Fonts_has_family(family_name):
            google_fonts.add_labels(open_prs[0]["number"], ["I Font Upgrade"])
        else:
            google_fonts.add_labels(open_prs[0]["number"], ["I New Font"])
    else:
        resp = google_fonts.create_issue_comment(open_prs[0]["number"], "Updated")
        google_fonts.update_pr(open_prs[0]["number"], title=title)
        log.info(f"Updated PR '{resp['html_url']}'")

    # inherit labels from issue
    if issue_number:
        issue_labels = google_fonts.get_labels(issue_number)
        google_fonts.add_labels(
            open_prs[0]["number"], [l["name"] for l in issue_labels]
        )
    # add item to traffic board
    if TRAFFIC_JAM_ID and not open_prs:
        log.info(f"Adding project to traffic jam")
        google_fonts._run_graphql(
            ADD_TO_TRAFFIC_JAM.format(
                project_id=TRAFFIC_JAM_ID,
                content_id=resp["node_id"],
            ),
            {},
        )
    return True


@contextmanager
def current_git_state(repo: Repository, family_path):
    """Stash current git state and restore it after the context is done."""
    stashed = False
    try:
        try:
            log.debug("Stashing current git state")
            repo.stash(repo.default_signature, "WIP: stashing")
            stashed = True
        except:
            pass
        yield True
    finally:
        log.debug("Restoring previous git state")
        shutil.rmtree(family_path, ignore_errors=True)
        repo.reset(repo.head.target, GIT_RESET_HARD)
        if stashed:
            repo.stash_pop()


def make_package(
    repo_path: "str | Path",
    family_name: str,
    license: str = "ofl",
    skip_tags: bool = False,
    pr: bool = True,
    base_repo: str = "google",
    head_repo: str = "google",
    latest_release: bool = False,
    build_from_source: bool = False,
    issue_number=None,
    **kwargs,
):
    if skip_tags:
        log.warning(
            f"skip_tags is deprecated since we now have a tagging webapp, "
            "https://google.github.io/fonts/tags.html"
        )
    if pr and not has_gh_token():
        raise ValueError(
            f"Tool requires 'GH_TOKEN' environment variable in order to make "
            "the pull request."
        )
    repo = Repository(repo_path)
    repo_path = Path(repo.workdir)
    if not is_google_fonts_repo(repo_path):
        raise ValueError(f"{repo_path} is not a path to a valid google/fonts repo")

    if family_name.endswith(".pb"):
        metadata_fp = Path(family_name)
        metadata = load_metadata(metadata_fp)
        family_path = find_family_in_repo(metadata.name, repo_path)
        if not family_path:
            family_path = Path(repo_path / license / get_family_dir(metadata.name))
            os.makedirs(family_path, exist_ok=True)
    else:
        family_path = find_family_in_repo(family_name, repo_path)  # type: ignore
        if not family_path:
            # get files from branch if they exist
            branch_name = _git_branch_name(family_name, license)
            family_branch = repo.lookup_branch(branch_name)
            if family_branch:
                metadata_path = Path(
                    repo_path / license / get_family_dir(family_name) / "METADATA.pb"
                )
                repo.checkout(
                    family_branch, paths=[metadata_path.relative_to(repo.workdir)]
                )
                log.warning(
                    f"Found '{metadata_path}' in branch '{branch_name}'. The file has "
                    "been moved into the main branch.\nMake your modifications to this "
                    "file and rerun tool with same commands."
                )
                repo.reset(repo.head.target, GIT_RESET_MIXED)
            else:
                metadata_path = create_metadata(repo_path, family_name, license)
                log.warning(
                    f"No family was found in repository!\n\nI've created "
                    f"'{metadata_path}'.\nPlease populate the file and rerun tool "
                    "with the same commands."
                )
            return
        metadata_fp = family_path / "METADATA.pb"
        metadata = load_metadata(metadata_fp)

    # Ensure the family's METADATA.pb file has the required source fields
    if no_source_metadata(metadata):
        append_source_template(metadata_fp, metadata)
        raise ValueError(
            f"'{metadata_fp}' lacks source info! Please populate the "
            "updated METADATA.pb file and rerun tool with the "
            "same commands."
        )

    if incomplete_source_metadata(metadata):
        raise ValueError(
            f"'{metadata_fp}' Please fill in the source placeholder fields "
            "in the METADATA.pb file and rerun tool with the same commands."
        )

    with current_git_state(repo, family_path):
        branch = create_git_branch(metadata, repo, head_repo)
        packaged = package_family(
            family_path, metadata, latest_release, build_from_source, **kwargs
        )
        title, msg, branch = commit_family(
            branch, family_path, metadata, repo, head_repo, issue_number
        )

        if pr:
            pr_family(
                branch.name,
                family_path,
                title,
                msg,
                metadata.name,
                base_repo,
                head_repo,
                issue_number,
            )
            log.info(
                f"\nPR submitted to google/fonts repo!\n\n"
                "Please ensure the checklist supplied in the PR is completed"
            )
