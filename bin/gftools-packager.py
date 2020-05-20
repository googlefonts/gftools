#!/usr/bin/env python3
import sys
from gftools import packager

if __name__ == '__main__':
    print('args:', *sys.argv[1:])
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
    packager.make_update_package(sys.argv[1])

