"""
This module implements gftools/bin/gftools-packager.py

Tool to take files from a font family project upstream git repository
to the google/fonts GitHub repository structure, taking care of all the details.

Documentation at gftools/docs/gftools-packager/README.md
"""
import sys
import os
from pathlib import PurePath
import shutil
from tempfile import TemporaryDirectory, mkstemp
import subprocess
import requests
import pprint
import typing
from collections import OrderedDict
import traceback
from io import StringIO, BytesIO
from contextlib import contextmanager
import urllib.parse
import pygit2 # type: ignore
from strictyaml import ( # type: ignore
                        Map,
                        MapPattern,
                        Enum,
                        Str,
                        Any,
                        EmptyNone,
                        EmptyDict,
                        Optional,
                        dirty_load,
                        as_document,
                        YAMLValidationError,
                        YAML
                      )
import functools
from hashlib import sha1
from fontTools.ttLib import TTFont # type: ignore

# ignore type because mypy error: Module 'google.protobuf' has no
# attribute 'text_format'
from google.protobuf import text_format # type: ignore

# Getting many mypy errors here like: Lib/gftools/fonts_public_pb2.py:253:
#     error: Unexpected keyword argument "serialized_options" for "Descriptor"
# The "type: ignore" annotation didn't help.
from typing import TYPE_CHECKING
if TYPE_CHECKING:
  fonts_pb2: typing.Any
else:
  import gftools.fonts_public_pb2 as fonts_pb2

CATEGORIES = ['DISPLAY', 'SERIF', 'SANS_SERIF', 'HANDWRITING', 'MONOSPACE']

from pkg_resources import resource_filename
with open(resource_filename('gftools', 'template.upstream.yaml')) as f:
  upstream_yaml_template = f.read()
  # string.format fails if we use other instances of {variables}
  # without adding them to the call to format (KeyError).
  upstream_yaml_template = upstream_yaml_template.replace('{CATEGORIES}', ', '.join(CATEGORIES))



# GITHUB_REPO_HTTPS_URL = 'https://github.com/{gh_repo_name_with_owner}.git'.format
GITHUB_REPO_SSH_URL = 'git@github.com:{repo_name_with_owner}.git'.format

GITHUB_GRAPHQL_API = 'https://api.github.com/graphql'
GITHUB_V3_REST_API = 'https://api.github.com'

GIT_NEW_BRANCH_PREFIX = 'gftools_packager_'
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

def _get_github_api_token() -> str:
  # $ export GH_TOKEN={the GitHub API token}
  return os.environ['GH_TOKEN']

def _post_github(url: str, payload: typing.Dict):
  github_api_token = _get_github_api_token()
  headers = {'Authorization': f'bearer {github_api_token}'}
  response = requests.post(url, json=payload, headers=headers)
  if response.status_code == requests.codes.unprocessable:
    # has a helpful response.json with an 'errors' key.
    pass
  else:
    response.raise_for_status()
  json = response.json()
  if 'errors' in json:
    errors = pprint.pformat(json['errors'], indent=2)
    raise Exception(f'GitHub POST query failed to url {url}:\n {errors}')
  return json

def _run_gh_graphql_query(query, variables):
  payload = {'query': query, 'variables': variables}
  return _post_github(GITHUB_GRAPHQL_API, payload)

def _family_name_normal(family_name: str) -> str:
  return family_name.lower()\
      .replace(' ', '')\
      .replace('.', '')\
      .replace('/', '')

def get_gh_gf_family_entry(family_name):
  # needs input sanitation
  family_name_normal = _family_name_normal(family_name)
  variables = _get_query_variables('google','fonts', family_name_normal)

  result = _run_gh_graphql_query(GITHUB_GRAPHQL_GET_FAMILY_ENTRY, variables)
  return result

def _git_tree_iterate(path, tree, topdown):
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
    yield from _git_tree_iterate(path, tree[name], topdown)
    path.pop()
  if not topdown:
    yield path and os.path.join(*path) or '.', dirs, files

def _git_tree_walk(path, tree, topdown=True):
  yield from _git_tree_iterate(path.split(os.sep), tree[path], topdown)

def get_github_blob(repo_owner, repo_name, file_sha):
  url = f'{GITHUB_V3_REST_API}/repos/{repo_owner}/{repo_name}/git/blobs/{file_sha}'
  headers = {
    'Accept': 'application/vnd.github.v3.raw'
  }
  response = requests.get(url, headers=headers)
  # print(f'response headers: {pprint.pformat(response.headers, indent=2)}')
  # raises requests.exceptions.HTTPError
  response.raise_for_status()
  return response

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

  # I don't understand why git clone doesn't take this more explicit form.
  # But, I recommended it in the docs, so here's a little fix.
  if branch_or_tag.startswith('tags/'):
    branch_or_tag = branch_or_tag[len('tags/'):]

  return subprocess.run(['git', 'clone', '--depth', '1', '--bare'
                       , '-b', branch_or_tag, git_url
                       , target_dir], check=True
                       , stdout=subprocess.PIPE)

# Eventually we need all these keys to make an update, so this
# can't have Optional/Empty entries, unless that's really optional for
# the process.
upstream_yaml_schema = Map({
    'name': Str(),
    'repository_url': Str(), # TODO: custom validation please
    'branch': Str(),
    'category': Enum(CATEGORIES),
    'designer': Str(),
    Optional('build', default=''): EmptyNone() | Str(),
    # allowing EmptyDict here, even though we need files in here,
    # but we will catch missing files later in the process.
    # When we have repository_url and branch we can add a editor based
    # dialog that suggests all files present in the repo (delete lines of
    # files you don't want to include).
    'files': EmptyDict() | MapPattern(Str(), Str()) # Mappings with arbitrary key names
})

# Since upstream_yaml_template is incomplete, it can't be parsed with
# the complete upstream_yaml_schema. Here's a more forgiving schema for
# the template and for initializing with a stripped upstream_conf.
upstream_yaml_template_schema = Map({
    Optional('name', default=''): EmptyNone() | Str(),
    Optional('repository_url', default=''): EmptyNone() | Str(), # TODO: custom validation please
    'branch': EmptyNone() | Str(),
    Optional('category', default=None):  EmptyNone() | Enum(CATEGORIES),
    Optional('designer', default=''): EmptyNone() |Str(),
    Optional('build', default=''): EmptyNone() | Str(),
    'files': EmptyDict() | MapPattern(Str(), Str())
})

upstream_yaml_stripped_schema = Map({ # TODO: custom validation please
    # Only optional until it can be in METADATA.pb
    Optional('repository_url', default=''): Str(),
    'branch': EmptyNone() | Str(),
    Optional('build', default=''): EmptyNone() | Str(),
    'files': EmptyDict() | MapPattern(Str(), Str())
})

# ALLOWED FILES
LICENSE_FILES_2_DIRS = (
        ('LICENSE.txt', 'apache')
      , ('UFL.txt', 'ufl')
      , ('OFL.txt', 'ofl')

)

# ('apache', 'ufl', 'ofl')
LICENSE_DIRS = tuple(zip(*LICENSE_FILES_2_DIRS))[1]

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
ALLOWED_FILES = {
    'DESCRIPTION.en_us.html'
  , 'FONTLOG.txt'
  , *dict(LICENSE_FILES_2_DIRS).keys() # just the file names/keys
# METADATA.pb is not taken from upstream, technically we update the
# version in google fonts or create it newly
}

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

class UserAbortError(Exception):
  pass

class ProgramAbortError(Exception):
  pass

def _get_gf_dir_content(family_name: str) \
        -> typing.Tuple[typing.Union[str, None], typing.Dict[str, typing.Dict[str, typing.Any]]]:
  gfentry = get_gh_gf_family_entry(family_name)
  entries = None
  for license_dir in LICENSE_DIRS:
    if gfentry['data']['repository'][license_dir] is not None:
      entries = gfentry['data']['repository'][license_dir]['entries']
      break
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
# UP =  '\u001b[1A' # moves cursor 1 up
# reset = (CLEARLINE + UP) * num_linebeaks + TOLEFT

def user_input(question: str,
               options: 'OrderedDict[str, str]',
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
    not require user interaction. That way we can have an all -y/--no-confirm
    flag will always choose the default.

    yes: don't ask the user and use the default. If the value is a boolean
    *default* must be set, because we expect the boolean comes from the
    -y/--no-confirm flag and the programmers intent is to make this dialogue
    usable with that flag. If the value is None, we don't check if default is
    set. The boolean False versus None differentiation is intended as a self
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
                      , quiet: bool=False, use_template_schema=False):
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
        yaml_schema = upstream_yaml_schema if not use_template_schema \
                                      else upstream_yaml_template_schema
        last_good_conf = dirty_load(updated_upstream_conf, yaml_schema,
                                    allow_flow_style=True)
      except Exception as e:
        answer = user_input(f'The configuration did not parse ({type(e).__name__}):\n\n'
                       f'{e}',
                       OrderedDict(f='fix last edit',
                                   r='retry last edit',
                                   s='start all over',
                                   q='quit program'),
                       # the default should always be an option that does
                       # not require user interaction. That way we can
                       # have an all -y/--no-confirm flag that always
                       # chooses the default.
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

def _load_or_repl_upstream(upstream_yaml_text: str, yes: bool = False,
                           quiet: bool = False,
                           use_template_schema: bool = False
                          ) -> typing.Tuple[bool, YAML]:
  try:
    yaml_schema = upstream_yaml_schema if not use_template_schema \
                                    else upstream_yaml_template_schema
    return False, dirty_load(upstream_yaml_text, yaml_schema
                                        , allow_flow_style=True)
  except YAMLValidationError as err:
    answer = user_input('The configuration has schema errors:\n\n'
                     f'{err}',
                     OrderedDict(e='edit',
                                 q='quit program'),
                     default='q', yes=yes, quiet=quiet)
    if answer == 'q':
      raise UserAbortError()
    return True, _repl_upstream_conf(upstream_yaml_text, yes=yes, quiet=quiet,
                                    use_template_schema=use_template_schema)

def _upstream_conf_from_file(filename: str, yes: bool = False,
                                            quiet: bool = False,
                                            use_template_schema: bool = False
                                          ) -> YAML:
  """ If this parses there will be no repl, the user can edit
  the file directly on disk.
  If it doesn't parse, there's a chance to edit until the yaml parses
  and to change the result back to disk.
  """
  with open(filename, 'r+') as upstream_yaml_file:
    upstream_yaml_text = upstream_yaml_file.read()
    edited, upstream_conf_yaml = _load_or_repl_upstream(upstream_yaml_text
                                                  , yes=yes, quiet=quiet
                                                  , use_template_schema=use_template_schema)
    # "edited" is only true when upstream_yaml_text did not parse and
    # was then edited successfully.
    if edited:
      answer = user_input(f'Save changed file {filename}?',
            OrderedDict(y='yes',
                        n='no'),
            default='y', yes=yes, quiet=quiet)
      if answer == 'y':
        upstream_yaml_file.seek(0)
        upstream_yaml_file.truncate()
        upstream_yaml_file.write(upstream_conf_yaml.as_yaml())
  return upstream_conf_yaml


def _upstream_conf_from_scratch(family_name: typing.Union[str, None] = None,
                                yes: bool = False, quiet: bool = False,
                                use_template_schema:bool = False) -> YAML:

  upstream_conf_yaml = dirty_load(upstream_yaml_template, upstream_yaml_template_schema
                                            , allow_flow_style=True)
  if family_name is not None:
    upstream_conf_yaml['name'] = family_name

  if use_template_schema and yes: # for -u/--upstream-yaml
    return upstream_conf_yaml

  template = upstream_conf_yaml.as_yaml()
  return _repl_upstream_conf(template, yes=yes, quiet=quiet,
                                           use_template_schema=use_template_schema)

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
              # have an all -y/--no-confirm flag that always chooses the
              # default.
              default='o', yes=yes, quiet=quiet)
  if answer == 'q':
    raise UserAbortError()

  license_dir = {d[0]:d for d in LICENSE_DIRS}[answer]
  return license_dir


def _upstream_conf_from_yaml_metadata(
                              upstream_yaml_text: typing.Union[str, None],
                              metadata_text: typing.Union[str, None],
                              yes: bool = False,
                              quiet: bool = False,
                              use_template_schema: bool = False) -> YAML:
  """ Make a package when the family is in the google/fonts repo.
  Uses data preferred from upstream.yaml, if already present, and fills
  the gaps with data from METADATA.pb. This is to enable the removal of
  redundant data from upstream.yaml when it is in METADATA.pb, while also
  keeping upstream.yaml as the source of truth when in doubt.

  Eventually the common update path.
  """
  upstream_conf = {}
  if metadata_text is not None:
    metadata = fonts_pb2.FamilyProto()
    text_format.Parse(metadata_text, metadata)
    # existing repo, no upstream conf:
    # from METADATA.pb we use:
    #       designer, category, name
    # we won't get **yet**:
    #       source.repository_url
    # we still need the new stuff:
    #       branch, files
    upstream_conf.update({
      'designer': metadata.designer or None,
      'category': metadata.category or None,
      'name': metadata.name  or None,
      # we won't get this just now in most cases!
      'repository_url': metadata.source.repository_url or None,
    })
  if upstream_yaml_text is not None:
    # Only drop into REPL mode if can't parse and validate,
    # and use use_template_schema, because this is not the real deal
    # yet and we can be very forgiving.
    _, upstream_conf_yaml = _load_or_repl_upstream(upstream_yaml_text
                                                  , yes=yes, quiet=quiet
                                                  , use_template_schema=True)

    # remove None values:
    upstream_conf_yaml_data = {k:v for k,v in upstream_conf_yaml.data.items()
                                              if v is not None }
    # Override keys set by METADATA.pb before, if there's overlap.
    upstream_conf.update(upstream_conf_yaml_data)

  upstream_conf_yaml = dirty_load(upstream_yaml_template, upstream_yaml_template_schema
                                       , allow_flow_style=True)
  for k,v in upstream_conf.items():
    if v is None: continue
    upstream_conf_yaml[k] = v

  upstream_yaml_text = upstream_conf_yaml.as_yaml()
  assert upstream_yaml_text is not None

  # two cases:
  # - upstream.yaml may need an update by the user
  # - upstream.yaml may be invalid (updated schema, syntax)
  answer = user_input('Do you want to edit the current upstream configuration?',
                 OrderedDict(y='yes',
                             n='no'),
                 default='n', yes=yes, quiet=quiet)
  if answer == 'y':
    return _repl_upstream_conf(upstream_yaml_text, yes=yes, quiet=quiet ,
                              use_template_schema=use_template_schema)
  _, upstream_conf_yaml =  _load_or_repl_upstream(upstream_yaml_text, yes=yes,
                              quiet=quiet, use_template_schema=use_template_schema)
  return upstream_conf_yaml

def _get_upstream_info(file_or_family: str, is_file: bool, yes: bool,
                          quiet: bool, require_license_dir: bool = True,
                          use_template_schema: bool = False
                          ) -> typing.Tuple[YAML, typing.Union[str, None], dict]:
  # the first task is to acquire an upstream_conf, the license dir and
  # if present the available files for the family in the google/fonts repo.
  license_dir: typing.Union[str, None] = None
  upstream_conf_yaml = None
  gf_dir_content: typing.Dict[str, typing.Dict[str, typing.Any]] = {}

  if not is_file:
    family_name = file_or_family
  else:
    # load a upstream.yaml from disk
    upstream_conf_yaml = _upstream_conf_from_file(file_or_family,
                                      yes=yes, quiet=quiet,
                                      use_template_schema=use_template_schema)
    family_name = upstream_conf_yaml['name'].data

  # TODO:_get_gf_dir_content: is implemented as github graphql query,
  # but, as an alternative, could also be answered with a local
  # clone of the git repository. then _get_gf_dir_content needs a
  # unified api.
  # This could be pereferable if there's a google/fonts clone on the
  # system and e.g. if the user has a bad/no internet access or
  # is running into github api rate limits.
  #
  # if family_name can't be found:
  #    license_dir is None, gf_dir_content is an empty dict
  license_dir, gf_dir_content = _get_gf_dir_content(family_name)

  if license_dir is None:
    # The family is not specified or not found on google/fonts.
    # Can also be an user input error, but we don't handle this yet/here.
    print(f'Font Family "{family_name}" not found on Google Fonts.')
    if require_license_dir:
      license_dir = _user_input_license(yes=yes, quiet=quiet)
    if upstream_conf_yaml is None:
      # if there was no local upstream yaml
      upstream_conf_yaml = _upstream_conf_from_scratch(family_name,
                                        yes=yes, quiet=quiet,
                                        use_template_schema=use_template_schema)
  else:
    print(f'Font Family "{family_name}" is on Google Fonts under "{license_dir}".')

  if upstream_conf_yaml is not None:
    # loaded from_file or created from_scratch
    return upstream_conf_yaml, license_dir, gf_dir_content or {}

  upstream_yaml_text: typing.Union[str, None] = None
  metadata_text: typing.Union[str, None] = None

  if 'upstream.yaml' in gf_dir_content:
    # normal case
    print(f'Using upstream.yaml from google/fonts for {family_name}.')
    file_sha = gf_dir_content['upstream.yaml']['oid']
    response = get_github_gf_blob(file_sha)
    upstream_yaml_text = response.text

  if 'METADATA.pb' in gf_dir_content:
    file_sha = gf_dir_content['METADATA.pb']['oid']
    response = get_github_gf_blob(file_sha)
    metadata_text = response.text

  if upstream_yaml_text is None and metadata_text is None:
    raise Exception('Unexpected: can\'t use google fonts family data '
                    f'for {family_name}.')

  upstream_conf_yaml = _upstream_conf_from_yaml_metadata(upstream_yaml_text,
                                          metadata_text,
                                          yes=yes, quiet=quiet,
                                          use_template_schema=use_template_schema)

  return upstream_conf_yaml, license_dir, gf_dir_content or {}


def _edit_upstream_info(upstream_conf_yaml: YAML, file_or_family: str,
                        is_file: bool, yes:bool, quiet: bool)\
                        -> typing.Tuple[YAML, str, dict]:
  license_dir = None
  gf_dir_content: typing.Dict[str, typing.Dict[str, typing.Any]] = {}

  print(f'Edit upstream conf.')
  upstream_conf_yaml = _repl_upstream_conf(upstream_conf_yaml.as_yaml(),
                                                    yes=yes, quiet=quiet)
  if is_file:
    answer = user_input(f'Save changed file {file_or_family}?',
            OrderedDict(y='yes',
                        n='no'),
            default='y', yes=yes, quiet=quiet)
    if answer == 'y':
      with open(file_or_family, 'w') as upstream_yaml_file:
        upstream_yaml_file.write(upstream_conf_yaml.as_yaml())
  family_name = upstream_conf_yaml['name'].data
  # if family_name can't be found:
  #    license_dir is None, gf_dir_content is an empty dict
  license_dir, gf_dir_content = _get_gf_dir_content(family_name)
  if license_dir is None:
    # The family is not specified or not found on google/fonts.
    # Can also be an user input error, but we don't handle this yet/here.
    print(f'Font Family "{family_name}" not found on Google Fonts.')
    license_dir = _user_input_license(yes=yes, quiet=quiet)

  return upstream_conf_yaml, license_dir, gf_dir_content or {}

def _is_allowed_file(filename: str, no_whitelist: bool=False):
  # there are two places where .ttf files are allowed to go
  # we don't do filename/basename validation here, that's
  # a job for font bakery
  if filename.endswith('.ttf') \
      and os.path.dirname(filename) in ['', 'static']:
    return True # using this!
  elif filename not in ALLOWED_FILES \
                        and not no_whitelist: # this is the default
    return False
  return True

SKIP_NOT_PERMITTED = 'Target is not a permitted filename (see --no_whitelist):'
SKIP_SOURCE_NOT_FOUND = 'Source not found in upstream:'
SKIP_SOURCE_NOT_BLOB = 'Source is not a blob (blob=file):'
SKIP_COPY_EXCEPTION = 'Can\'t copy:'

def _copy_upstream_files_from_git(branch: str, files: dict, repo: pygit2.Repository
            , write_file_to_package: typing.Callable[[str, bytes], None]
            , no_whitelist: bool=False) \
              -> OrderedDict:

  skipped: 'OrderedDict[str, typing.List[str]]' = OrderedDict([
      (SKIP_NOT_PERMITTED, []),
      (SKIP_SOURCE_NOT_FOUND, []),
      (SKIP_SOURCE_NOT_BLOB, []),
      (SKIP_COPY_EXCEPTION, [])
  ])
  for source, target in files.items():
    # else: allow, write_file_to_package will raise errors if target is bad
    if not _is_allowed_file(target, no_whitelist):
      skipped[SKIP_NOT_PERMITTED].append(target)
      continue

    try:
      source_object = repo.revparse_single(f"{branch}:{source}")
    except KeyError as e:
      skipped[SKIP_SOURCE_NOT_FOUND].append(source)
      continue

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

def _copy_upstream_files_from_dir(source_dir: str, files: dict,
              write_file_to_package: typing.Callable[[str, bytes], None],
              no_whitelist: bool=False) -> OrderedDict:

  skipped: 'OrderedDict[str, typing.List[str]]' = OrderedDict([
      (SKIP_NOT_PERMITTED, []),
      (SKIP_SOURCE_NOT_FOUND, []),
      (SKIP_SOURCE_NOT_BLOB, []),
      (SKIP_COPY_EXCEPTION, [])
  ])
  for source, target in files.items():
    # else: allow, write_file_to_package will raise errors if target is bad
    if not _is_allowed_file(target, no_whitelist):
      skipped[SKIP_NOT_PERMITTED].append(target)
      continue

    try:
      with open(os.path.join(source_dir, source), 'rb') as f:
        source_data = f.read()
    except FileNotFoundError:
      skipped[SKIP_SOURCE_NOT_FOUND].append(source)
      continue
    except Exception as err:
      # e.g. IsADirectoryError
      skipped[SKIP_SOURCE_NOT_BLOB].append(f'{source} ({type(err).__name__})')
      continue

    try:
      write_file_to_package(target, source_data)
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
                                  upstream_commit_sha:str,
                                  no_source: bool) -> None:
  metadata_file_name = os.path.join(tmp_package_family_dir, 'METADATA.pb')
  try:
    subprocess.run(['gftools', 'add-font', tmp_package_family_dir]
                                , check=True, stdout=subprocess.PIPE
                                , stderr=subprocess.PIPE)
  except subprocess.CalledProcessError as e:
    print(str(e.stderr, 'utf-8'), file=sys.stderr)
    raise e

  metadata = fonts_pb2.FamilyProto()

  with open(metadata_file_name, 'rb') as fb:
    text_format.Parse(fb.read(), metadata)

  # make upstream_conf the source of truth for some entries
  metadata.name = upstream_conf['name']
  for font in metadata.fonts:
    font.name = upstream_conf['name']
  metadata.designer = upstream_conf['designer']
  metadata.category = upstream_conf['category']
  # metadata.date_added # is handled well

  if no_source:
    # remove in case it is present
    metadata.ClearField('source')
  else:
    metadata.source.repository_url = upstream_conf['repository_url']
    metadata.source.commit = upstream_commit_sha

  text_proto = text_format.MessageToString(metadata, as_utf8=True)
  with open(metadata_file_name, 'w') as f:
    f.write(text_proto)

def _create_package_content(package_target_dir: str, repos_dir: str,
        upstream_conf_yaml: YAML, license_dir: str, gf_dir_content:dict,
        no_source: bool, allow_build: bool, yes: bool, quiet: bool,
        no_whitelist: bool = False) -> str:
  print(f'Creating package with \n{_format_upstream_yaml(upstream_conf_yaml)}')
  upstream_conf = upstream_conf_yaml.data
  upstream_commit_sha = None

  family_name_normal = _family_name_normal(upstream_conf['name'])
  family_dir = os.path.join(license_dir, family_name_normal)
  package_family_dir = os.path.join(package_target_dir, family_dir)
  # putting state into functions, could be done with classes/methods as well
  write_file_to_package = functools.partial(_write_file_to_package,
                                            package_family_dir)
  file_in_package = functools.partial(_file_in_package,
                                      package_family_dir)
  # Get and add upstream files!
  upstream_dir_target = (
      f'{upstream_conf["repository_url"]}'
      f'__{upstream_conf["branch"]}'
      # Despite of '.' and '/' I'd expect the other replacements
      # not so important in this case.
    ) \
    .replace('://', '_') \
    .replace('/', '_') \
    .replace('.', '_') \
    .replace('\\', '_')

  local_repo_path_marker = 'local://'
  if upstream_conf['repository_url'].startswith(local_repo_path_marker):
    print(f'WARNING using "local://" hack for repository_url: {upstream_conf["repository_url"]}')
    local_path = upstream_conf['repository_url'][len(local_repo_path_marker):]
    upstream_dir = os.path.expanduser(local_path)
  else:
    upstream_dir = os.path.join(repos_dir, upstream_dir_target)
    if not os.path.exists(upstream_dir):
      # for super families it's likely that we can reuse the same clone
      # of the repository for all members
      _shallow_clone_git(upstream_dir, upstream_conf['repository_url']
                                    , upstream_conf['branch'])
  repo = pygit2.Repository(upstream_dir)

  upstream_commit = repo.revparse_single(upstream_conf['branch'])
  upstream_commit_sha = upstream_commit.hex

  # Copy all files from upstream_conf['files'] to package_family_dir
  # We are strict about what to allow, unexpected files
  # are not copied. Instead print a warning an suggest filing an
  # issue if the file is legitimate. A flag to explicitly
  # skip the whitelist check (--no_whitelist)
  # enables making packages even when new, yet unknown files are required).
  # Do we have a Font Bakery check for expected/allowed files? Would
  # be a good complement.
  if upstream_conf['build']:

    print(f'Found build command:\n  $ {upstream_conf["build"]}')
    if not allow_build:
      answer = user_input(f'Can\'t execute build command without explicit '
              'permission. Don\'t allow this lightly '
              'and review build command, build process and its dependencies prior. '
              'This support for building from sources is provisional, a '
              'discussion can be found at https://github.com/googlefonts/gftools/issues/231',
              OrderedDict(b='build',
                          q='quit program'),
              default='q', yes=yes, quiet=quiet)
      if answer == 'q':
        raise UserAbortError('Can\'t execute required build command. '
                              'Use --allow-build to allow explicitly.')
    with TemporaryDirectory() as tmp:
      print(f'Building...')
      subprocess.run(['git', 'clone', upstream_dir, tmp], check=True)
      subprocess.run(['bash', '-c', upstream_conf['build']]
                       , cwd=tmp
                       , check=True)
      print(f'DONE building!')
      skipped = _copy_upstream_files_from_dir(tmp, upstream_conf['files'],
                        write_file_to_package, no_whitelist=no_whitelist)
  else:
    skipped = _copy_upstream_files_from_git(upstream_conf['branch'],
                    upstream_conf['files'], repo, write_file_to_package,
                    no_whitelist=no_whitelist)
  if skipped:
    message = ['Some files from upstream_conf could not be copied.']
    for reason, items in skipped.items():
      message.append(reason)
      for item in items:
        message.append(f' - {item}')
    # The whitelist can be ignored using the flag no_whitelist flag,
    # but the rest should be fixed in the files map, because it's
    # obviously wrong, not working, configuration.
    # TODO: This case could (but should it?) be a repl-case to ask
    # interactively, if the no_whitelist flag should be used then,
    # if yes, _copy_upstream_files could be tried again. But given
    # that the use case for the flag is a narrow one, I doubt the
    # effort needed and the added complexity is worth it.
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
  _create_or_update_metadata_pb(upstream_conf, package_family_dir,
                                upstream_commit_sha, no_source)

  # create/update upstream.yaml
  # Remove keys that are also in METADATA.pb googlefonts/gftools#233
  # and also clear all comments.
  redundant_keys = {'name', 'category', 'designer', 'repository_url'}
  if no_source:
    # source is NOT in METADATA.pb so we want to keep it in upstream_conf
    # NOTE: there's another position where this has to be considered
    # i.e. in case of git as target when making a commit.
    redundant_keys.remove('repository_url')

  upstream_conf_stripped = OrderedDict((k, v) for k, v in upstream_conf.items() \
                                                  if k not in redundant_keys)
  # Don't keep an empty build key.
  if 'build' in upstream_conf_stripped and (upstream_conf_stripped['build'] == ''\
                or upstream_conf_stripped['build'] is None):
    del upstream_conf_stripped['build']
  upstream_conf_stripped_yaml = as_document(upstream_conf_stripped, upstream_yaml_stripped_schema)
  with open(os.path.join(package_family_dir, 'upstream.yaml'), 'w') as f:
    f.write(upstream_conf_stripped_yaml.as_yaml())
  print(f'DONE Creating package for {upstream_conf["name"]}!')
  return family_dir

def _check_git_target(target: str) -> None:
  try:
    repo = repo = pygit2.Repository(target)
  except Exception as e:
    raise ProgramAbortError(f'Can\'t open "{target}" as git repository. '
                            f'{e} ({type(e).__name__}).')
  repo_owner = 'google'
  repo_name = 'fonts'
  repo_name_with_owner = f'{repo_owner}/{repo_name}'
  remote_name_or_none = _find_github_remote(repo, repo_owner, repo_name, 'master')
  if remote_name_or_none is None:
    # NOTE: we could ask the user if we should add the missing remote.
    # This makes especially sense if the repository is a fork of
    # google/fonts and essentially has the same history/object database.
    # It would be very uncommon, probably unintended, if the repo is not
    # related to the google/fonts repo and fetching from that remote would
    # have to download a lot of new data, as well as probably create
    # confusing situations for the user when dealing with GitHub PRs etc.
    print (f'The git repository at target "{target}" has no remote for '
      f'GitHub {repo_name_with_owner}.\n'
      'You can add it by running:\n'
      f'$ cd {target}\n'
      f'$ git remote add googlefonts {GITHUB_REPO_SSH_URL(repo_name_with_owner=repo_name_with_owner)}.git\n'
      'For more context, run:\n'
      '$ git remote help')

    raise ProgramAbortError(f'The target git repository has no remote for '
              f'GitHub google/fonts.')

def _check_directory_target(target: str) -> None:
  if not os.path.isdir(target):
    raise ProgramAbortError(f'Target "{target}" is not a directory.')

def _check_target(is_gf_git: bool, target: str) -> None:
  if is_gf_git:
    return _check_git_target(target)
  else:
    return _check_directory_target(target)

def _git_tree_from_dir(repo: pygit2.Repository, tmp_package_family_dir: str) -> str:
  trees: typing.Dict[str, str] = {}
  for root, dirs, files in os.walk(tmp_package_family_dir, topdown=False):
    # if root == tmp_package_family_dir: rel_dir = '.'
    rel_dir = os.path.relpath(root, tmp_package_family_dir)
    treebuilder = repo.TreeBuilder()
    for filename in files:
      with open(os.path.join(root, filename), 'rb') as f:
        blob_id = repo.create_blob(f.read())
      treebuilder.insert(filename, blob_id, pygit2.GIT_FILEMODE_BLOB)
    for dirname in dirs:
      path = dirname if rel_dir == '.' else os.path.join(rel_dir, dirname)
      tree_id = trees[path]
      treebuilder.insert(dirname, tree_id, pygit2.GIT_FILEMODE_TREE)
    # store for use in later iteration, note, we're going bottom up
    trees[rel_dir] = treebuilder.write()
  return trees['.']

def _git_write_file(repo: pygit2.Repository, tree_builder: pygit2.TreeBuilder,
                                        file_path: str, data: bytes) -> None:
  blob_id = repo.create_blob(data)
  return _git_makedirs_write(repo, tree_builder, PurePath(file_path).parts,
                            blob_id, pygit2.GIT_FILEMODE_BLOB)


def _git_makedirs_write(repo: pygit2.Repository, tree_builder:pygit2.TreeBuilder,
          path:typing.Tuple[str, ...], git_obj_id: str, git_obj_filemode:int) -> None:
  name, rest_path = path[0], path[1:]
  if not rest_path:
    tree_builder.insert(name, git_obj_id, git_obj_filemode)
    return

  child_tree = tree_builder.get(name)
  try:
    child_tree_builder = repo.TreeBuilder(child_tree)
  except TypeError as e:
    # will raise TypeError if license_dir_tree is None i.e. not exisiting
    # but also if child_tree is not a pygit2.GIT_FILEMODE_TREE

    # os.makedirs(name, exists_ok=True) would raise FileExistsError if
    # it is tasked to create a directory where a file already exists
    # It seems unlikely that we want to override existing files here
    # so I copy that behavior.
    if child_tree is not None:
      # FileExistsError is an OSError so it's probably misused here
      raise FileExistsError(f'The git entry {name} exists as f{child_tree.type_str}.')
    child_tree_builder = repo.TreeBuilder()

  _git_makedirs_write(repo, child_tree_builder, rest_path, git_obj_id, git_obj_filemode)
  child_tree_id = child_tree_builder.write()
  tree_builder.insert(name, child_tree_id,  pygit2.GIT_FILEMODE_TREE)

def _git_copy_dir(repo: pygit2.Repository, tree_builder: pygit2.TreeBuilder,
                      source_dir:str, target_dir:str) -> None:
  # This is a new tree, i.e. not based on an existing tree.
  tree_id = _git_tree_from_dir(repo, source_dir)

  # Here we insert into an existing tree.
  _git_makedirs_write(repo, tree_builder, PurePath(target_dir).parts,
                            tree_id, pygit2.GIT_FILEMODE_TREE)

# thanks https://stackoverflow.com/a/1094933
def _sizeof_fmt(num, suffix='B'):
  for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
    if abs(num) < 1024.0:
      return "%3.1f%s%s" % (num, unit, suffix)
    num /= 1024.0
  return "%.1f%s%s" % (num, 'Yi', suffix)

def _push(repo: pygit2.Repository, url: str, local_branch_name: str,
          remote_branch_name: str, force: bool):
  full_local_ref = local_branch_name if local_branch_name.find('refs/') == 0 \
                                     else f'refs/heads/{local_branch_name}'
  full_remote_ref = f'refs/heads/{remote_branch_name}'
  ref_spec = f'{full_local_ref}:{full_remote_ref}'
  if force:
    # ref_spec for force pushing must include a + at the start.
    ref_spec = f'+{ref_spec}'

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
  subprocess.run(['git', 'push', url, ref_spec],
                    cwd=repo.path,
                    check=True,
                    stdout=subprocess.PIPE)

  #if callbacks.rejected_push_message is not None:
  #  raise Exception(callbacks.rejected_push_message)

def get_github_open_pull_requests(repo_owner: str, repo_name: str,
                pr_head: str, pr_base_branch: str) -> typing.Union[typing.List]:
  url = (f'{GITHUB_V3_REST_API}/repos/{repo_owner}/{repo_name}/pulls?state=open'
         f'&head={urllib.parse.quote(pr_head)}'
         f'&base={urllib.parse.quote(pr_base_branch)}')
  github_api_token = _get_github_api_token()
  headers = {'Authorization': f'bearer {github_api_token}'}

  response = requests.get(url, headers=headers)
  # print(f'response headers: {pprint.pformat(response.headers, indent=2)}')
  # raises requests.exceptions.HTTPError
  response.raise_for_status()
  json = response.json()
  if 'errors' in json:
    errors = pprint.pformat(json['errors'], indent=2)
    raise Exception(f'GitHub REST query failed:\n {errors}')
  return json

def create_github_pull_request(repo_owner: str, repo_name: str, pr_head: str,
                               pr_base_branch: str, title: str, body: str):
  url = f'{GITHUB_V3_REST_API}/repos/{repo_owner}/{repo_name}/pulls'
  payload = {
    'title': title,
    'body': body,
    'head': pr_head,
    'base': pr_base_branch,
    'maintainer_can_modify': True
  }
  return _post_github(url, payload)

def create_github_issue_comment(repo_owner: str, repo_name: str,
                                issue_number: int, pr_comment_body: str):
  url = (f'{GITHUB_V3_REST_API}/repos/{repo_owner}/{repo_name}/issues'
          f'/{issue_number}/comments')
  payload = {
    'body': pr_comment_body
  }
  return _post_github(url, payload)

def create_github_issue(repo_owner: str, repo_name: str,
                        pr_title: str, pr_body: str):
  url = (f'{GITHUB_V3_REST_API}/repos/{repo_owner}/{repo_name}/issues')
  payload = {
    'title': pr_title,
    'body': pr_body
  }
  return _post_github(url, payload)

def _make_pr(repo: pygit2.Repository, local_branch_name: str,
                                  pr_upstream: str, push_upstream: str,
                                  pr_title: str, pr_message_body: str):
  print('Making a Pull Request …')
  if not push_upstream:
    push_upstream = pr_upstream

  push_owner, _push_repo = push_upstream.split('/')
  pr_owner, pr_repo = pr_upstream.split('/')
  url = GITHUB_REPO_SSH_URL(repo_name_with_owner=push_upstream)

  remote_branch_name = local_branch_name
  # We must only allow force pushing/general pushing to branch names that
  # this tool *likely* created! Otherwise, we may end up force pushing
  # to master! Hence: we expect a prefix for remote_branch_name indicating
  # this tool created it.
  if remote_branch_name.find(GIT_NEW_BRANCH_PREFIX) != 0:
    remote_branch_name = (f'{GIT_NEW_BRANCH_PREFIX}'
                          f'{remote_branch_name.replace(os.sep, "_")}')

  print('git push:\n'
          f'  url is {url}\n'
          f'  local branch name is {local_branch_name}\n'
          f'  remote branch name is {remote_branch_name}\n'
  )
  # Always force push?
  # If force == False and we update an existing remote:
  #   _pygit2.GitError: cannot push non-fastforwardable reference
  # But I don't use the --force flag here, because I believe this is
  # very much the standard case, i.e. that we update existing PRs.
  _push(repo, url, local_branch_name, remote_branch_name, force=True)
  print('DONE git push!')

  pr_head = f'{push_owner}:{remote_branch_name}'
  pr_base_branch = 'master'  # currently we always do PRs to master
    #_updateUpstream(prRemoteName, prRemoteRef))
    #// NOTE: at this point the PUSH was already successful, so the branch
    #// of the PR exists or if it existed it has changed.
  open_prs = get_github_open_pull_requests(pr_owner, pr_repo, pr_head,
                                           pr_base_branch)

  if not len(open_prs):
    # No open PRs, creating …
    result = create_github_pull_request(pr_owner, pr_repo, pr_head,
                                pr_base_branch, pr_title, pr_message_body)
    print(f'Created a PR #{result["number"]} {result["html_url"]}')
  else:
    # found open PR
    pr_issue_number = open_prs[0]['number']
    pr_comment_body = f'Updated\n\n## {pr_title}\n\n---\n{pr_message_body}'
    result = create_github_issue_comment(pr_owner, pr_repo, pr_issue_number,
                                                        pr_comment_body)
    print(f'Created a comment in PR #{pr_issue_number} {result["html_url"]}')

def _get_root_commit(repo: pygit2.Repository, base_remote_branch:str,
                                  tip_commit: pygit2.Commit) -> pygit2.Commit:
  for root_commit in repo.walk(tip_commit.id,
                  pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_TIME):
    try:
      # If it doesn't raise KeyError i.e. root_commit is contained in
      # our base_remote_branch and not part of the PR.
      return repo.branches.remote.with_commit(root_commit)[base_remote_branch].peel()
    except KeyError:
      continue
    break;

def _get_change_info_from_diff(repo: pygit2.Repository, root_tree: pygit2.Tree,
                                            tip_tree: pygit2.Tree) -> typing.Dict:
  # I probably also want the changed files between root_commit and tip commit
  diff =  repo.diff(root_tree, tip_tree)
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
    if delta.status_char() == 'D':
      all_touched_files.add(delta.old_file.path)
    else:
      all_touched_files.add(delta.new_file.path)
  touched_family_dirs = set()
  for filename in all_touched_files:
    for dirname in LICENSE_DIRS:
      if filename.startswith(f'{dirname}{os.path.sep}'):
        # items are e.g. ('ofl', 'gelasio')
        touched_family_dirs.add(tuple(filename.split(os.path.sep)[:2]))
        break
  family_changes_dict = {}
  for dir_path_tuple in touched_family_dirs:
    family_tree: pygit2.Tree = tip_tree
    for pathpart in dir_path_tuple:
      family_tree = family_tree / pathpart

    metadata_blob: pygit2.Blob = family_tree / 'METADATA.pb'
    metadata = fonts_pb2.FamilyProto()
    text_format.Parse(metadata_blob.data, metadata)

    # get the version
    first_font_file_name = metadata.fonts[0].filename
    first_font_blob: pygit2.Blob = family_tree / first_font_file_name
    first_font_file = BytesIO(first_font_blob.data)
    ttFont = TTFont(first_font_file)
    version:typing.Union[None, str] = None
    NAME_ID_VERSION = 5
    for entry in ttFont['name'].names:
      if entry.nameID == NAME_ID_VERSION:
        # just taking the first instance
        version = entry.string.decode(entry.getEncoding())
        if version:
          break

    # repoNameWithOwner
    prefix  = 'https://github.com/'
    suffix = '.git'
    repoNameWithOwner: typing.Union[None,str] = None
    if metadata.source.repository_url.startswith(prefix):
      repoNameWithOwner = '/'.join(metadata.source.repository_url[len(prefix):]
                                           .split('/')[0:2])
      if repoNameWithOwner.endswith(suffix):
        repoNameWithOwner = repoNameWithOwner[:-len(suffix)]
    commit_url: typing.Union[None,str] = None
    if repoNameWithOwner:
      commit_url = f'https://github.com/{repoNameWithOwner}/commit/{metadata.source.commit}'

    family_changes_dict['/'.join(dir_path_tuple)] = {
      'family_name': metadata.name,
      'repository': metadata.source.repository_url,
      'commit': metadata.source.commit,
      'version': version or '(unknown version)',
      'repoNameWithOwner': repoNameWithOwner,
      'commit_url': commit_url
    }
  return family_changes_dict

def _title_message_from_diff(repo: pygit2.Repository, root_tree: pygit2.Tree,
                            tip_tree: pygit2.Tree) -> typing.Tuple[str, str]:
  family_changes_dict = _get_change_info_from_diff(repo, root_tree, tip_tree)
  title = []
  body = []
  for _, fam_entry in family_changes_dict.items():
    title.append(f'{fam_entry["family_name"]}: {fam_entry["version"]} added')
    commit = fam_entry['commit_url'] or fam_entry['commit']
    body.append(f'* {fam_entry["family_name"]} '
               f'{fam_entry["version"]} taken from the upstream repo '
               f'{fam_entry["repository"]} at commit {commit}.'
               )
  return '; '.join(title), '\n'.join(body)

def _git_get_path(tree: pygit2.Tree, path: str) -> pygit2.Object:
  last = tree
  for pathpart in PurePath(path).parts:
    last = last / pathpart
  return last

def _git_make_commit(repo: pygit2.Repository, add_commit: bool, force: bool,
          yes: bool, quiet: bool, local_branch: str, remote_name: str,
          base_remote_branch: str, tmp_package_family_dir: str,
          family_dir: str, no_source: bool):
  base_commit = None
  if add_commit:
    try:
      base_commit = repo.branches.local[local_branch].peel()
    except KeyError as e:
      pass

  if not base_commit:
    #fetch! make sure we're on the actual gf master HEAD
    _git_fetch_master(repo, remote_name)
    # base_commit = repo.revparse_single(f'refs/remotes/{base_remote_branch}')
    # same but maybe better readable:
    base_commit = repo.branches.remote[base_remote_branch].peel()

  # Maybe I can start with the commit tree here ...
  treeBuilder = repo.TreeBuilder(base_commit.tree)
  _git_copy_dir(repo, treeBuilder, tmp_package_family_dir, family_dir)

  # create the commit
  user_name = list(repo.config.get_multivar('user.name'))[0]
  user_email = list(repo.config.get_multivar('user.email'))[0]
  author = pygit2.Signature(user_name, user_email)
  committer = pygit2.Signature(user_name, user_email)

  new_tree_id = treeBuilder.write()
  new_tree: pygit2.Tree = repo.get(new_tree_id)
  title, body = _title_message_from_diff(repo, base_commit.tree, new_tree)

  commit_id = repo.create_commit(
          None,
          author, committer,
          f'[gftools-packager] {title}\n\n{body}',
          new_tree_id,
          [base_commit.id] # parents
  )

  if no_source:
    # remove source from METADATA.pb in an extra new commit, this will make it
    # easy to track these changes and to revert them when feasible.
    treeBuilder = repo.TreeBuilder(new_tree)
    # read METADATA.pb
    metadata_filename = os.path.join(family_dir, 'METADATA.pb')
    metadata_blob = _git_get_path(new_tree, metadata_filename)
    metadata = fonts_pb2.FamilyProto()
    text_format.Parse(metadata_blob.data, metadata)
    # delete source fields
    repository_url = metadata.source.repository_url
    metadata.ClearField('source')
    # write METADATA.pb
    text_proto = text_format.MessageToString(metadata, as_utf8=True)
    _git_write_file(repo, treeBuilder, metadata_filename, text_proto)
    # read upstream.yaml
    upstream_filename = os.path.join(family_dir, 'upstream.yaml')
    upstream_text = _git_get_path(new_tree, upstream_filename).data.decode('utf-8')
    upstream_conf_yaml = dirty_load(upstream_text, upstream_yaml_stripped_schema,
                                                    allow_flow_style=True)
    # preserve the info: transfer from METADATA.pb
    upstream_conf_yaml['repository_url'] = repository_url
    # write upstream.yaml
    _git_write_file(repo, treeBuilder, upstream_filename, upstream_conf_yaml.as_yaml())
    # commit
    new_tree_id = treeBuilder.write()
    commit_id = repo.create_commit(
            None,
            author, committer,
            f'[gftools-packager] {family_dir} remove METADATA "source".  google/fonts#2587',
            new_tree_id,
            [commit_id] # parents
    )


  commit = repo.get(commit_id)
  # create branch or add to an existing one if add_commit
  while True:
    try:
      repo.branches.local.create(local_branch, commit, force=add_commit or force)
    except pygit2.AlreadyExistsError:
      # _pygit2.AlreadyExistsError: failed to write reference
      #     'refs/heads/gftools_packager_ofl_gelasio': a reference with
      #     that name already exists.
      answer = user_input(f'Can\'t override existing branch {local_branch}'
                          ' without explicit permission.',
              OrderedDict(f='force override',
                          q='quit program'),
              default='q', yes=yes, quiet=quiet)
      if answer == 'q':
        raise UserAbortError(f'Can\'t override existing branch {local_branch}. '
                            'Use --branch to specify another branch name. '
                            'Use --force to allow explicitly.')
      else: # answer == 'f'
        force = True
        continue
    break

  # only for reporting
  target_label = f'git branch {local_branch}'
  package_contents = []
  for root, dirs, files in _git_tree_walk(family_dir, commit.tree):
    for filename in files:
      entry_name = os.path.join(root, filename)
      filesize = commit.tree[entry_name].size
      package_contents.append((entry_name, filesize))
  _print_package_report(target_label, package_contents)

def _packagage_to_git(tmp_package_family_dir: str, target: str, family_dir: str,
                     branch: str, force:bool, yes: bool, quiet: bool,
                     add_commit: bool, no_source: bool) -> None:

  repo = pygit2.Repository(target)
  # we checked that it exists earlier!
  remote_name = _find_github_remote(repo, 'google', 'fonts', 'master')
  base_remote_branch = f'{remote_name}/master'
  if remote_name is None:
    raise Exception('No remote found for google/fonts master.')

  _git_make_commit(repo, add_commit, force, yes, quiet, branch,
                   remote_name, base_remote_branch, tmp_package_family_dir,
                   family_dir, no_source)


def _dispatch_git(target: str, target_branch: str,pr_upstream: str,
                  push_upstream: str) -> None:
  repo = pygit2.Repository(target)
  # we checked that it exists earlier!
  remote_name = _find_github_remote(repo, 'google', 'fonts', 'master')
  base_remote_branch = f'{remote_name}/master'
  if remote_name is None:
    raise Exception('No remote found for google/fonts master.')

  git_branch: pygit2.Branch = repo.branches.local[target_branch]
  tip_commit: pygit2.Commit = git_branch.peel()
  root_commit: pygit2.Commit = _get_root_commit(repo, base_remote_branch, tip_commit)
  pr_title, _ = _title_message_from_diff(repo, root_commit.tree, tip_commit.tree)
  if not pr_title:
    # Happens e.g. if we have a bunch of commits that revert themselves,
    # to me this happened in development, in a for production use very unlikely
    # situation.
    # But can also happen if we PR commits that don't do changes in family
    # dirs. In these cases the PR author should probably come up with a
    # better title than this placeholder an change it in the GitHub web-GUI.
    pr_title = '(UNKNOWN gftools-packager: found no family changes)'

  current_commit = tip_commit
  messages = []
  while current_commit.id != root_commit.id:
    messages.append(f' {current_commit.short_id}: {current_commit.message}')
    current_commit = current_commit.parents[0]
  pr_message_body  = '\n\n'.join(reversed(messages))

  _make_pr(repo, target_branch, pr_upstream, push_upstream,
                                            pr_title, pr_message_body)

def _packagage_to_dir(tmp_package_family_dir: str, target: str,
                  family_dir: str, force: bool, yes: bool, quiet: bool):
  # target is a directory:
  target_family_dir = os.path.join(target, family_dir)
  if os.path.exists(target_family_dir):
    if not force:
      answer = user_input(f'Can\'t override existing directory {target_family_dir}'
                          ' without explicit permission.',
              OrderedDict(f='force override',
                          q='quit program'),
              default='q', yes=yes, quiet=quiet)
      if answer == 'q':
        raise UserAbortError('Can\'t override existing directory '
                              f'{target_family_dir}. '
                              'Use --force to allow explicitly.')
    shutil.rmtree(target_family_dir)
  else: # not exists
    os.makedirs(os.path.dirname(target_family_dir), exist_ok=True)
  shutil.move(tmp_package_family_dir, target_family_dir)

  # only for reporting
  target_label = f'directory {target}'
  package_contents = []
  for root, dirs, files in os.walk(target_family_dir):
    for filename in files:
      full_path = os.path.join(root, filename)
      entry_name = os.path.relpath(full_path, target)
      filesize = os.path.getsize(full_path)
      package_contents.append((entry_name, filesize))
  print(f'Package Directory: {target_family_dir}')
  _print_package_report(target_label, package_contents)

def _write_upstream_yaml_backup(upstream_conf_yaml: YAML) -> str:
  family_name_normal = _family_name_normal(upstream_conf_yaml['name'].data)
  count = 0
  while True:
    counter = '' if count == 0 else f'_{count}'
    filename = f'./{family_name_normal}.upstream{counter}.yaml'
    try:
      # 'x': don't override existing files
      with open(filename, 'x') as f:
        f.write(upstream_conf_yaml.as_yaml())
    except FileExistsError:
      # retry until the file could be created, file name changes
      count += 1
      continue
    break
  return filename

def _packages_to_target(tmp_package_dir: str, family_dirs: typing.List[str],
                        target: str, is_gf_git: bool,
                        branch: str, force: bool,
                        yes: bool, quiet: bool, add_commit: bool,
                        no_source: bool) ->None:
  for i, family_dir in enumerate(family_dirs):
    tmp_package_family_dir = os.path.join(tmp_package_dir, family_dir)
    # NOTE: if there are any files outside of family_dir that need moving
    # that is not yet supported! The reason is, there's no case for this
    # yet. So, if _create_package_content is changed to put files outside
    # of family_dir, these targets will have to follow and implement it.
    if is_gf_git:
      if i > 0:
        add_commit = True
      _packagage_to_git(tmp_package_family_dir, target, family_dir,
                               branch, force, yes, quiet, add_commit, no_source)
    else:
      _packagage_to_dir(tmp_package_family_dir, target, family_dir,
                               force, yes, quiet)


def _branch_name_from_family_dirs(family_dirs: typing.List[str]) -> str:
  if len(family_dirs) == 1:
    return f'{GIT_NEW_BRANCH_PREFIX}{family_dirs[0].replace(os.sep, "_")}'

  by_licensedir: typing.Dict[str, typing.List[str]] = {};
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
  hash_hex_ini = sha1(full_branch_name.encode('utf-8')).hexdigest()[:10]
  # This is the shortened version from above:
  # gftools_packager_apache_arimo-cherrycreamsoda_ofl_d79615d347
  return f'{full_branch_name[:max_len-11]}_{hash_hex_ini}'

def _file_or_family_is_file(file_or_family: str) -> bool:
  return file_or_family.endswith('.yaml') or \
         file_or_family.endswith('.yml') # .yml is common, too

def _output_upstream_yaml(file_or_family: typing.Union[str, None], target: str,
                    yes: bool, quiet: bool, force: bool) -> None:
  if not file_or_family:
     # just use the template
     upstream_conf_yaml =  dirty_load(upstream_yaml_template, upstream_yaml_template_schema
                                            , allow_flow_style=True)
  else:
    is_file = _file_or_family_is_file(file_or_family)
    upstream_conf_yaml, _, _ = _get_upstream_info(file_or_family, is_file,
                                    yes, quiet, require_license_dir=False,
                                    use_template_schema=True)
  # save!
  while True:
    try:
      with open(target, 'x' if not force else 'w') as f:
        f.write(upstream_conf_yaml.as_yaml())
      break
    except FileExistsError:
      if not force:
        answer = user_input(f'Can\'t override existing target file {target}'
                          ' without explicit permission.',
              OrderedDict(f='force override',
                          q='quit program'),
              default='q', yes=yes, quiet=quiet)
      if answer == 'q':
        raise UserAbortError('Can\'t override existing target file '
                              f'{target}. '
                              'Use --force to allow explicitly.')
      else: # answer == 'f'
        force = True
        continue
  print(f'DONE upstream conf saved as {target}!')


def make_package(file_or_families: typing.List[str], target: str, yes: bool,
                 quiet: bool, no_whitelist: bool, is_gf_git: bool, force: bool,
                 add_commit: bool, pr: bool, pr_upstream: str,
                 push_upstream: str, upstream_yaml: bool, no_source: bool,
                 allow_build: bool, branch: typing.Union[str, None]=None):

  if upstream_yaml:
    return _output_upstream_yaml(file_or_families[0] if file_or_families else None,
                            target, yes, quiet, force)
  # some flags can be set implicitly
  pr = pr or bool(push_upstream) or bool(pr_upstream)
  # set default
  if not pr_upstream: pr_upstream = 'google/fonts'

  is_gf_git = is_gf_git or bool(branch) or add_commit or pr
  # Basic early checks. Raises if target does not qualify.
  _check_target(is_gf_git, target)

  # note: use branch if it is explicit (and if is_gf_git)
  target_branch = branch if branch is not None else ''

  family_dirs: typing.List[str] = []
  with TemporaryDirectory() as tmp_dir:
    tmp_package_dir = os.path.join(tmp_dir, 'packages')
    os.makedirs(tmp_package_dir, exist_ok=True)
    tmp_repos_dir = os.path.join(tmp_dir, 'repos')
    os.makedirs(tmp_repos_dir, exist_ok=True)

    for file_or_family in file_or_families:
      is_file = _file_or_family_is_file(file_or_family)
      edit = False
      while True: # repl
        if not edit:
          ( upstream_conf_yaml, license_dir,
            gf_dir_content ) = _get_upstream_info(file_or_family, is_file,
                                                                  yes, quiet)
        else:
          ( upstream_conf_yaml, license_dir,
            gf_dir_content ) = _edit_upstream_info(upstream_conf_yaml,
                                        file_or_family, is_file, yes, quiet)
          edit = False # reset
        assert isinstance(license_dir, str)
        try:
          family_dir = _create_package_content(tmp_package_dir, tmp_repos_dir,
                                upstream_conf_yaml, license_dir,
                                gf_dir_content,
                                # if is_gf_git source is removed in an
                                # extra commit
                                no_source and not is_gf_git,
                                allow_build, yes, quiet, no_whitelist)
          family_dirs.append(family_dir)
        except UserAbortError as e:
          # The user aborted already, no need to bother any further.
          # FIXME: however, we don't get to the point where we can save
          # the upstream conf to disk, and that may be desirable here!
          raise e
        except Exception:
          error_io = StringIO()
          traceback.print_exc(file=error_io)
          error_io.seek(0)
          answer = user_input(f'Upstream conf caused an error:'
                              f'\n-----\n\n{error_io.read()}\n-----\n'
                              'How do you want to proceed?',
                  OrderedDict(e='edit upstream conf and retry',
                              q='raise and quit program'),
                  default='q', yes=yes, quiet=quiet)
          if answer == 'q':
            if not yes:
              # Should be possible to save to original file if is_file
              # but we should give that option only if the file would change.
              # Also, in edit_upstream_info it is possible to save to the
              # original file.
              answer = user_input('Save upstream conf to disk?\nIt can be '
                                   'annoying having to redo all changes, which '
                                   'will be lost if you choose no.\n'
                                   'The saved file can be edited and used with '
                                   'the --file option.' ,
                  OrderedDict(y='yes—save to disk',
                              n='no—discard changes'),
                  default='y', yes=yes, quiet=quiet)
              if answer == 'y':
                upstream_yaml_backup_filename = _write_upstream_yaml_backup(
                                                          upstream_conf_yaml)
                print(f'Upstream conf has been saved to: {upstream_yaml_backup_filename}')
            raise UserAbortError()
          else:
            # answer == 'e'
            # continue loop: go back to _get_upstream_info
            edit = True
            continue
        # Done with file_or_family!
        break # break the REPL while loop.
    if not family_dirs:
      print('No families to package.')
    # done with collecting data for all file_or_families

    if is_gf_git:
      # need to have a unified branch for all file_or_families ...
      # if there are more than one families ...
      if not branch:
        target_branch = _branch_name_from_family_dirs(family_dirs)
    _packages_to_target(tmp_package_dir, family_dirs, target, is_gf_git,
                        target_branch, force, yes, quiet, add_commit, no_source)

  if pr and is_gf_git:
    _dispatch_git(target, target_branch, pr_upstream, push_upstream)


def _print_package_report (target_label: str,
            package_contents: typing.List[typing.Tuple[str, int]]) -> None:
  print(f'Created files in {target_label}:')
  for entry_name, filesize in package_contents:
    filesize_str = filesize
    print(f'   {entry_name} {_sizeof_fmt(filesize_str)}')

def _find_github_remote(repo: pygit2.Repository, owner: str, name: str,
          branch: typing.Union[str, None] = None) -> typing.Union[str, None]:
  """
  Find a remote-name that is a good fit for the GitHub owner and repo-name.
  A good fit is when we can use it to fetch/push from/to GitHubs repository
  to/from the `branch` if branch is given or any branch if `branch` is None.

  Returns remote-name or None
  """
  searched_repo = f'{owner}/{name}'
  # If we plan to also push to these, it is important which
  # remote url we choose, esp. because of authentication methods.
  # I'd try to pick remotes after the order below, e.g. first the
  # ssh based urls, then the https url, because human users will
  # likely have a working ssh setup if they are pushing to github,
  # An environment like the FBD can have complete control over the
  # remotes it uses.
  # If more control is needed we'll have to add it.
  accepted_remote_urls = [
     GITHUB_REPO_SSH_URL(repo_name_with_owner=searched_repo), # ssh
     f'ssh://git@github.com/{searched_repo}', # ssh
     f'https://github.com/{searched_repo}.git', # token (auth not needed for fetch)
  ]
  candidates = dict() # url->remote

  # NOTE: a shallow cloned repository has no remotes.
  for remote in repo.remotes:
    if remote.url not in accepted_remote_urls or remote.url in candidates:
      continue
    # To be honest, we'll likely encounter the (default) first refspec case
    # in almost all matching remotes.
    accepted_refspecs = {
      f'+refs/heads/*:refs/remotes/{remote.name}/*'
    }
    if branch:
      accepted_refspecs.add(
                  f'+refs/heads/{branch}:refs/remotes/{remote.name}/{branch}')
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
      self.rejected_push_message = (f'Update to reference {refname} got '
                                    f'rejected with message {message}')

  def credentials(self, url, username_from_url, allowed_types):
    if allowed_types & pygit2.credentials.GIT_CREDENTIAL_USERNAME:
      print('GIT_CREDENTIAL_USERNAME')
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

def _git_fetch_master(repo: pygit2.Repository, remote_name: str) -> None:

  # perform a fetch
  print(f'Start fetching {remote_name}/master')
  # fetch(refspecs=None, message=None, callbacks=None, prune=0)
  # using just 'master' instead of 'refs/heads/master' works as well

  # This fails on MacOS, just as any oother pygit2 network interaction.
  # remote = repo.remotes[remote_name]
  # stats = remote.fetch(['refs/heads/master'], callbacks=PYGit2RemoteCallbacks())

  subprocess.run(['git', 'fetch', remote_name, 'master'],
    cwd=repo.path,
    check=True,
    stdout=subprocess.PIPE
  )


  print(f'DONE fetch') # {_sizeof_fmt(stats.received_bytes)} '
        # f'{stats.indexed_objects} receive dobjects!')

@contextmanager
def _create_tmp_remote(repo: pygit2.Repository, url:str) -> typing.Iterator[pygit2.Remote]:
  remote_name_template = 'tmp_{}'.format
  # create a new remote (with unique name)
  i = 0
  tmp_name: str
  remote: pygit2.Remote
  # try to create and expect to fail if it exists
  while True:
    try:
      tmp_name = remote_name_template(i)
      remote = repo.remotes.create(tmp_name, url)
      break
    except ValueError as e:
      # raises ValueError: remote '{tmp_name}' already exists
      if 'already exists' not in f'{e}':
        # ValueError is rather generic, maybe another condition can raise
        # it, hence I check for the phrase "already exists" as well.
        # I think something similar to FileExistsError would have been better
        # to raise here. Though that's an OSError.
        raise e
      i += 1
      continue
  try:
    yield remote
  finally:
    repo.remotes.delete(tmp_name)

# note: currently unused, example!
# def _git_create_remote(repo: pygit2.Repository) -> None:
#   # If we did not find a suitable remote, we can add it.
#   # If remote_name exists: repo.remotes.creat raises:
#   # "ValueError: remote 'upstream' already exists"
#   default_remote_name = 'upstream'
#
#   remote_name = input(f'Creating a git remote.\nEnter remote name (default={default_remote_name}),a=abort:')
#   if remote_name == 'a':
#     raise UserAbortError()
#   remote_name = remote_name or default_remote_name
#
#   searched_repo = 'google/fonts'
#   url =  f'git@github.com:{searched_repo}.git'
#   # url =  f'ssh://git@github.com/{searched_repo}'
#   # url = f'https://github.com/{searched_repo}.git'
#
#   refspecs_candidates = {
#       '1': f'+refs/heads/*:refs/remotes/{remote_name}/*'
#     , '2': f'+refs/heads/master:refs/remotes/{remote_name}/master'
#   }
#   print('Pick a fetch refspec for the remote:')
#   print(f'1: {refspecs_candidates["1"]} (default)')
#   print(f'2: {refspecs_candidates["2"]} (minimal)')
#   refspec = input(f'1(default),2,a=abort:').strip()
#   if refspec == 'a':
#     raise UserAbortError()
#   fetch_refspec = refspecs_candidates[refspec or '1']
#
#   # raises ValueError: remote 'upstream' already exists
#   # fetch argument will apply the default refspec if it is None
#   repo.remotes.create(remote_name, url, fetch=fetch_refspec)
