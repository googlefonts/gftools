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


class TestSubcommands(unittest.TestCase):
    """Functional tests to determine that bin/gftools runs correctly"""
    def setUp(self):
        self.bin_path = os.path.join('bin')
        self.maxDiff = None

    def test_list_subcommands_has_all_scripts(self):
        """Tests if the output from running gftools --list-subcommands
        matches the scripts within the bin folder"""

        scripts = [re.sub('\.\w*$', '', f.replace('gftools-', '')) for f in \
                   os.listdir(self.bin_path) if f.startswith('gftools-')]
        subcommands = subprocess.check_output(['python',
                                               os.path.join('bin', 'gftools'),
                                               '--list-subcommands'], encoding="utf-8").split()
        self.assertEqual(sorted(scripts), sorted(subcommands))


class TestGFToolsScripts(unittest.TestCase):
    """Functional tests to determine whether each script can execute successfully"""
    def setUp(self):
        self.get_path = lambda name: os.path.join('bin', 'gftools-' + name + '.py')
        self.example_dir = os.path.join('data', 'test', 'cabin')
        self.example_font = os.path.join(self.example_dir, 'Cabin-Regular.ttf')
        self.example_family = glob(os.path.join("data", "test", "mavenpro", "*.ttf"))
        self.example_vf_font = os.path.join("data", "test", 'Lora-Roman-VF.ttf')
        self.example_vf_stat = os.path.join("data", "test", 'lora_stat.yaml')
        self.example_builder_config = os.path.join("data", "test", 'builder_test.yaml')
        self.src_vtt_font = os.path.join("data", "test", "Inconsolata[wdth,wght].ttf")
        self.gf_family_dir = os.path.join('data', 'test', 'mock_googlefonts', 'ofl', 'abel')
        self.nam_file = os.path.join('data', 'test', 'arabic_unique-glyphs.nam')
        self.blacklisted_scripts = [
          ['python', self.get_path('build-contributors')],  # requires source folder of git commits
          ['python', self.get_path('check-category')],  # Requires GF key
          ['python', self.get_path('check-gf-github')],  # Requires github credentials
          ['python', self.get_path('build-font2ttf')],  # Requires fontforge
          ['python', self.get_path('generate-glyphdata')],  # Generates desired_glyph_data.json
          ['python', self.get_path('metadata-vs-api')],  # Requires an API key
          ['python', self.get_path('update-version')],  # Needs to know the current font version and the next version to set
          ['python', self.get_path('family-html-snippet')], # Requires GF api token
          ['python', self.get_path('qa')], # Has seperate checks
          ['python', self.get_path('sanity-check')], # Very old doesn't follow new spec. Should be deprecated.
        ]
        self.dir_before_tests = os.listdir(self.example_dir)

    def tearDown(self):
        """Clears the example folder of any files created during the unit tests"""
        files_to_delete = set(os.listdir(self.example_dir)) - set(self.dir_before_tests)
        for f in files_to_delete:
            os.remove(os.path.join(self.example_dir, f))

    def check_script(self, command):
        """Template for unit testing the python scripts"""
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8")
        stdout, stderr = process.communicate()
        self.assertNotIn('Err', stderr, ' '.join(command) + ':\n\n' + stderr)

    def test_build_ofl(self):
        self.check_script(['python', self.get_path('add-font'), self.gf_family_dir])

    def test_build_ofl(self):
        self.check_script(['python', self.get_path('build-ofl'), self.example_dir])

    def test_check_bbox(self):
        self.check_script(['python', self.get_path('check-bbox'), self.example_font, '--glyphs', '--extremes'])

    def test_check_copyright_notices(self):
        self.check_script(['python', self.get_path('check-copyright-notices')])

    def test_check_font_version(self):
        self.check_script(['python', self.get_path('check-font-version'), self.example_font])

    def test_check_name(self):
        self.check_script(['python', self.get_path('check-name'), self.example_font])

    def test_check_vtt_compatibility(self):
        self.check_script(['python', self.get_path('check-vtt-compatibility'), self.example_font, self.example_font])

    def test_compare_font(self):
        self.check_script(['python', self.get_path('compare-font'), self.example_font, self.example_font])

    def test_dump_names(self):
        self.check_script(['python', self.get_path('dump-names'), self.example_font])

    def test_find_features(self):
        self.check_script(['python', self.get_path('find-features'), self.example_font])

    def test_fix_ascii_fontmetadata(self):
        self.check_script(['python', self.get_path('fix-ascii-fontmetadata'), self.example_font])

    def test_fix_cmap(self):
        self.check_script(['python', self.get_path('fix-cmap'), self.example_font])

    def test_fix_dsig(self):
        self.check_script(['python', self.get_path('fix-dsig'), self.example_font])

    def test_fix_familymetadata(self):
        self.check_script(['python', self.get_path('fix-familymetadata'), self.example_font])

    def test_fix_fsselection(self):
        self.check_script(['python', self.get_path('fix-fsselection'), self.example_font])

    def test_fix_fstype(self):
        self.check_script(['python', self.get_path('fix-fstype'), self.example_font])

    def test_fix_gasp(self):
        self.check_script(['python', self.get_path('fix-gasp'), self.example_font])

    def test_fix_glyph_private_encoding(self):
        self.check_script(['python', self.get_path('fix-glyph-private-encoding'), self.example_font])

    def test_fix_glyphs(self):
        self.check_script(['python', self.get_path('fix-glyphs')])

    def test_fix_hinting(self):
        self.check_script(['python', self.get_path('fix-hinting'), self.example_font])

    def test_fix_isfixedpitch(self):
        self.check_script(['python', self.get_path('fix-isfixedpitch'), "--fonts", self.example_font])

    def test_fix_nameids(self):
        self.check_script(['python', self.get_path('fix-nameids'), self.example_font])

    def test_fix_nonhinting(self):
        self.check_script(['python', self.get_path('fix-nonhinting'), self.example_font, self.example_font + '.fix'])

    def test_fix_ttfautohint(self):
        self.check_script(['python', self.get_path('fix-ttfautohint'), self.example_font])

    def test_fix_vendorid(self):
        self.check_script(['python', self.get_path('fix-vendorid'), self.example_font])

    def test_fix_vertical_metrics(self):
        self.check_script(['python', self.get_path('fix-vertical-metrics'), self.example_font])

    def test_font_diff(self):
        self.check_script(['python', self.get_path('font-diff'), self.example_font, self.example_font])

    def test_font_weights_coveraget(self):
        self.check_script(['python', self.get_path('font-weights-coverage'), self.example_font])

    def test_fix_font(self):
        self.check_script(['python', self.get_path('fix-font'), self.example_font])

    def test_fix_family(self):
        self.check_script(['python', self.get_path('fix-family')] + self.example_family)

    def test_list_italicangle(self):
        self.check_script(['python', self.get_path('list-italicangle'), self.example_font])

    def test_list_panose(self):
        self.check_script(['python', self.get_path('list-panose'), self.example_font])

    def test_list_variable_source(self):
        self.check_script(['python', self.get_path('list-variable-source')])

    def test_list_weightclass(self):
        self.check_script(['python', self.get_path('list-weightclass'), self.example_font])

    def test_list_widthclass(self):
        self.check_script(['python', self.get_path('list-widthclass'), self.example_font])

    def test_nametable_from_filename(self):
        self.check_script(['python', self.get_path('nametable-from-filename'), self.example_font])

    def test_namelist(self):
        self.check_script(['python', self.get_path('namelist'), self.example_font])

    def test_ots(self):
        self.check_script(['python', self.get_path('ots'), self.example_font])

    def test_rangify(self):
        self.check_script(['python', self.get_path('rangify'), self.nam_file])

    def test_test_gf_coverage(self):
        self.check_script(['python', self.get_path('test-gf-coverage'), self.example_font])

    def test_ttf2cp(self):
        self.check_script(['python', self.get_path('ttf2cp'), self.example_font])

    def test_unicode_names(self):
        self.check_script(['python', self.get_path('unicode-names'), "--nam_file", self.nam_file])

    def test_update_families(self):
        self.check_script(['python', self.get_path('update-families'), self.example_font])

    def test_update_version(self):
        self.check_script(['python', self.get_path('update-version'), self.example_font])

    def test_varfont_info(self):
        self.check_script(['python', self.get_path('varfont-info'), self.example_vf_font])

    def test_what_subsets(self):
        self.check_script(['python', self.get_path('what-subsets'), self.example_font])

    def test_rename_font(self):
        self.check_script(['python', self.get_path('rename-font'), self.example_font, "Foobar"])
# Temporarily disabling this until we close issue #13
# (https://github.com/googlefonts/tools/issues/13)
# See also https://github.com/googlefonts/fontbakery/issues/1535
#    def test_update_families(self):
#        self.check_script(['python', self.get_path('update-families'), self.example_font])

    def test_update_nameids(self):
        self.check_script(['python', self.get_path('update-nameids'), self.example_font, "-c", "Foobar"])

    def test_check_vtt_compile(self):
        self.check_script(['python', self.get_path('check-vtt-compile'), self.src_vtt_font])

    def test_gen_stat(self):
        self.check_script(
            ['python', self.get_path('gen-stat'), self.example_vf_font, "--axis-order", "wght"]
        )

    def test_gen_stat2(self):
        self.check_script(
            ['python', self.get_path('gen-stat'), self.example_vf_font, "--src", self.example_vf_stat]
        )

    def test_builder(self):
        self.check_script(['python', self.get_path('builder'), self.example_builder_config])


if __name__ == '__main__':
    unittest.main()
