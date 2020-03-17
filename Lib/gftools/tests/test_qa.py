import subprocess
import unittest
import tempfile
import os


class TestQA(unittest.TestCase):
    def _test_diff_pr_vs_googlefonts(self):
        with tempfile.TemporaryDirectory() as qa_out:
            subprocess.call(
                [
                    "gftools",
                    "qa",
                    "-pr",
                    "https://github.com/google/fonts/pull/2067",
                    "-gfb",
                    "--fontbakery",
                    "-o",
                    qa_out,
                ]
            )
            self.assertTrue("Fontbakery" in os.listdir(qa_out))

    def _test_diff_github_fonts_vs_googlefonts(self):
        with tempfile.TemporaryDirectory() as qa_out:
            subprocess.call(
                [
                    "gftools",
                    "qa",
                    "-gh",
                    "https://github.com/googlefonts/AmaticSC/tree/master/fonts/ttf",
                    "-gfb",
                    "--fontbakery",
                    "-o",
                    qa_out,
                ]
            )
            self.assertTrue("Fontbakery" in os.listdir(qa_out))

    def test_diff_github_fonts_vs_googlefonts_vf(self):
        with tempfile.TemporaryDirectory() as qa_out:
            subprocess.call(
                [
                    "gftools",
                    "qa",
                    "-gh",
                    "https://github.com/google/fonts/tree/master/ofl/mavenpro",
                    "-gfb",
                    "--fontbakery",
                    "--diffenator",
                    "--browser-previews",
                    "--diffbrowsers",
                    "--plot-glyphs",
                    "-o",
                    qa_out,
                ]
            )
            for dir_ in ["Fontbakery", "Diffenator", "Diffbrowsers",
                         "plot_glyphs", "browser_previews"]:
                self.assertTrue(dir_ in os.listdir(qa_out))

if __name__ == "__main__":
    unittest.main()
