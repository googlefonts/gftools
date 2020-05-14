
# FIXME: document dependencies, expect command line `git` with support
# for shallow clones

import os
from tempfile import TemporaryDirectory
from subprocess import run
import requests
import pprint

GIT_REPO_HTTPS_URL = 'https://github.com/{repo_name_with_owner}.git'.format
GIT_REPO_SSH_URL = 'git@github.com:{repo_name_with_owner}.git'.format





#how to build a package:
#
# Usually I would get the current files from google/fonts, not the ttfs
# Then override with the files from upstream and add the ttfs.
# But since it looks like getting the files from google/fonts is via
# single http requests per file in some cases, I think it's best to
# 1. get all relevant files from the upstream
# 2. get all files from google/fonts that are no already in the package (excluding ttfs again)
# 3. create or upgrade the METADATA.pb file
# 4. create or upgrade the upstream.yaml file (or whereever the data is located)
#    NOTE: that upstream.yaml is the beginning of all things, if it is not
#          available, we should create it


# get package base from google/fonts
# -- use a directory (maybe not necessary, only implement if easy AF)
# ++ use github http
# ++ use pygit2 if a clone is specified

# get files from upstream
# ++ use a directory (local qa iteration workflow, not necessarily commited and pushed)
# ++ use pygit2 (is shallow possible?) will only use committed stuff! could enforce using fetched remote)
#     this is for creating a PR to reduce human error (uncomitted changes)
#     so, could warn if there are not committed changes in the working directory
# -- (use github http): directory with shallow or pygit2 with shallow seems preferable

# when using remotes, we may not know the name of the remote of the
# current user, hence we should look for a remote with the correct git address
# that is the correct user/repo combination.
# we could expand to allow any git remote, not just github, but that is
# not an actual requirement, just a possibility









# def _shallow_clone_upstream(gh_repo_name_with_owner, branch_or_tag='master'
#                                         , fonts_dir, font_files_prefix):
#   """
#       getting this as a shallow copy, because for some files we want to
#       search in the filesystem.
#
#       branch_or_tag: as used in `git clone -b`
#
#       NOTE: libgit2 and hence pygit2 doesn't support shallow clones,
#       but that's the most light weight way to get the whole directory
#       structure.
#       Another way to get this data would be the github api, but there's
#       a quota (see response headers "X-Ratelimit-Limit: 60" and
#       "X-Ratelimit-Remaining"
#       https://developer.github.com/v3/#rate-limiting
#       unauthorized requests (per IP): the rate limit allows for up to 60 requests per hour.
#       Basic Authentication or OAuth: you can make up to 5000 requests per hour.
#
#   """
#   git_url = GIT_REPO_HTTPS_URL(gh_repo_name_with_owner=gh_repo_name_with_owner)
#   with TemporaryDirectory() as upstream_dir:
#     run(['git', 'clone', '--depth', '1', '-b', branch_or_tag, git_url
#                        , upstream_dir], capture_output=True, check=True)
#     # FIXME: format (in memory, another tmp dir, memory fs?
#     get_package_data_from_upstream(upstream_dir, fonts_dir, font_files_prefix)



# def get_package_data_from_upstream(upstream_dir, fonts_dir, font_files_prefix):
#
#
#
# There are different possible ways to get to the data:
#
# use a git repo that is bare -> we don't plan to use file system functions
# use a git repo that is shallow -> quick download
# use an existing non bare git repo -> should be quickest if existing,
#       hence we need to parse from which remote to read/fetch
# use the github API and http: can run into quotas quickly (i.e. in FBD)
#       NOTE: below using the graphQL api fixes these:
#       This can have a racecondition: getting separate files from the
#       server when the data on the server changes in between. Can rather
#       cause a problem when getting data from upstream than from google/fonts,
#       because the lateer, esp. when getting data for one family, doesn't
#       change often.
#       using the tree api removes the race condition;
#         https://api.github.com/repos/google/fonts/git/trees/630a60fec397257625b0d4049577ddca4eeffaec
#       vs content api:
#         https://api.github.com/repos/google/fonts/contents/ofl/abhayalibre?ref=master
#       Note how the tree api pins to the trees hasj
#
# For the google/fonts data:
#   * if there's an existing clone, with an appropriate remote, using this is best
#   * without existing git repo, using  github + http should suffice.
#   However, later, for creating the PR we need a full, current master branch,
#   but that's not the scope of this tool.
#
#   A shallow clone of google/fonts is rather much too big in order to get just
#   the data of a single family or even super family.
#
#   I expect, that the common case for CLI is to have a clone of google/fonts
#   lying around, we can expect this from our "expert users"
#   For the Dashboard, requiring the whole repo in each worker is not super
#   easy. however, it could just be a part of the docker image. Bloats the
#   image, but solves the problem.
#   Users who won't make the PR personally (maybe using the dashboard
#   or just iterating over QA but the PR is doing someone else, wouldn't need
#   the google/fonts clone and it may annoy them having to have it (size, bandwidth).
#
#   Or, maybe have a git server in the cluster, that at least speeds up
#   downloading compared to going over the internet to github,
#   also reduces stressing github servers if we scale big. Fetching
#   the repo could be fetched on startup and updated prior to usages,
#   for some cases, checked out to a fixed commit, to ensure operation
#   on a controlled version. different versions across workers for the same
#   job could cause trouble.
#
#
#   Ok, so generally, whatever the function is to get files from somewhere
#   (directory, git-plumbing, github-api)
#   maybe a generator directory listing (depth first traversal?) and/or a
#   filtering function to select files?
#
#
#
# def get_files(filenames):
#   collected = []
#   for filename in filenames:
#     use = (yield filename)
#     if use:
#       collected.append(filename)
#   return collected
#
# In [24]: ex = None
#
# In [25]: use = None
#
# In [26]: gen = get_files(['A', 'B', 'C'])
#
# In [27]: try: use = gen.send(use is not None or use); print('USE', use)
#     ...: except StopIteration as e: ex = e;print('END')
# USE A
#
# In [28]: try: use = gen.send(use is not None or use); print('USE', use)
#     ...: except StopIteration as e: ex = e;print('END')
# USE B
#
# In [29]: try: use = gen.send(use is not None or use); print('USE', use)
#     ...: except StopIteration as e: ex = e;print('END')
# USE C
#
# In [30]: try: use = gen.send(use is not None or use); print('USE', use)
#     ...: except StopIteration as e: ex = e;print('END')
# END
#
# In [31]: ex.value
# Out[31]: ['A', 'B', 'C']
#
#
#
#
# def get_files(address, collected):
#   for filename in directoryTraversal(address):
#     (use = yield filename)
#     if(use)
#       collected.add(filename, download(filename))
#
# collected = Files()
# gen = get_files(address, collected)
# result = None
# # TypeError: can't send non-None value to a just-started generator
# In [33]: use = None
#
# In [34]: gen = get_files(['A', 'B', 'C'])
#
# In [35]: while True:
#     ...:     try:
#     ...:         filename = gen.send(use)
#     ...:         use = filename is not None
#     ...:     except StopIteration as e:
#     ...:         result = e.value
#     ...:         break
#     ...:
#
# In [36]: result
# Out[36]: ['A', 'B', 'C']
#
#
#
# def gen2(filter_func):
#   collected = list()
#   for filename in directoryTraversal:
#     if not filter_func(use):
#       continue
#     collected.append(filename)
#   return collected
#
#
#
# it would be interesting to see if pygit2 can handle bare + shallow repositories ...
# it can for our case, which is reading the cloned shallow tree

import random
# The idea is er search only in "prefixes" and on the way back to root.
# to find files like LICENSE.txt or DESCRIPTION.en.us closest to the
# font files.
# We don't go deeper than the prefix that applies.
# FIXME: with one prefix the depth/breath first concept works better
#        otherwise, LICENSES could be ambiguous!
# because we know the possibly picked file is contained in that prefix
# depth first: topdown=False
# breadth first: topdown=True
def dir_walk_breath_first(dirname, prefixes=None, excludes=None):
  topdown=False
  gen = os.walk(dirname, topdown=topdown)
  _dir_walk_breath_first(gen, dirname, prefixes, excludes, topdown)

#this is more experimental than meant for actual code!
def _dir_walk_breath_first(gen, basedir, prefixes, excludes, topdown):
  print('prefixes', prefixes, 'excludes', excludes, 'topdown', topdown)
  whitelisted_dirs = set()
  for prfx in prefixes:
    prfx = os.path.normpath(prfx)
    whitelisted_dirs.add(prfx)
    while prfx:
      prfx, _ = os.path.split(prfx)
      whitelisted_dirs.add(os.path.normpath(prfx))
  for root, dirs, files in gen:
    # is "." if root == basedir otherwise no . at the beginning
    normalized = os.path.relpath(root, basedir)
    if topdown:
      # this is an optimization that only works in topdown=true mode
      # skip dirs not in prefixes
      dirs[:] = [d for d in dirs
                    if not whitelisted_dirs or
                      (os.path.join(normalized, d) if normalized != '.' else d)
                                          in whitelisted_dirs]
      dirs[:] = [d for d in dirs if d not in excludes]
      # sorting is not essential here, it's just to make it easier to
      # comparethe git generator with os.walk. The latter has no
      # specified sort order.
      dirs.sort()
    if whitelisted_dirs and normalized not in whitelisted_dirs or normalized in excludes\
        or any([os.path.commonpath([ex, normalized]) for ex in excludes]):
      continue
    # print('root', normalized, '| raw:', root, '|', dirs)
    # print('dirs', type(dirs), dirs)
    # would probably be  a yield
    print(f'{normalized}/', *[f'\n   {f}' for f in files])
  return


# Using object(expression:$rev), we query all three license folders
# for family_name, but only the entry that exists will return a tree (directory).
# Non existing directories will be null (i.e. None).
# Hence, we can send one query to know the family exists or not, in which
# directory (license) and have a (flat) directory listing.
# I queried "rateLimit{cost}" and this had a cost of 1!
GITHUB_GRAPHQL_GET_FAMILY_ENTRY = """
fragment FamilyFiles on Tree {
  entries{
    name
    type
    oid
  }
}

query ListFiles($repoName: String!,
                $repoOwner: String!,
                $revision: String!,
                $oflDir: String!,
                $uflDir: String!,
                $apacheDir: String!
) {
  repository(name: $repoName, owner: $repoOwner) {
    rev(qualifiedName: $revision) {
      prefix
      name
      target {
        ... on Commit {
          __typename
          oid
          messageHeadline
          pushedDate
        }
      }
    }
    ofl: object(expression: $oflDir) {
      ...FamilyFiles
    }
    apache: object(expression:$apacheDir) {
      __typename
      ...FamilyFiles
    }
    ufl: object(expression:$uflDir) {
      __typename
      ...FamilyFiles
    }
  }
}
"""

def _get_query_variables(repo_owner, repo_name, family_name, revision='refs/heads/master'):
  """
  call like: get_query_variables('google', 'fonts', 'gelasio')

  revision: see $ git help rev-parse
            and git help revisions
  for a branch called "master" "refs/heads/master" is best, but
  "master" would work as well.
  tag names work as well, ideally "ref/tags/v0.6.8" but "v0.6.8" would
  work too. The full name is less ambiguous.
  """
  return {
    'repoOwner': repo_owner,
    'repoName': repo_name,
    'revision': revision,
    'oflDir': f'{revision}:ofl/{family_name}',
    'apacheDir': f'{revision}:apache/{family_name}',
    'uflDir': f'{revision}:ufl/{family_name}'
  }

GITHUB_GRAPHQL_API = 'https://api.github.com/graphql'
# $ export GITHUB_API_TOKEN={the GitHub API token}
GITHUB_API_TOKEN = os.environ['GITHUB_API_TOKEN']
def _run_gh_graphql_query(query, variables):
  headers = {"Authorization": f'bearer {GITHUB_API_TOKEN}'}
  request = requests.post(GITHUB_GRAPHQL_API, json={'query': query, 'variables': variables}, headers=headers)
  request.raise_for_status()
  json = request.json()
  if 'errors' in json:
    errors = pprint.pformat(json['errors'], indent=2)
    raise Exception(f'GrapQL query failed:\n {errors}')
  return json;


def gh_get_family_entry(family_name):
  # needs input sanitation
  family_name_normal = family_name.replace(' ', '').lower()
  print('query family', family_name_normal, f'(raw {family_name})')

  variables = _get_query_variables('google','fonts', family_name_normal)

  print('variables', variables)
  result = _run_gh_graphql_query(GITHUB_GRAPHQL_GET_FAMILY_ENTRY, variables)
  print('result:', result)
  return result


import pygit2
# this should be similar to dir_walk_breath_first but using the git
# objects database, optionally on a shallow repo or on a bare repo
# via pygit2 ...
def _print_git_tree(tree):
  print(f'''tree entries:
  {"""
  """.join([f"<{e.type_str}>: {e.name}" for e in tree])}
  ''')

def _print_git_object(obj, root=None):
  print(f'type: {obj.type_str}')
  print(f'oid: {obj.id}')
  if root is not None:
    print(f'root: {root}')
  # , GIT_OBJ_TREE, GIT_OBJ_BLOB or GIT_OBJ_TAG
  if obj.type == pygit2.GIT_OBJ_COMMIT:
    print(f'message: {obj.message}')
    _print_git_tree(obj.tree)
  if obj.type == pygit2.GIT_OBJ_TREE:
    _print_git_tree(obj)

from collections import deque


def _tree_iterate(path, tree, topdown):
  dirs = []
  files = []
  for e in tree:
    if e.type == pygit2.GIT_OBJ_TREE:
      dirs.append(e.name)
    elif e.type == pygit2.GIT_OBJ_BLOB:
      files.append(e.name)
  if topdown:
    yield path and os.path.join(*path) or '.', dirs, files
  # note, if topdown, caller can manipulate dirs
  for name in dirs:
    path.append(name)
    yield from _tree_iterate(path, tree[name], topdown)
    path.pop()
  if not topdown:
    yield path and os.path.join(*path) or '.', dirs, files

def git_tree_walk(repo, path='', revision='refs/heads/master', topdown=True):
  # will always be a tree, because of the colon in rev
  rev = f'{revision}:{path}'
  tree = repo.revparse_single(rev)
  # _print_git_object(tree)
  # print('>>*<<'*16)
  yield from _tree_iterate([path] if path else [], tree, topdown)

def fs_directory_listing(dirname, prefixes=[], excludes=[], topdown=True):
  gen = os.walk(dirname, topdown=topdown)
  _dir_walk_breath_first(gen, dirname, prefixes, excludes, topdown)

def git_directory_listing(repo_path, basedir='', prefixes=[], excludes=[], topdown=True):
  repo = pygit2.Repository(repo_path)
  # topdown = True
  # basedir = '' # 'fonts'
  gen = git_tree_walk(repo, basedir, topdown=topdown)
  # prefixes = [] # ['ttf', 'variable']# ['fonts/ttf', 'fonts/variable']
  _dir_walk_breath_first(gen, basedir, prefixes, excludes, topdown)

  return
  # repo = pygit2.Repository(repo_path)
  # commit = repo.revparse_single('refs/heads/master')
  # _print_git_object(commit)
  #
  # root = 'fonts/ttf'
  # tree = repo.revparse_single(f'refs/heads/master:{root}')
  # _print_git_object(tree)

  #for root, dirs, files in os.walk(dirname):
  #  depth = root.count(os.path.sep) + 1 - source.count(os.path.sep)
  #  subdir = os.path.relpath(root, source)
  #  if depth >= maxDepth:
  #      # This is a the magic piece, it modifies the list that is
  #      # used by the os.walk iterator.
  #      # Deeper dirs won't be visited...
  #      del dirs[:]
  #  if depth > maxDepth:
  #      continue
  #  for filename in files:
  #      if subdir != '.':
  #          filename = os.path.join(subdir, filename)
  #      yield from fileURLGenerator(target, filename)
  #  for filename in target['config'].get('file_map', {}):
  #      if subdir != '.':
  #          filename = os.path.join(subdir, filename)
  #      yield from fileURLGenerator(target, filename, fromFileMap=True)


# breath first vs depth first:



# Ok, having a fixed list of basically [cp from to] commands sounds easy.
# Could have a helper to create such a list.
#
# This would work to copy all fonts from the upstream to the package and
# handily rename as well.
#
# FIXME:
#       - what to do about the field: family name is confirmed as good?
#       - should we copy not necessarily needed fields from the upstreams spreadsheet???
#           we should probably also document these if necessary!
#           "Status": (OK, NOTE, RENAMED, ?) probably unnecessary if there's an upstream.yaml
#           "sources": editor+version (maintained?)
#           "requests": definitely not up to date/maintained
#           "implemented count": definitely not up to date/maintained
#           "Notes": ???
#           "Vietnamese ranked priority": ???
#           "glyphs_axis": don't know how these are used ot if they are maintained
#           "family name is confirmed as good?": THIS is kind of important!
#         Maybe we can also remove the data that is then in the upstream.yaml
#         to make the spreadsheet not duplicate.
#         OR: make an auto updater for the redundant data in the upstream
#         spreadsheet using Google Drive API (Marc has done something like that).
#       - how will SANDBOX work and what about the field "feature branch key"
#         (e.g. = "Graphicore Fork")
#       - "fontfiles prefix" could be useful to to automatic/assisted creation
#                            of the "fonts" mapping however, then as
#                            "fonts_dir" + "fonts_prefix"
#       - file names, especially with variable fonts: we could do this maybe
#         automated? There's code afaik...
#         ("upstream.yaml assistant")
#         Esp. if file names are all that is needed to a family into google/fonts
#       - variable fonts "static" files besides of file names, should we use an
#         instancer tool to automatically create the static files if they
#         don't exist in the upstream
#
# - What is the workflow to "add" a new family? In that case there's no
#   existing upstream.yaml file...
# - What is the workflow to "change" an "upstream.yaml" file?
#
#
# - Since there's some redundancy with METADATA.pb it's time to rethink
# the "source of truth" handling in this case. If both files are next to
# each other, it can be as well the METADATA.pb file.
# THOUGH: METADATA.pb is not meant for hand-editing and it sucks a bit at it.
#
# Is there a possibility to have some parts of this rather in the upstream
# than in google/fonts?
# How to discover "SANDBOX" entries => * external db, dashboard specific, of
#                                        upstream.yaml files.
#                                      * the db could be repoWithOwner, branch, path/to/upstream.yaml
#                                         though, path/to/upstream.yaml could be a default like
#                                         "gftools-packager.yaml" in the repo root.
#
#
# for DESCRIPTION.en_us.html we already accept that the version on upstream
# supersedes the google/fonts version, so that's an option for integration,
# that doesn't need much attention from the upstream maintainers but allows
# for control.
#
# The minimal upstream info is probably: repoWithOwner + branch as that is
# enough to find the upstream,  and if there's a local ".gftools-packager.yaml"
# it can be used to seed/create the upstream.yaml files.
#
# # gftools-packager.yaml
#   * Think about this like package.yaml or bower.json or "How to Publish an
#     Open-Source Python Package to PyPI"
#     https://realpython.com/pypi-publish-python-package/
#     (YO SEE: "Naming Your Package": You might need to brainstorm and do some
#     research to find the perfect name. Use the PyPI search to check if a name
#     is already taken. The name that you come up with will be visible on PyPI.
#     has parallels to font naming!)
#  * gftools-packager.yaml is not upstream.yaml, it can have many google-fonts
#     style families configured for one repo! The keys could be the the full
#     font name. This is for both: super families AND families co-hosted
#     in the same upstream.
#  * To make the PR, we could even have a tool that calls font-bakery dashboard
#    directly to build the package and QA ...
#    BUT, it's also possible to do it locally!
#  * all files that are now searched "by file name" could have an explicit
#    mapping, I.e. map DESCRIPTION.en_us.html differently per family in the config
#    file.
#    Also: fontbakery.yaml files will likely need different versions per family, etc
#
# Superfamilies (think in the future):
#   * We may have to upgrade a superfamily all at once, if there are breaking
#   changes between the families. A package created by the packager could be
#   aware of this.
#   * Would have to run QA for each family in the package that needs upgrading.
#     But that's not hard to do!
#   * right now, our way to do this would be: create a PR for each family
#     of the super family.
#     Live with the Font Bakery FAILS and accept them as a fact of live.
#   * We would have one PR to upgrade all of a superfamily
#
#
#
#
# ofl/gelasio/upstream.yaml
# ---
# family: Gelasio # (full family name, with initial upper cases and spaces)
# repo: SorkinType/Gelasio # (used to be "upstream" using "repoWithOwnerStyle")
# branch: master
# genre: Sans Serif
# designer: Eben Sorkin
#        # NOTE: this is an example how mapping font file names could work!
# files: #  this replaces "fontfiles prefix"
#  - - fonts/variable/Gelasio-Italic-VF.ttf
#    - Gelasio-Italic[wght].ttf
#  - - fonts/variable/Gelasio-VF.ttf
#    - Gelasio[wght].ttf
#  - - fonts/ttf/Gelasio-BoldItalic.ttf
#    - static/Gelasio-BoldItalic.ttf
#  - - fonts/ttf/Gelasio-Medium.ttf
#    - static/Gelasio-Medium.ttf
#  - - fonts/ttf/Gelasio-MediumItalic.ttf
#    - static/Gelasio-MediumItalic.ttf
#  - - fonts/ttf/Gelasio-SemiBold.ttf
#    - static/Gelasio-SemiBold.ttf
#  - - fonts/ttf/Gelasio-Regular.ttf
#    - static/Gelasio-Regular.ttf
#  - - fonts/ttf/Gelasio-Italic.ttf
#    - static/Gelasio-Italic.ttf
#  - - fonts/ttf/Gelasio-Bold.ttf
#    - static/Gelasio-Bold.ttf
#  - - fonts/ttf/Gelasio-SemiBoldItalic.ttf
#    - static/Gelasio-SemiBoldItalic.ttf
#
#
# CLI Sketches:
#
# gftools packager init # create a new gftools-packager.yaml
# gftools packager familyname <options> # create a package
# # both use packager:
# gftools qa familyname # local qa, should be possible to run via FBD
# gftools pr familyname # QA will run by google bot, should be possible to run via FBD (?)
#
#
# for CLI/FBD integration, authentication is needed, maybe we can
# pass the "GITHUB_API_TOKEN" (a "personal access token") to FBD and use
# it on behalf of the user. OR: at the dashboard: give the user an access
# token that is persistent, revokebale, linked to a gh-access-token.
# That's basically the same as a sessionID, but persisitent. Maybe must
# keep it not as clear text, not clear how to do so...,
