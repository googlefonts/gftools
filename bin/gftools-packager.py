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
                  'Use --file to mark it as a file otherwise it\'s used as family name.')
parser.add_argument(
            '--file',
            dest='is_file',
            action='store_true',
            help='Load upstream.yaml from a file, use the [name] argument as path.')
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
# for documenting of non interactive tasks
# FIXME: maybe make this the default and quiet the choice?
parser.add_argument(
            '-q',
            '--quiet',
            action='store_true',
            help='Don\'t print user interaction dialogues when --no-confirm is used.')
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
    print('args:', args)
    # packager.dir_walk_breath_first(sys.argv[1], ['fonts/ttf', 'fonts/variable', 'sources'])
    # packager.get_gh_gf_family_entry(sys.argv[1])
    # packager.git_directory_listing(sys.argv[1])

    # prefixes = ['fonts/ttf', 'fonts/variable', 'sources', 'ofl/josefinsans/static']
    # topdown = True
    # if sys.argv[1] == 'git':
    #     packager.git_directory_listing(sys.argv[2], prefixes=prefixes, topdown=topdown)
    # elif sys.argv[1] == 'fs':
    #     packager.fs_directory_listing(sys.argv[2], prefixes=prefixes, excludes=['.git'], topdown=topdown)
    # packager.is_google_fonts(sys.argv[1])

    # args: Namespace(file=True, file_or_family='xwhyzet.upstream.yaml', verbose=False, yes=False)
    try:
      packager.make_package(**args.__dict__)
    except UserAbortError:

      print('Aborted',
            'by user!' if not args.yes else \
            'by program! User interaction required (don\'t use the --yes flag).')
      sys.exit(1)
    except ProgramAbortError as e:
      print(f'Aborted by program: {e}')
      sys.exit(1)
    print('Done!')
