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
            help='The family name or a file name of an upstream.yaml file')
parser.add_argument(
            '--file',
            dest='is_file',
            action='store_true',
            help='load upstream.yaml from a file, use the [name] argument as path')
parser.add_argument(
            '-y',
            '--yes',
            action='store_true',
            help='Answer all user interaction with yes (removes all interactivity).')

# for documenting of non interactive tasks
# FIXME: maybe make this the default and quiet the choice?
parser.add_argument(
            '-q',
            '--quiet',
            action='store_true',
            help='Don\'t print user interaction dialogues when --yes is used.')

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
