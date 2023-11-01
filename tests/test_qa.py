import pytest
import tempfile
import os
import subprocess
from glob import glob
from pathlib import Path


TEST_DATA = os.path.join("data", "test")
TEST_FONT = os.path.join(TEST_DATA, "MavenPro[wght].ttf")


def get_fp_tree(fp):
    res = []
    for dirpath, _, filenames in os.walk(fp):
        for f in filenames:
            new_fp = os.path.join(dirpath, f)
            new_fp = Path(os.path.relpath(new_fp, start=fp))
            res.append(new_fp)
    return res

@pytest.mark.parametrize(
    "cmd,expected_filepaths",
    [
        (
            ["gftools", "qa", "-f", TEST_FONT, "-fb", TEST_FONT, "-a"],
            [
                Path('Diffbrowsers/Black-Bold-Medium-Regular/new-MavenPro[wght].ttf'),
                Path('Diffbrowsers/Black-Bold-Medium-Regular/diffbrowsers_proofer.html'),
                Path('Diffbrowsers/Black-Bold-Medium-Regular/diffbrowsers_glyphs.html'),
                Path('Diffbrowsers/Black-Bold-Medium-Regular/old-MavenPro[wght].ttf'),
                Path('Diffbrowsers/Black-Bold-Medium-Regular/diffbrowsers_text.html'),
                Path('Diffbrowsers/Black-Bold-Medium-Regular/diffbrowsers_waterfall.html'),
                Path('fonts_before/MavenPro[wght].ttf'),
                Path('Fontbakery/report.md'),
                Path('fonts/MavenPro[wght].ttf'),
                Path('Diffenator/Black-Bold-Medium-Regular/Medium/diffenator.html'),
                Path('Diffenator/Black-Bold-Medium-Regular/Medium/new-MavenPro[wght].ttf'),
                Path('Diffenator/Black-Bold-Medium-Regular/Medium/old-MavenPro[wght].ttf'),
                Path('Diffenator/Black-Bold-Medium-Regular/Bold/diffenator.html'),
                Path('Diffenator/Black-Bold-Medium-Regular/Bold/new-MavenPro[wght].ttf'),
                Path('Diffenator/Black-Bold-Medium-Regular/Bold/old-MavenPro[wght].ttf'),
                Path('Diffenator/Black-Bold-Medium-Regular/Regular/diffenator.html'),
                Path('Diffenator/Black-Bold-Medium-Regular/Regular/new-MavenPro[wght].ttf'),
                Path('Diffenator/Black-Bold-Medium-Regular/Regular/old-MavenPro[wght].ttf'),
                Path('Diffenator/Black-Bold-Medium-Regular/Black/diffenator.html'),
                Path('Diffenator/Black-Bold-Medium-Regular/Black/new-MavenPro[wght].ttf'),
                Path('Diffenator/Black-Bold-Medium-Regular/Black/old-MavenPro[wght].ttf'),
            ]
        ),
        (
            ["gftools", "qa", "-f", TEST_FONT, "--proof"],
            [
                Path('Proof/Regular-Medium-Bold-Black/MavenPro[wght].ttf'),
                Path('Proof/Regular-Medium-Bold-Black/diffbrowsers_proofer.html'),
                Path('Proof/Regular-Medium-Bold-Black/diffbrowsers_glyphs.html'),
                Path('Proof/Regular-Medium-Bold-Black/diffbrowsers_text.html'),
                Path('Proof/Regular-Medium-Bold-Black/diffbrowsers_waterfall.html'),
                Path('fonts/MavenPro[wght].ttf')
            ]
        )
    ]
)
def test_qa(cmd, expected_filepaths):
    with tempfile.TemporaryDirectory() as tmp_dir:
        cmd += ["-o", tmp_dir]
        subprocess.run(cmd)
        got_filepaths = get_fp_tree(tmp_dir)
        assert sorted(got_filepaths) == sorted(expected_filepaths)