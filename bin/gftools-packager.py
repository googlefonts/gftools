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
    if sys.argv[1] == 'update':
        packager.make_update_package(sys.argv[2])
    elif sys.argv[1] == 'init':
        if len(sys.argv) >= 3:
            # the case when the family is already on google/fonts
            # but there's no upstream_conf
            packager.make_init_package_from_family(sys.argv[2])
        else:
            packager.make_init_package_from_scratch(sys.argv[2])
    else:
        print(f'packager command f{sys.argv[1]} not found')
        sys.exit(1)
