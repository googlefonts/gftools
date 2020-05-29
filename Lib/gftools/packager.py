
# FIXME: document dependencies, expect command line `git` with support
# for shallow clones (not in old git versions)

# FIXME: I added some type annotations, but I did not use a static
# type checker. Hence, there are errors and missing definitions!

import sys
import os
from tempfile import TemporaryDirectory, mkstemp
import subprocess
import requests
import pprint
import typing
from collections import OrderedDict

GITHUB_REPO_HTTPS_URL = 'https://github.com/{gh_repo_name_with_owner}.git'.format
GITHUB_REPO_SSH_URL = 'git@github.com:{gh_repo_name_with_owner}.git'.format

# how to build a package:
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
#       using the tree api removes the race condition
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
                $reference: String!,
                $oflDir: String!,
                $uflDir: String!,
                $apacheDir: String!
) {
  repository(name: $repoName, owner: $repoOwner) {
    ref(qualifiedName: $reference) {
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

def _get_query_variables(repo_owner, repo_name, family_name, reference='refs/heads/master'):
  """
  call like: get_query_variables('google', 'fonts', 'gelasio')

  reference: see $ git help rev-parse
            and git help revisions
            and https://git-scm.com/book/en/v2/Git-Internals-Git-References
  for a branch called "master" "refs/heads/master" is best, but
  "master" would work as well.
  tag names work as well, ideally "ref/tags/v0.6.8" but "v0.6.8" would
  work too. The full name is less ambiguous.
  """
  return {
    'repoOwner': repo_owner,
    'repoName': repo_name,
    'reference': reference,
    'oflDir': f'{reference}:ofl/{family_name}',
    'apacheDir': f'{reference}:apache/{family_name}',
    'uflDir': f'{reference}:ufl/{family_name}'
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
  return json

def get_gh_gf_family_entry(family_name):
  # needs input sanitation
  family_name_normal = family_name.replace(' ', '').lower()
  variables = _get_query_variables('google','fonts', family_name_normal)

  result = _run_gh_graphql_query(GITHUB_GRAPHQL_GET_FAMILY_ENTRY, variables)
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

def git_tree_walk(repo, path='', reference='refs/heads/master', topdown=True):
  # will always be a tree, because of the colon in rev
  rev = f'{reference}:{path}'
  tree = repo.revparse_single(rev)
  # _print_git_object(tree)
  # print('>>*<<'*16)
  yield from _tree_iterate([path] if path else [], tree, topdown)


# the following two produce reasonable similar results.
# this means the iterators are fine!
# needs unit testing
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

GITHUB_V3_REST_API = 'https://api.github.com/'
def get_github_blob(repo_owner, repo_name, file_sha):
  url = f'{GITHUB_V3_REST_API}repos/{repo_owner}/{repo_name}/git/blobs/{file_sha}'
  headers = {
    'Accept': 'application/vnd.github.v3.raw'
  }
  response = request = requests.get(url, headers=headers)
  print(f'response headers: {pprint.pformat(response.headers, indent=2)}')
  # raises requests.exceptions.HTTPError
  request.raise_for_status()
  return response
  # if 'charset' in response.headers['content-type']:
  #   print('response.text:', response.text)
  # else:
  #   # use binary data
  #   # response.content
  #   print('response.content:', response.content)

def get_github_gf_blob(file_sha):
  return get_github_blob('google', 'fonts', file_sha)

def _shallow_clone_git(target_dir, git_url, branch_or_tag='master'):
  """
      getting this as a shallow copy, because for some files we want to
      search in the filesystem.

      branch_or_tag: as used in `git clone -b`

      NOTE: libgit2 and hence pygit2 doesn't support shallow clones yet,
      but that's the most lightweight way to get the whole directory
      structure.
  """

  return subprocess.run(['git', 'clone', '--depth', '1', '--bare'
                       , '-b', branch_or_tag, git_url
                       , target_dir], check=True
                       , stdout=subprocess.PIPE)

def _shallow_clone_github(target_dir, gh_repo_name_with_owner, branch_or_tag='master'):
  """
      Another way to get this data would be the github api, but there's
      a quota (see response headers "X-Ratelimit-Limit: 60" and
      "X-Ratelimit-Remaining"
      https://developer.github.com/v3/#rate-limiting
      unauthorized requests (per IP): the rate limit allows for up to 60 requests per hour.
      Basic Authentication or OAuth: you can make up to 5000 requests per hour.
  """
  git_url = GITHUB_REPO_HTTPS_URL(gh_repo_name_with_owner=gh_repo_name_with_owner)
  return _shallow_clone_git(target_dir, git_url, branch_or_tag=branch_or_tag)



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
from strictyaml import (
                        Map,
                        MapPattern,
                        Enum,
                        Seq,
                        Str,
                        Any,
                        EmptyNone,
                        EmptyDict,
                        dirty_load,
                        as_document,
                        YAMLValidationError,
                        YAML
                      )
# FIXME: why don't I have the license in here? It's not in the upstream
# repo list. Probably usually discovered by the presence and name of the
# license file.
CATEGORIES = ['DISPLAY', 'SERIF', 'SANS_SERIF', 'SANS_SERIF',
                  'HANDWRITING', 'MONOSPACE']

upstream_yaml_schema = Map({
    'name': Str(),
    'repository_url': Str(), # TODO: custom validation please
    'branch': Str(),
    'category': Enum(CATEGORIES),
    'designer': Str(),
    # allowing EmptyDict here, even though we need files in here,
    # but we will catch missing files later in the process.
    # When we have repository_url and branch we can add a editor based
    # dialog that suggests all files present in the repo (delete lines of
    # files you don't want to include).
    'files': EmptyDict() | MapPattern(Str(), Str()) # Mappings with arbitrary key names
})

# since upstream_yaml_template is incomplete, it can't be parsed with
# the complete upstream_yaml_schema. Here's a more forgiving schema for
# the template.
upstream_yaml_template_schema = Map({
    'name': EmptyNone() | Str(),
    'repository_url': EmptyNone() | Str(), # TODO: custom validation please
    'branch': EmptyNone() | Str(),
    'category':  EmptyNone() | Enum(CATEGORIES),
    'designer': EmptyNone() |Str(),
    'files': EmptyDict() | MapPattern(Str(), Str())
})

upstream_yaml_template  = f'''
# Please edit this upstream configuration for the family accordingly.
# This is a yaml formatted file.
# An "#" (number sign) denotes a comment.
# For more help see the docs at:
# https://github.com/googlefonts/gf-docs/tree/master/METADATA

# Full family name, with initial upper cases and spaces
name:

# In most cases this should be based on the GitHub https repo url:
# this https://github.com/{{owner}}/{{repo}}.git
repository_url:

# The branch name used to update google fonts. e.g.: master
branch:

# Choose one of: {', '.join(CATEGORIES)}
category:

# Full name of the type designer(s) or foundry who designed the fonts.
designer:

# Dictionary mapping of SOURCE file names to TARGET file names. Where
# SOURCE is the file path in the upstream repo and TARGET is the file
# path in the google fonts family directory.
# Accepted and expected files:
#     - The font files, ending with ".ttf"
#     - In case of a variable font, static instances in: static/Family-instance.ttf
#     - DESCRIPTION.en_us.html
#     - OFL.txt, the license.  Less likely UFL.txt and LICENSE.txt.
#     - (optional) FONTLOG.txt
files:
  # These are some examples as comments, please modify, add, delete as necessary:
  # OFL.txt: OFL.txt
  # DESCRIPTION.en_us.html: DESCRIPTION.en_us.html
  # fonts/variable/Gelasio-Italic-VF.ttf: Gelasio-Italic[wght].ttf
'''


gelasio_upstream_yaml  = '''
# ofl/gelasio/upstream.yaml
# ---

name: Gelasio # (full family name, with initial upper cases and spaces)
repository_url: https://github.com/SorkinType/Gelasio.git # (used to be "upstream" using "repoWithOwnerStyle")
branch: master
category: SANS_SERIF
designer: Eben Sorkin
# NOTE: this is an example how mapping font file names could work!
#  this replaces "fontfiles prefix"

files:
  DESCRIPTION.en_us.html:
      DESCRIPTION.en_us.html
  OFL.txt:
      OFL.txt
  fonts/variable/Gelasio-Italic-VF.ttf:
      Gelasio-Italic[wght].ttf
  fonts/variable/Gelasio-VF.ttf:
      Gelasio[wght].ttf
  fonts/ttf/Gelasio-BoldItalic.ttf:
      static/Gelasio-BoldItalic.ttf
  fonts/ttf/Gelasio-Medium.ttf:
      static/Gelasio-Medium.ttf
  fonts/ttf/Gelasio-MediumItalic.ttf:
      static/Gelasio-MediumItalic.ttf
  fonts/ttf/Gelasio-SemiBold.ttf:
      static/Gelasio-SemiBold.ttf
  fonts/ttf/Gelasio-Regular.ttf:
      static/Gelasio-Regular.ttf
  fonts/ttf/Gelasio-Italic.ttf:
      static/Gelasio-Italic.ttf
  fonts/ttf/Gelasio-Bold.ttf:
      static/Gelasio-Bold.ttf
  fonts/ttf/Gelasio-SemiBoldItalic.ttf:
      static/Gelasio-SemiBoldItalic.ttf
'''


LICENSE_FILES_2_DIRS = (
        ('UFL.txt', 'ufl')
      , ('OFL.txt', 'ofl')
      , ('LICENSE.txt', 'apache')
)

# /path/to/google/Fonts$ find */*/*  | grep -E "(ofl|apache|ufl)/*/*" \
#                                    | grep -Ev "*/*/*.ttf" \
#                                    | sed 's/.*\/.*\///g' \
#                                    | sort | uniq -c | sort -hr
#  1094 DESCRIPTION.en_us.html
#  1064 METADATA.pb
#  1034 OFL.txt
#   383 FONTLOG.txt
#    43 LICENSE.txt
#    41 static
#    39 EARLY_ACCESS.category
#     7 README
#     4 COPYRIGHT.txt
#     3 UFL.txt
#     3 TRADEMARKS.txt
#     3 README.txt
#     3 LICENCE.txt
#     3 LICENCE-FAQ.txt
#     3 CONTRIBUTING.txt
#     2 README.md
#     2 CONTRIBUTORS.txt
#     1 ofl.txt
#     1 DESCRIPTION.vi_vn.html
#     1 AUTHORS.txt
#
# NOTE: as seen above, there are a lot more filenames in the family
# directories than we do allow here. This may need some adjustment
# later.
# We could allow them maybe if they are already in the upstream, so new
# packages can't add files we don't want to have anymore. Something like
# this.
# All the 3 entries files are in the ufl ubuntu fonts!
#
# TODO: file a bug at goole/fonts, googlefonts/gf-docs or googlefonts/fontbakery?
# Maybe we can have this phenomena acknowledged and documented.
# These allowed files are the officially documented files:
# https://github.com/googlefonts/gf-docs/tree/master/Spec#repository-structure
ALLOWED_FILES = {
    'DESCRIPTION.en_us.html'
  , 'FONTLOG.txt'
  , *dict(LICENSE_FILES_2_DIRS).keys() # just the file names/keys
}

# 'METADATA.pb' # not taken from upstream, technically we update the
# version in google fonts or create it newly


from warnings import warn
import functools

from google.protobuf import text_format
import gftools.fonts_public_pb2 as fonts_pb2

def _write_file_to_package(basedir:str, filename:str, data:bytes) -> None:
  full_name = os.path.realpath(os.path.join(basedir, filename))

  # Can't just let write the file anywhere!
  full_directory = os.path.join(os.path.realpath(basedir), '')
  if os.path.commonprefix([full_name, full_directory]) != full_directory:
    raise Exception(f'Target is not in package directory: "{filename}".')

  os.makedirs(os.path.dirname(full_name), exist_ok=True)
  with open(full_name, 'wb') as f:
    f.write(data)

def _file_in_package(basedir, filename):
  full_name = os.path.join(basedir, filename)
  return os.path.isfile(full_name)

def _genre_2_category(genre):
    # 'Display' => 'DISPLAY'
    # 'Serif' => 'SERIF'
    # 'Sans Serif' => 'SANS_SERIF'
    # 'sans-serif' => 'SANS_SERIF' // this is not what we use
    # 'Handwriting' => 'HANDWRITING'
    # 'Monospace' => 'MONOSPACE'
    return genre.upper().replace(' ', '_').replace('-', '_')


### REDUNDANCIES AND NORMALIZATION
#
# If there is a google/fonts family but no upstream.yaml how much can we
# make from the info that is in METADATA.pb, which is certified good data.
#
# designer
# genre(category)
# family(name)
#
# repo (repository if already present there's probably also an upstream.yaml)
# FIXME: rename repo->source.repository_url, expect github https urls, as in METADATA
# FIXME: genre and family should be the same names and format as in METADATA (category, name)
#
# FIXME: if these are real redundancies (they are) between upsteam.yaml an METADATA it
# would be good to normalize!
# The argument for upstream.yaml is that it is intendet to bootstrap METADATA
# without using data within fonts (because it's self referential). But that
# is basically a critique on how add-fonts handles these values, and we
# actually undo it in here using the data of upstream.yaml. So, with the
# occasion of this tool, we could actually reform/refactor add-fonts.
#
# Actually new fields: branch and files (where files is a new sub-type)
#
# But, for the moment, it is maybe better to separate the two structures and
# go on with upstream.yamls.
#
# NOTE: for bootstrapping, we could als just fill a METADATA.pb with only
# the upstream.conf fields
#
#
# So: existing repo, no upstream conf:
# from METADATA.pb we use:
#       designer, category, name
# we won't get yet:
#       repository_url
# we still need the new stuff:
#       branch, files
#
#
#

#there's some advice to chose an editor to open and how to set a default
# https://stackoverflow.com/questions/10725238/opening-default-text-editor-in-bash
# I like chosing VISUAL over EDITOR falling back to vi, where on my
# system actually vi equals vim:
# ${VISUAL:-${EDITOR:-vi}}
#
# then: maybe we can fill a "upstream_conf" and fill a upstream.yaml file
# with helpful documentation/comments (just like `git rebase -i`) as a
# super simple interface. It's good to note that strictyaml can handle
# comments, also between open and save, so ideally we can
# 1. open a template that has the documentation comments
# 2. set the data that we (think) we know
# 3. present it to the user for editing.
#
# interface `git rebase -i` style
#
# ------------------
#
# Rebase e810d3d..64f437f onto e810d3d (2 commands)
#
# Commands:
# p, pick <commit> = use commit
# r, reword <commit> = use commit, but edit the commit message
# e, edit <commit> = use commit, but stop for amending
# s, squash <commit> = use commit, but meld into previous commit
# f, fixup <commit> = like "squash", but discard this commit's log message
# x, exec <command> = run command (the rest of the line) using shell
# b, break = stop here (continue rebase later with 'git rebase --continue')
# d, drop <commit> = remove commit
# l, label <label> = label current HEAD with a name
# t, reset <label> = reset HEAD to a label
# m, merge [-C <commit> | -c <commit>] <label> [# <oneline>]
# .       create a merge commit using the original merge commit's
# .       message (or the oneline, if no original merge commit was
# .       specified). Use -c <commit> to reword the commit message.
#
# These lines can be re-ordered; they are executed from top to bottom.
#
# If you remove a line here THAT COMMIT WILL BE LOST.
#
# However, if you remove everything, the rebase will be aborted.
# -------------------
#
# Then, when you break it:
#
# --------------------
# error: invalid line 2:  what now?
# You can fix this with 'git rebase --edit-todo' and then run 'git rebase --continue'.
# Or you can abort the rebase with 'git rebase --abort'.
# --------------------
#
# There are two files in .git/rebase-merge/
#      - git-rebase-todo
#      - git-rebase-todo.backup
#
# The .backup file is the version before the user edited, while the
# other is the version that the user left for interpreting
####
# ----------
###
# The interface of `git commit --amend` is much simper:
# ----------
# Commit Message
#
# # Please enter the commit message for your changes. Lines starting
# with '#' will be ignored, and an empty message aborts the commit.
#
# Date:      Wed May 20 04:45:34 2020 +0200
#
# On branch master
# Changes to be committed:
#      modified:   file1.txt
#      new file:   file3.txt
# -------------
# it stores this message in .git/COMMIT_EDITMSG but there's no feedback
# loop involved and also no cleaning up after the commit --ammend format
#
# NOTE: the interface AND aditional information is in the comment footer.
#
#
# NOTE: if editor is not in the command line, but a GUI, the command line
# also prints a  hint:
# $ git commit --amend
# > hint: Waiting for your editor to close the file...
# AND when closed that line is removed!
#

class UserAbortError(Exception):
  pass

class ProgramAbortError(Exception):
  pass

def _get_gf_dir_content(family_name: str) \
        -> typing.Tuple[typing.Union[str, None], dict]:
  gfentry = get_gh_gf_family_entry(family_name)
  entries = None
  for license_dir in ['apache', 'ufl', 'ofl']:
    if gfentry['data']['repository'][license_dir] is not None:
      entries = gfentry['data']['repository'][license_dir]['entries']
  if entries is None:
    return None, {}
  gf_dir_content = {f['name']: f for f in entries}
  return license_dir, gf_dir_content


def _get_editor_command():
  # # there's some advice to chose an editor to open and how to set a default
  # https://stackoverflow.com/questions/10725238/opening-default-text-editor-in-bash
  # I like chosing VISUAL over EDITOR falling back to vi, where on my
  # system actually vi equals vim:
  # ${VISUAL:-${EDITOR:-vi}}
  return os.environ.get('VISUAL' , os.environ.get('EDITOR', 'vi'))

# ANSI controls
TOLEFT = '\u001b[1000D' # Move all the way left (max 1000 steps
CLEARLINE = '\u001b[2K'    # Clear the line
UP =  '\u001b[1A' # moves cursor 1 up
# reset = (CLEARLINE + UP) * num_linebeaks + TOLEFT

def user_input(question: str,
               options: typing.OrderedDict,
               default: typing.Union[str, None] = None,
               yes: typing.Union[bool, None] = None,
               quiet: bool = False
            ):
  """
    Returns one of the keys of the *options* dict.

    In interactive mode (if *yes* is not True, see below) use the
    *input()* function to ask the user a *question* and present the user
    with the possible answers in *options*. Where the keys in *options*
    are the actual options to enter and the values are the descriptions
    or labels.

    default: if *yes* is a bool this should be an option that does
    not require user interaction. That way we can have an all --yes flag
    will always choose the default.

    yes: don't ask the user and use the default. If the value is a boolean
    *default* must be set, because we expect the boolean comes from the
    --yes flag and the programmers intent is to make this dialogue usable
    with that flag. If the value is None, we don't check if default is set.
    The boolean False versus None differentiation is intended as a self
    check to raise awareness of how to use this function.

    quiet: if *yes* is true don't print the question to stdout.
  """
  if default is not None and default not in options:
    # UX: all possible choices must be explicit.
    raise Exception(f'default is f{default} but must be one of: '
                    f'{", ".join(options.keys())}.')
  if yes is not None and default is None:
    # This is a programming error see the __doc__ string above.
    raise Exception('IF yes is is a boolean, default can\'t be None.')

  options_items = [f'{"["+k+"]" if default==k else k}={v}'
                                        for k, v in options.items()]
  question = f'{question}\nYour options {",".join(options_items)}:'

  if yes:
    if not quiet:
      # Don't ask, but print to document the default decision.
      print (question, default)
    return default

  while True:
    answer = input(question).strip()
    if answer == '' and default is not None:
      return default
    if answer in options:
      return answer
    # else will ask again


def _format_upstream_yaml (upstream_yaml: YAML, compact: bool = True):
  # removes comments to make it more compact to read
  if compact:
    description = 'upstream configuration (no comments, normalized)'
    content = as_document(upstream_yaml.data, upstream_yaml_schema).as_yaml()
  else:
    description = 'upstream configuration'
    content = upstream_yaml.as_yaml()
  len_top_bars = (58 - len(description)) // 2
  top = f'{"-"*len_top_bars} {description} {"-"*len_top_bars}'
  return (
    f'{top}\n'
    f'{content}'
    f'{"-"*len(top)}'
  )

def _repl_upstream_conf(initial_upstream_conf: str, yes: bool=False
                      , quiet: bool=False):
  if yes:
    raise UserAbortError()
  # repl means "read-eval-print loop"
  editor = _get_editor_command()

  # it would be nice to have a location where the file can be inspected
  # after this program ends, similar to swp files of vim or how git stores
  # such files. However, that should maybe be in the upstream repository
  # rather than in the current working directory. Since I'm undecided
  # I simply go with a temp file
  _tempfilefd, upstream_yaml_file_name = mkstemp(suffix='.yaml'
                                                     , prefix='upstream')
  try:
    # Unlike TemporaryFile(), the user of mkstemp() is responsible for
    # deleting the temporary file when done with it.
    os.close(_tempfilefd)
    print(f'temp file name is {upstream_yaml_file_name}')

    last_good_conf = None
    edit_challenge = initial_upstream_conf

    while True:
      # truncates the file on open
      with open(upstream_yaml_file_name, 'w') as upstream_yaml_file:
        upstream_yaml_file.write(edit_challenge)
      # open it in an editor
      # NOTE the carriage return, this line will be removed again.
      # not sure if this should go to stdout or stderr
      print ('hint: Waiting for your editor to close the file ...'
                                    , end='', flush=True, file=sys.stderr)
      subprocess.run([editor, upstream_yaml_file_name])
      print (CLEARLINE + TOLEFT, end='', flush=True, file=sys.stderr)

      # read the file
      with open(upstream_yaml_file_name, 'r') as upstream_yaml_file:
        updated_upstream_conf = upstream_yaml_file.read()

      # parse the file
      try:
        last_good_conf = dirty_load(updated_upstream_conf, upstream_yaml_schema
                                           , allow_flow_style=True)
      except YAMLValidationError as err:
        answer = user_input('The configuration has schema errors:\n\n'
                       f'{err}',
                       OrderedDict(f='fix last edit',
                                   r='retry last edit',
                                   s='start all over',
                                   q='quit program'),
                       # the default should always be an option that does
                       # not require user interaction. That way we can
                       # have an all --yes flag that always choses the
                       # default.
                       default='q', yes=yes, quiet=quiet)
        if answer == 'f':
          edit_challenge = updated_upstream_conf
        elif answer == 'r':
          # edit_challenge = edit_challenge
          pass
        elif answer == 's':
          edit_challenge = initial_upstream_conf
        else: # anser == 'q':
          raise UserAbortError()
        continue

      return last_good_conf
      # This was thought as an extra check for the user, but I think it's
      # rather anoying than helpful. Note, the user just edited and
      # it parsed successfully.
      # # Ask the user if this looks good.
      # answer = user_input('Use this upstream configuration?\n'
      #       f'{_format_upstream_yaml(last_good_conf)}',
      #       OrderedDict(y='yes',
      #                   e='edit again',
      #                   s='start all over',
      #                   q='quit program'),
      #       default='y', yes=yes, quiet=quiet)
      # if answer == 'y':
      #   return last_good_conf
      # elif answer == 'e':
      #   edit_challenge = last_good_conf.as_yaml()
      # elif answer == 's':
      #   edit_challenge = initial_upstream_conf
      # else: # answer == 'q':
      #   raise UserAbortError()
  finally:
    os.unlink(upstream_yaml_file_name)

# add path to make completely fresh package (similar to from_family)
# unite with update path
# flags ... use a local update.yaml
#         --yes
#         --quiet
# make proper CLI!
# different use cases: local workflow
#   Where to put the package
#

# FIXME: when we know the full name of the family perhaps we can look up
# some data from the upstream spreadsheet, as it is used by FBD
#  - could also help to pre-fill the files map using the files prefix
# FIXME 2: an assistent to pre-fill the files map would be nice.
#          could be just all files from the repository
# FIXME 3: files map add flag to override "allowed files" i.e. to allow
#          otherwise blacklisted (=not whitelisted) files: but that should
#          be a temporary measure. Eventually these files should be in
#          the whitelist.

def _load_or_repl_upstream(upstream_yaml_text: str, yes: bool=False
                        , quiet: bool=False) -> typing.Tuple[bool, YAML]:
  try:
    return False, dirty_load(upstream_yaml_text, upstream_yaml_schema
                                        , allow_flow_style=True)
  except YAMLValidationError as err:
    answer = user_input('The configuration has schema errors:\n\n'
                     f'{err}',
                     OrderedDict(e='edit',
                                 q='quit program'),
                     default='q', yes=yes, quiet=quiet)
    if answer == 'q':
      raise UserAbortError()
    return True, _repl_upstream_conf(upstream_yaml_text, yes=yes, quiet=quiet)

def _upstream_conf_from_file(filename: str, yes: bool=False
                                          , quiet: bool=False) -> YAML:
  """ If this parses there will be no repl, the user can edit
  the file directly on disk.
  If it doesn't parse, there's a chance to edit until the yaml parses
  and to change the result back to disk.
  """
  with open(filename, 'r+') as upstream_yaml_file:
    upstream_yaml_text = upstream_yaml_file.read()
    edited, upstream_conf_yaml = _load_or_repl_upstream(upstream_yaml_text
                                                  , yes=yes, quiet=quiet)
    # "edited" is only true when upstream_yaml_text did not parse and
    # was then edited successfully.
    if edited:
      answer = user_input(f'Save changed file {filename}?\n'
            f'{_format_upstream_yaml(upstream_conf_yaml, compact=False)}',
            OrderedDict(y='yes',
                        n='no'),
            default='y', yes=yes, quiet=quiet)
      if answer == 'y':
        upstream_yaml_file.seek(0)
        upstream_yaml_file.truncate()
        upstream_yaml_file.write(upstream_conf_yaml.as_yaml())
  return upstream_conf_yaml


def _upstream_conf_from_scratch(family_name: typing.Union[str, None]=None,
                                yes: bool=False, quiet: bool=False) \
                                                  -> YAML:
  if family_name is not None:
    upstream_conf_yaml = dirty_load(upstream_yaml_template, upstream_yaml_template_schema
                                            , allow_flow_style=True)
    upstream_conf_yaml['name'] = family_name
    template = upstream_conf_yaml.as_yaml()
  else:
    template = upstream_yaml_template
  upstream_conf_yaml = _repl_upstream_conf(upstream_yaml_template,
                                           yes=yes, quiet=quiet)

  return upstream_conf_yaml

def _user_input_license(yes: bool=False, quiet: bool=False):
  answer = user_input('To add a new typeface family to Google Fonts we '
              'must know the license of the family.\n'
              'It\'s very likely that OFL is the license that is expected here.',
              OrderedDict(o='OFL: SIL Open Font License',
                          a='Apache License',
                          u='Ubuntu Font License',
                          q='quit program'),
              # the default should always be an option that does
              # not require user interaction. That way we can
              # have an all --yes flag that always choses the
              # default.
              default='o', yes=yes, quiet=quiet)
  if answer == 'q':
    raise UserAbortError()
  license_dir = dict(o='ofl', a='apache', u='ufl')[answer]
  return license_dir

def _upstream_conf_from_metadata(metadata_str: str, yes: bool=False
                                                  , quiet: bool=False):
  """Use the data that is already in METADATA,pb to bootstrap filling
     the upstream conf.
  """
  metadata = fonts_pb2.FamilyProto()
  text_format.Parse(metadata_str, metadata)
  # existing repo, no upstream conf:
  # from METADATA.pb we use:
  #       designer, category, name
  # we won't get **yet**:
  #       source.repository_url
  # we still need the new stuff:
  #       branch, files
  upstream_conf = {
    'designer': metadata.designer or None,
    'category': metadata.category or None,
    'name': metadata.name  or None,
    # we won't get this just now in most cases!
    'repository_url': metadata.source.repository_url or None,
  }

  upstream_conf_yaml = dirty_load(upstream_yaml_template, upstream_yaml_template_schema
                                       , allow_flow_style=True)
  for k,v in upstream_conf.items():
    if v is None: continue
    upstream_conf_yaml[k] = v
  return _repl_upstream_conf(upstream_conf_yaml.as_yaml(), yes=yes, quiet=quiet)

def _upstream_conf_from_yaml(upstream_yaml_text: str, yes: bool=False
                            , quiet: bool=False) -> YAML:
  """ Make a package when the upstream.yaml file is already in the
  google/fonts repo.

  Eventually the common update path.
  """
  # two cases:
  # - upstream.yaml may need an update by the user
  # - upstream.yaml may be invalid (updated schema, syntax)
  answer = user_input('Do you want to edit upstream.yaml?',
                 OrderedDict(y='yes',
                             n='no'),
                 default='n', yes=yes, quiet=quiet)
  if answer == 'y':
    return _repl_upstream_conf(upstream_yaml_text, yes=yes, quiet=quiet)
  _, upstream_conf_yaml =  _load_or_repl_upstream(upstream_yaml_text, yes=yes, quiet=quiet)
  return upstream_conf_yaml


def _get_upstream_info(file_or_family: str, is_file: bool, yes: bool, quiet: bool) \
                                    -> typing.Tuple[YAML, str, dict]:
  # the first task is to acquire an upstream_conf, the license dir and
  # if present the available files for the family in the google/fonts repo.
  license_dir = None
  upstream_conf_yaml = None
  gf_dir_content = {}

  if not is_file:
    family_name = file_or_family
  else:
    # load a upstream.yaml from disk
    upstream_conf_yaml = _upstream_conf_from_file(file_or_family
                                                  , yes=yes, quiet=quiet)
    family_name = upstream_conf_yaml['name'].data

  # TODO:_get_gf_dir_content: is implemented as github graphql query,
  # but, as an alternative, could also be answered with a local
  # clone of the git repository. then _get_gf_dir_content needs a
  # unified api.
  # if family_name can't be found:
  #    license_dir is None, gf_dir_content is an empty dict
  license_dir, gf_dir_content = _get_gf_dir_content(family_name)

  if license_dir is None:
    # The family is not specified or not found on google/fonts.
    # Can also be an user input error, but we don't handle this yet/here.
    print(f'Font Family "{family_name}" not found on Google Fonts.')
    license_dir = _user_input_license(yes=yes, quiet=quiet)
    if upstream_conf_yaml is None:
      # if there was no local upstream yaml 'file://'
      upstream_conf_yaml = _upstream_conf_from_scratch(family_name
                                                  , yes=yes, quiet=quiet)
  else:
    print(f'Font Family "{family_name}" is on Google Fonts under "{license_dir}".')

  if upstream_conf_yaml is not None:
    # loaded via file:// or from_scratch
    pass
  # found on google/fonts and use gf_dir_content
  elif family_name == 'Gelasio':
    # CAUTION: SHIM IN PLACE!
    # FIXME temp
    warn(f'TEMP! Using upstream_yaml shim for {family_name}!')
    upstream_conf_yaml = _upstream_conf_from_yaml(gelasio_upstream_yaml
                                                  , yes=yes, quiet=quiet)
  elif 'upstream.yaml' in gf_dir_content:
    # normal case
    print(f'Using upstream.yaml from google/fonts for {family_name}.')
    file_sha = gf_dir_content['upstream.yaml']['oid']
    response = get_github_gf_blob(file_sha)
    upstream_conf_yaml = _upstream_conf_from_yaml(response.text
                                                  , yes=yes, quiet=quiet)
  elif 'METADATA.pb' in gf_dir_content:
    # until there's upstream_conf in each family dir
    print(f'Using METADATA.pb.yaml from google/fonts for {family_name}.')
    file_sha = gf_dir_content['METADATA.pb']['oid']
    response = get_github_gf_blob(file_sha)
    upstream_conf_yaml = _upstream_conf_from_metadata(response.text
                                                , yes=yes, quiet=quiet)
  else:
    raise Exception('Unexpected: can\'t use google fonts family data '
                    f'for {family_name}.')
  return upstream_conf_yaml, license_dir, gf_dir_content or {}

def _copy_upstream_files(branch: str, files: dict, repo: pygit2.Repository
            , write_file_to_package: typing.Callable[[str, bytes], None]
            , no_whitelist: bool=False) \
              -> OrderedDict:

  SKIP_NOT_PERMITTED = 'Target is not a permitted filename (see --no_whitelist):'
  SKIP_SOURCE_NOT_FOUND = 'Source not found in upstream:'
  SKIP_SOURCE_NOT_BLOB = 'Source is not a blob (blob=file):'
  SKIP_COPY_EXCEPTION = 'Can\'t copy:'
  skipped = OrderedDict([
      (SKIP_NOT_PERMITTED, []),
      (SKIP_SOURCE_NOT_FOUND, []),
      (SKIP_SOURCE_NOT_BLOB, []),
      (SKIP_COPY_EXCEPTION, [])
  ])
  for source, target in files.items():
    # there are two places where .ttf files are allowed to go
    # we don't do filename/basename validation here, that's
    # a job for font bakery
    if target.endswith('.ttf') \
        and os.path.dirname(target) in ['', 'static']:
      pass # using this!
    elif target not in ALLOWED_FILES \
                          and not no_whitelist: # this is the default
      skipped[SKIP_NOT_PERMITTED].append(target)
      continue
    # else: allow, write_file_to_package will raise errors if target is bad

    try:
      source_object = repo.revparse_single(f"{branch}:{source}")
    except KeyError as e:
      skipped[SKIP_SOURCE_NOT_FOUND].append(source)
      continue
    _print_git_object(source_object)

    if(source_object.type != pygit2.GIT_OBJ_BLOB):
      skipped[SKIP_SOURCE_NOT_BLOB].append(f'{source} (type is {source_object.type_str})')
      continue

    try:
      write_file_to_package(target, source_object.data)
    except Exception as e:
      # i.e. file exists
      skipped[SKIP_COPY_EXCEPTION].append(f'{target} ERROR: {e}')
  # Clean up empty entries in skipped.
  # using list() because we can't delete from a dict during iterated
  for key in list(skipped):
    if not skipped[key]: del skipped[key]
  # If skipped is empty all went smooth.
  return skipped

def _create_or_update_metadata_pb(upstream_conf: YAML,
                                  tmp_package_family_dir:str,
                                  upstream_commit_sha:str) -> None:
  metadata_file_name = os.path.join(tmp_package_family_dir, 'METADATA.pb')
  subprocess.run(['gftools', 'add-font', tmp_package_family_dir]
                                , check=True, stdout=subprocess.PIPE)
  metadata = fonts_pb2.FamilyProto()
  with open(metadata_file_name, 'rb') as f:
    text_format.Parse(f.read(), metadata)

  # make upstream_conf the source of truth for some entries
  metadata.name = upstream_conf['name']
  for font in metadata.fonts:
    font.name = upstream_conf['name']
  metadata.designer = upstream_conf['designer']
  metadata.category = upstream_conf['category']
  # metadata.date_added # is handled well

  metadata.source.repository_url = upstream_conf['repository_url']
  metadata.source.commit = upstream_commit_sha

  text_proto = text_format.MessageToString(metadata)
  with open(metadata_file_name, 'w') as f:
    f.write(text_proto)

def _create_package(upstream_conf_yaml: YAML, license_dir: str, gf_dir_content:dict,
                  no_whitelist: bool = False):
  upstream_conf = upstream_conf_yaml.data

  print(f'Creating package with \n{_format_upstream_yaml(upstream_conf_yaml)}')

  upstream_commit_sha = None

  # NOTE: this tmp_package_dir could be a TreeObject of a google/fonts git
  # repository!
  with TemporaryDirectory() as tmp_package_dir:
    family_name_normal = upstream_conf['name'].replace(' ', '').lower()
    tmp_package_family_dir = os.path.join(tmp_package_dir, license_dir, family_name_normal)
    # putting state into functions, could be done with classes/methods as well
    write_file_to_package = functools.partial(_write_file_to_package,
                                              tmp_package_family_dir)
    file_in_package = functools.partial(_file_in_package,
                                        tmp_package_family_dir)
    # Get and add upstream files!
    with TemporaryDirectory() as upstream_dir:
      # TODO: we could also use a path to an existing local clone of the
      # repo here or even enable to use a path to a directory. This is
      # rather  for the user story of work in progress "sandbox" checking.
      # However, for the FBD sandbox workflow a repo/branch is also
      # needed, so using the --file flag for a local upstream.yaml file
      # is an OK path for the moment to support in progress work, although
      # not so straight forward if all files are on disk already.
      # Perhaps, we could just use the "file://" uri scheme in
      # repository_url to address a local git repository and then
      # skip the cloning:
      # upstream_dir = upstream_conf['repository_url'][len('file://'):]
      # the context manager in here: TemporaryDirectory could be skipped
      # as well, or we use a "fake" context manager easily with
      # @contextlib.contextmanager
      _shallow_clone_git(upstream_dir, upstream_conf['repository_url']
                                        , upstream_conf['branch'])
      repo = pygit2.Repository(upstream_dir)
      upstream_commit = repo.revparse_single(upstream_conf['branch'])
      upstream_commit_sha = upstream_commit.hex

      # Copy all files from upstream_conf['files'] to tmp_package_family_dir
      # We are strict about what to allow, unexpected files
      # are not copied. Instead print a warning an suggest filing an
      # issue if the file is legitimate. A flag to explicitly
      # skip the whitelist check (--no_whitelist)
      # enables making packages even when new yet unknown files are required).
      # Do we have a Font Bakery check for expected/allowed files? Would
      # be a good complement.
      skipped = _copy_upstream_files(upstream_conf['branch'],
                        upstream_conf['files'], repo, write_file_to_package,
                        no_whitelist=no_whitelist)
      if skipped:
        message = ['Some files from upstream_conf could not be copied.']
        for reason, items in skipped.items():
          message.append(reason)
          for item in items:
            message.append(f' - {item}')
        # The whitelist could be ignored using a flag, but the rest should
        # be fixed in the files map, because it's obviously wrong (not working)
        raise ProgramAbortError('\n'.join(message))

    # Get and add all files from google/fonts
    for name, entry in gf_dir_content.items():
      # not copying old TTFs, directories and files that are already there
      if name.endswith('.ttf') \
            or entry['type'] != 'blob'\
            or file_in_package(name):
        continue
      file_sha = gf_dir_content[name]['oid']
      response = get_github_gf_blob(file_sha)
      write_file_to_package(name, response.content)

    # create/update METADATA.pb
    _create_or_update_metadata_pb(upstream_conf, tmp_package_family_dir,
                                                    upstream_commit_sha)

    # create/update upstream.yaml
    with open(os.path.join(tmp_package_family_dir, 'upstream.yaml'), 'w') as f:
      f.write(upstream_conf_yaml.as_yaml())

    # FIXME: REMOVE, also, how to go on now?
    print('Package content:')
    for root, dirs, files in os.walk(tmp_package_dir):
      for filename in files:
        full_path = os.path.join(root, filename)
        filesize = os.path.getsize(full_path)
        print(f'    {os.path.relpath(full_path, tmp_package_dir)} '
              f'{int(filesize / (1<<10))}KB (len: {filesize})')

    print('Package is DONE. TODO: What next?')


def make_package(file_or_family: str, is_file: bool, yes: bool, quiet: bool,
                no_whitelist: bool):
  ( upstream_conf_yaml, license_dir,
    gf_dir_content ) = _get_upstream_info(file_or_family, is_file, yes, quiet)
  _create_package(upstream_conf_yaml, license_dir, gf_dir_content, no_whitelist)

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
# keep it not as clear text, not clear how to do so...
#
# In general here, the idea is that the dashboard could take on any task
# of the local machine.


# simple first
#
# check: get a path to a git-directory and figure if it has a google/fonts
# remote, otherwise: adding the remote and fetching could done with a --force
# flag.

def is_google_fonts(repo_path):
  repo = pygit2.Repository(repo_path)
  #remote.name
  #> 'origin'
  #>  remote.url
  # this is a good indicator that we are in fact in the right repository!
  #>'git@github.com:google/fonts.git'
  # so remote url can be a github ssh or https url

  # need a refspec to fetch {remoteName/master} ?
  # I'd expect
  # remote.fetch_refspecs # ['+refs/heads/*:refs/remotes/upstream/*']
  # to contain a refspec
  # f'+refs/heads/*:refs/remotes/{remote.name}/*'
  # then fetching
  # f'{remote.name}/master'
  # should be straight forward
  # maybe:
  # f'+refs/heads/master:refs/remotes/{remote.name}/master'
  # is also sufficient, as * looks like a wildcard
  # works well:  git fetch upstream +refs/heads/master:refs/remotes/upstream/master


  # if there's no remote with a github url, we could either ask the user
  # to add the remote suggesting the command to do so, or we
  # do it ourselves, after asking for permission.
  # This implies that fetching is OK, which is a big amount of data.


  searched_repo = 'google/fonts'
  accepted_remote_urls = {
  # f'git@github.com:{searched_repo}.git', # ssh
  # f'ssh://git@github.com/{searched_repo}' # ssh
     f'https://github.com/{searched_repo}.git' # token
  }
  found = None
  candidates = []
  # could find more remotes that work, but using the first match should suffice
  for remote in repo.remotes:
    if remote.url in accepted_remote_urls:
      print(f'looking at {remote.name} {remote.url}')
      candidates.append(remote)
      # FIX if insufficient:
      accepted_refspecs = {
        f'+refs/heads/*:refs/remotes/{remote.name}/*'
      , f'+refs/heads/master:refs/remotes/{remote.name}/master'
      }
      # NOTE: a shallow repository has no remotes!
      # but in case of a shallow repo, we probably rather
      # use the github api anyways.
      for refspec in remote.fetch_refspecs:
        if refspec in accepted_refspecs:
          if found is None:
            found = remote
          print(f'FOUND! {remote.name} {remote.url} with refspec {refspec}')
        else:
          print(f'NOPE {remote.name}')
    else:
      print(f'skipping {remote.name} {remote.url}')

  if found is not None:
    class MyRemoteCallbacks(pygit2.RemoteCallbacks):
      def credentials(self, url, username_from_url, allowed_types):
          if allowed_types & pygit2.credentials.GIT_CREDENTIAL_USERNAME:
              print('GIT_CREDENTIAL_USERNAME')
              return pygit2.Username("git")
          elif allowed_types & pygit2.credentials.GIT_CREDENTIAL_SSH_KEY:
              print('GIT_CREDENTIAL_SSH_KEY', url, username_from_url, allowed_types)
              sshkeys = os.path.join(os.getenv("HOME"), '.ssh')
              pubkey = os.path.join(sshkeys, 'id_rsa.pub')
              privkey = os.path.join(sshkeys, 'id_rsa')
              # The username for connecting to GitHub over SSH is 'git'.
              # https://github.com/libgit2/pygit2/issues/428#issuecomment-55775298
              print(f'pubkey {pubkey} privkey {privkey}')
              return pygit2.Keypair(username_from_url, pubkey, privkey, '')
          else:
              print('NO ALLOWED TYPES???', allowed_types)
              return None
      def sideband_progress(self, data):
        print(f'sideband_progress: {data}')

      # this works!
      def transfer_progress(self, tp):
          print('transfer_progress:\n'
            f'  received_bytes {tp.received_bytes}\n'
            f'  indexed_objects {tp.indexed_objects}\n'
            f'  received_objects {tp.received_objects}')

    print('start fetch')
    # fetch(refspecs=None, message=None, callbacks=None, prune=0)
    # using just 'master' instead of 'refs/heads/master' works as well
    stats = found.fetch(['refs/heads/master'], callbacks=MyRemoteCallbacks())
    print('DONE fetch:\n',
          f'  received_bytes {stats.received_bytes}\n'
          f'  indexed_objects {stats.indexed_objects}\n'
          f'  received_objects {stats.received_objects}')
          #f'  received_bytes {stats["received_bytes"]}\n'
          #f'  indexed_objects {stats["indexed_objects"]}\n'
          #f'  received_objects {stats["received_objects"]}')
    return

  print('candidates:', *[r.name for r in candidates])


  # FIXME: default_remote_name must be non-existing
  # TODO: what happens if it exists?
  default_remote_name = 'upstream'
  # This way it can't be 'a' (that's abort!), should be no issue.
  remote_name = input(f'Creating a git remote.\nEnter remote name (default={default_remote_name}),a=abort:')
  if remote_name == 'a':
    raise UserAbortError()
  remote_name = remote_name or default_remote_name

  # FIXME: SSH fails
  # _pygit2.GitError: Failed to retrieve list of SSH authentication methods: Failed getting response
  # https://github.com/libgit2/pygit2/issues/836
  # "These are libssh2 issues, not libgit2/pygit2. My advice is to use the latest version of libssh2: 1.9.0"
  # BUT:  "The pygit2 Linux wheels include libgit2 with libssh2 1.9.0 statically linked."
  # url =  f'git@github.com:{searched_repo}.git'
  # url =  f'ssh://git@github.com/{searched_repo}'



  url = f'https://github.com/{searched_repo}.git'
  print(f'creating remote: {remote_name} {url}')
  # raises ValueError: remote 'upstream' already exists

  refspecs_candidates = {
      '1': f'+refs/heads/*:refs/remotes/{remote_name}/*'
    , '2': f'+refs/heads/master:refs/remotes/{remote_name}/master'
  }
  print('Pick a fetch refspec:')
  print(f'1: {refspecs_candidates["1"]} (default)')
  print(f'2: {refspecs_candidates["2"]} (minimal)')
  refspec = input(f'1(default),2,a=abort:')
  if remote_name == 'a':
    raise UserAbortError()
  fetch_refspec = refspecs_candidates[refspec.strip()]
  repo.remotes.create(remote_name, url, fetch=fetch_refspec)

    # Create a new remote with the given name and url. Returns a <Remote> object.
    # If ‘fetch’ is provided, this fetch refspec will be used instead of the default.


    # Add a fetch refspec (str) to the remote
    # repo.remotes.add_fetch(remote_name, refspec)




  # for pushing to https github urls see:
  # Using a token on the command line
  # https://help.github.com/en/github/authenticating-to-github/creating-a-personal-access-token-for-the-command-line#using-a-token-on-the-command-line

  # import IPython
  # IPython.embed(colors="neutral") # nice!
