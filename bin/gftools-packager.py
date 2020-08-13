#!/usr/bin/env python3
"""Tool to take files from a font family project upstream git repository
to the google/fonts GitHub repository structure, taking care of all the details.

Documentation at gftools/docs/gftools-packager/README.md
"""

import sys
from gftools import packager
from gftools.packager import UserAbortError, ProgramAbortError
import argparse

def _ansi_bold(text:str) ->str:
  return f'\033[1m{text}\033[0m'

parser = argparse.ArgumentParser(
    prog='gftools packager',
    description='Package upstream font families for Google Fonts.',
    epilog=f'{_ansi_bold("Documentation:")} '
           'https://github.com/googlefonts/gftools/tree/master/docs/gftools-packager'
           '\n'
           f'{_ansi_bold("Issues:")} '
           'https://github.com/googlefonts/gftools/issues'
)

parser.add_argument(
            'file_or_families',
            metavar='name',
            type=str,
            nargs='*',
            help='The family name(s) or file name(s) of upstream conf yaml '
                 'files to be packaged. If a name ends with the ".yaml" suffix, '
                 'it\'s treated as a file otherwise it\'s used as family name '
                 'and  packager tries to gather upstream configuration from '
                 'the google/fonts GitHub repository. If no name is specified, '
                 'no package will be created. This is useful to only make a '
                 'PR from an already created branch, not adding a commit, '
                 'use -b/--branch and see see -p/--pr.')
parser.add_argument(
            '-f','--force',
            action='store_true',
            help='This allows the program to manipulate/change/delete data '
                 'in [target]. Without this flag only adding new items '
                 '(depends: files, directories or branches, trees, blobs) '
                 'is allowed.')
parser.add_argument(
            '-y',
            '--no-confirm',
            dest='yes',
            action='store_true',
            help='Don\'t require user interaction, by answering with the '
                 'default always. Removes all interactivity.')
parser.add_argument(
            '-q',
            '--quiet',
            action='store_true',
            help='Don\'t print user interaction dialogues when -y/--no-confirm is used.')
parser.add_argument(
            'target',
            type=str,
            help='The target of the package. By default a path to a directory. '
                 'See -f/--force to allow changing none-empty directories. '
                 'See -g/--gf-git to use it as a git repository. '
                 'A notable exception is -u/--upstream-yaml where the upstream.yaml '
                 'template will be saved to target file name.')
parser.add_argument(
            '-g','--gf-git',
            dest='is_gf_git',
            action='store_true',
            help='Try to use target as a git repository clone of GitHub google/fonts and '
                 'create or override a branch from upstream master using a generated '
                 'default branch name or a branch name specified with -b/--branch')
parser.add_argument(
            '-b', '--branch',
            type=str,
            default=None,
            help='Set the local target branch name instead '
                 'of using the generated branch name, like: "gftools_packager_{familyname}". '
                 'This implies -g/--gf-git, i.e. target will be treated as if -g/--gf-git is set.')
parser.add_argument(
            '-a', '--add-commit',
            action='store_true',
            help='Don\'t override existing branch and instead add a new '
                 'commit to the branch. Use this to create a PR for multiple '
                 'familes e.g. a super family or a bunch update. '
                 'It\'s likely that you want to combine this with -b/--branch. '
                 'This implies -g/--gf-git, i.e. target will be treated as if -g/--gf-git is set.')
parser.add_argument(
            '-p', '--pr',
            action='store_true',
            help='Make a pull request. '
                 'This implies -g/--gf-git, i.e. target will be treated as if -g/--gf-git is set. '
                 'See --pr-upstream  and --push-upstream.')
parser.add_argument(
            '--pr-upstream',
            type=str,
            default='',
            help='The upstream where the pull request goes, as a GitHub '
                 '"owner/repoName" pair (default: google/fonts). '
                 'This implies -p/--pr, i.e. target will be treated as if -p/--pr is set.'
                 )
parser.add_argument(
            '--push-upstream',
            type=str,
            default='',
            # we can push to a clone of google/fonts and then pr from
            # that clone to --pr-upstream, however, our ghactions QA can't
            # run on a different repo, that's why this is mostly for testing.
            help='The upstream where the push goes, as a GitHub "owner/repoName" '
                 'pair (default: the value of --pr-upstream). '
                 'This implies -p/--pr, i.e. target will be treated as if -p/--pr is set.')
parser.add_argument(
            '-u', '--upstream-yaml',
            action='store_true',
            help='Create and output the upstream.yaml to the file name given by target. '
                 'This is intended to help bootstrapping new upstream configurations. '
                 'In it\'s simplest form, if no name argument is given, it will output the '
                 'yaml template. '
                 'However, if name is given, this will also try to include all available '
                 'information and interact with the user. This can only handle one name, '
                 'because there can only be one target. '
                 'Use -y/--no-confirm to skip interactive mode.'
                 'Use -f/--force to override existing target.')
parser.add_argument(
            '--no-whitelist',
            action='store_true',
            help='Don\'t use the whitelist of allowed files to copy from '
                 'TARGET in upstream_conf.files. This is meant to enable '
                 'forward compatibility with new files and should not '
                 'be used regularly. Instead file an issue to add new '
                 'files to the whitelist.')
parser.add_argument(
            '--no-source',
            action='store_true',
            help='Don\'t add the "source" key to METADATA.pb. Use this temporarily '
            'until all back-end systems have been updated. '
            'See https://github.com/google/fonts/issues/2587'
            )


if __name__ == '__main__':
    args = parser.parse_args()
    try:
      packager.make_package(**args.__dict__)
    except UserAbortError as e:
      print('Aborted',
            'by user!' if not args.yes else \
            'by program! User interaction required (don\'t use the -y/--no-confirm flag).',
            f'{e}')
      sys.exit(1)
    except ProgramAbortError as e:
      print(f'Aborted by program: {e}')
      sys.exit(1)
    print('Done!')
