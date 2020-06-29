#!/usr/bin/env python3
import sys
from gftools import packager
from gftools.packager import UserAbortError, ProgramAbortError


import argparse

parser = argparse.ArgumentParser(description='Package upstream font families for Google Fonts.')

parser.add_argument(
            'file_or_family',
            metavar='name',
            type=str,
            help='The family name or a file name of an upstream.yaml file. '
                 'If the name ends with the ".yaml" suffix, it\'s treated '
                 'as a file otherwise it\'s used as family name and packager '
                 'tries to gather upstream configuration from the google/fonts '
                 'GitHub repository. If the name is "-", a hyphen, no package '
                 'will be created, this is useful to only make a PR, see '
                 '-p/--pr, from an already created branch.')
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
                  'See -g/--gf-git to use it as a git repository.')
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
            help='When -g/--gf-git is used, set the local target branch name instead '
                 'of using the generated branch name, like: "gftools-packager-{family-name}".')
parser.add_argument(
            '-c', '--add-commit',
            action='store_true',
            help='When -g/--gf-git is used, don\'t override existing branch '
            'and instead add a new commit to the branch. Use this to create '
            'a PR for multiple familes e.g. a super family or a bunch update.')
parser.add_argument(
            '-p', '--pr',
            action='store_true',
            help='Make a pull request, when -g/--gf-git. See --pr-upstream '
            'and --push-upstream.')
parser.add_argument(
            '--pr-upstream',
            type=str,
            default='google/fonts',
            help='The upstream where the pull request goes, as a GitHub '
                 '"owner/repoName" pair. (default: %(default)s)')
parser.add_argument(
            '--push-upstream',
            type=str,
            default='',
            # we can push to a clone of google/fonts and then pr from
            # that clone to --pr-upstream, however, our ghactions QA can't
            # run on a different repo, that's why this is mostly for testing.
            help='The upstream where the push goes, as a GitHub "owner/repoName" '
                 'pair. (default: the value of --pr-upstream)')
parser.add_argument(
            '--no-whitelist',
            action='store_true',
            help='Don\'t use the whitelist of allowed files to copy from '
                 'TARGET in upstream_conf.files. This is meant to enable '
                 'forward compatibility with new files and should not '
                 'be used regularly. Instead file an issue to add new '
                 'files to the whitelist.')

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
