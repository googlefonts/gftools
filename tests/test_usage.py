#!/usr/bin/env python3
# Copyright 2016 The Fontbakery Authors
# Copyright 2017 The Google Font Tools Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Unittests to check the functionality of Google Fonts Tools"""
import os
import re
from glob import glob
import unittest
import subprocess
from gftools.scripts import _get_subcommands

CWD = os.path.dirname(__file__)
TEST_DIR = os.path.join(CWD, "..", "data", "test")


class TestGFToolsScripts(unittest.TestCase):
    """Functional tests to determine whether each script can execute successfully"""

    def setUp(self):
        self.example_dir = os.path.join(TEST_DIR, "cabin")
        self.example_font = os.path.join(self.example_dir, "Cabin-Regular.ttf")
        self.example_family = glob(os.path.join(TEST_DIR, "mavenpro", "*.ttf"))
        self.example_vf_font = os.path.join(TEST_DIR, "Lora-Roman-VF.ttf")
        self.example_vf_stat = os.path.join(TEST_DIR, "lora_stat.yaml")
        self.example_glyphs_file = os.path.join(TEST_DIR, "Lora.glyphs")
        self.example_builder_config = os.path.join(TEST_DIR, "builder_test.yaml")
        self.example_builder_config_2_sources = os.path.join(
            TEST_DIR, "Libre-Bodoni", "sources", "config.yaml"
        )
        self.src_vtt_font = os.path.join(TEST_DIR, "Inconsolata[wdth,wght].ttf")
        self.gf_family_dir = os.path.join(
            "data", "test", "mock_googlefonts", "ofl", "abel"
        )
        self.nam_file = os.path.join("data", "test", "arabic_unique-glyphs.nam")
        self.dir_before_tests = os.listdir(self.example_dir)

    def tearDown(self):
        """Clears the example folder of any files created during the unit tests"""
        files_to_delete = set(os.listdir(self.example_dir)) - set(self.dir_before_tests)
        for f in files_to_delete:
            os.remove(os.path.join(self.example_dir, f))

    def test_add_font(self):
        from gftools.scripts.add_font import main

        main([self.gf_family_dir])

    def test_build_ofl(self):
        from gftools.scripts.build_ofl import main
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmp_dir:
            main([self.example_font, tmp_dir])

    def test_check_bbox(self):
        from gftools.scripts.check_bbox import main

        main([self.example_font, "--glyphs", "--extremes"])

    def test_check_copyright_notices(self):
        from gftools.scripts.check_copyright_notices import main

        main([self.example_font])

    def test_check_font_version(self):
        from gftools.scripts.check_font_version import main

        main(["Cabin"])

    def test_check_name(self):
        from gftools.scripts.check_name import main

        main([self.example_font])

    def test_check_vtt_compatibility(self):
        from gftools.scripts.check_vtt_compatibility import main

        main([self.example_font, self.example_font])

    def test_compare_font(self):
        from gftools.scripts.compare_font import main

        main([self.example_font, self.example_font])

    def test_find_features(self):
        from gftools.scripts.find_features import main

        main([self.example_font])

    def test_fix_ascii_fontmetadata(self):
        from gftools.scripts.fix_ascii_fontmetadata import main

        main([self.example_font])

    def test_fix_cmap(self):
        from gftools.scripts.fix_cmap import main

        main([self.example_font])

    def test_fix_familymetadata(self):
        from gftools.scripts.fix_familymetadata import main

        main([self.example_font])

    def test_fix_fsselection(self):
        from gftools.scripts.fix_fsselection import main

        main([self.example_font])

    def test_fix_fstype(self):
        from gftools.scripts.fix_fstype import main

        main([self.example_font])

    def test_fix_gasp(self):
        from gftools.scripts.fix_gasp import main

        main([self.example_font])

    def test_fix_glyph_private_encoding(self):
        from gftools.scripts.fix_glyph_private_encoding import main

        main([self.example_font])

    def test_fix_glyphs(self):
        from gftools.scripts.fix_glyphs import main

        main([self.example_glyphs_file])

    def test_fix_hinting(self):
        from gftools.scripts.fix_hinting import main

        main([self.example_font])

    def test_fix_isfixedpitch(self):
        from gftools.scripts.fix_isfixedpitch import main

        main(["--fonts", self.example_font])

    def test_fix_nameids(self):
        from gftools.scripts.fix_nameids import main

        main([self.example_font])

    def test_fix_nonhinting(self):
        from gftools.scripts.fix_nonhinting import main

        main([self.example_font, self.example_font + ".fix"])

    def test_fix_ttfautohint(self):
        from gftools.scripts.fix_ttfautohint import main

        main([self.example_font])

    def test_fix_vendorid(self):
        from gftools.scripts.fix_vendorid import main

        main([self.example_font])

    def test_fix_vertical_metrics(self):
        from gftools.scripts.fix_vertical_metrics import main

        main([self.example_font])

    def test_font_diff(self):
        from gftools.scripts.font_diff import main

        main([self.example_font, self.example_font])

    def test_font_weights_coverage(self):
        from gftools.scripts.font_weights_coverage import main

        main([self.example_dir])

    def test_fix_font(self):
        from gftools.scripts.fix_font import main

        main([self.example_font])

    def test_fix_family(self):
        from gftools.scripts.fix_family import main

        main(self.example_family)

    def test_list_italicangle(self):
        from gftools.scripts.list_italicangle import main

        main([self.example_font])

    def test_list_panose(self):
        from gftools.scripts.list_panose import main

        main([self.example_font])

    # def test_list_variable_source(self):
    #     from gftools.scripts.list_variable_source import main

    def test_list_weightclass(self):
        from gftools.scripts.list_weightclass import main

        main([self.example_font])

    def test_list_widthclass(self):
        from gftools.scripts.list_widthclass import main

        main([self.example_font])

    def test_nametable_from_filename(self):
        from gftools.scripts.nametable_from_filename import main

        main([self.example_font])

    def test_ots(self):
        from gftools.scripts.ots import main

        main([self.example_dir])

    def test_rangify(self):
        from gftools.scripts.rangify import main

        main([self.nam_file])

    def test_ttf2cp(self):
        from gftools.scripts.ttf2cp import main

        main([self.example_font])

    def test_unicode_names(self):
        from gftools.scripts.unicode_names import main

        main(["--nam_file", self.nam_file])

    def test_update_families(self):
        from gftools.scripts.update_families import main

        main([self.example_font])

    def test_update_version(self):
        from gftools.scripts.update_version import main

        main(["--old_version", "2.00099", "--new_version", "2.001", self.example_font])

    def test_varfont_info(self):
        from gftools.scripts.varfont_info import main

        main([self.example_vf_font])

    def test_what_subsets(self):
        from gftools.scripts.what_subsets import main

        main([self.example_font])


#     def test_rename_font(self):
#         from gftools.scripts.rename-font'), self.example_font, "Foobar"])
# # Temporarily disabling this until we close issue #13
# # (https://github.com/googlefonts/tools/issues/13)
# # See also https://github.com/googlefonts/fontbakery/issues/1535
# #    def test_update_families(self):
# #        from gftools.scripts.update-families'), self.example_font])

#     def test_update_nameids(self):
#         from gftools.scripts.update-nameids'), self.example_font, "-c", "Foobar"])

#     def test_check_vtt_compile(self):
#         from gftools.scripts.check-vtt-compile'), self.src_vtt_font])

#     def test_gen_stat(self):
#         self.check_script(
#             ['python', self.get_path('gen-stat'), self.example_vf_font, "--axis-order", "wght"]
#         )

#     def test_gen_stat2(self):
#         self.check_script(
#             ['python', self.get_path('gen-stat'), self.example_vf_font, "--src", self.example_vf_stat]
#         )

#     def test_builder(self):
#         from gftools.scripts.builder'), self.example_builder_config])

#     def test_builder_2_sources(self):
#         self.check_script(["python", self.get_path("builder"), self.example_builder_config_2_sources])


if __name__ == "__main__":
    unittest.main()
