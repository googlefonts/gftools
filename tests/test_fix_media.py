import pytest
import os
from gftools.scripts.fix_media import fix_media, MAX_WIDTH, MAX_HEIGHT, MAXSIZE_RASTER
from PIL import Image
import tempfile
from pathlib import Path


TEST_DATA = os.path.join("data", "test", "article")


def test_fix_media():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir = Path(tmp_dir)
        fix_media(
            TEST_DATA,
            out=tmp_dir,
        )
        # width should be 1024
        img = Image.open(os.path.join(tmp_dir, "img1.jpg"))
        img_width, img_height = img.size
        assert img_width <= MAX_WIDTH
        assert img_height <= MAX_HEIGHT

        # Filesize should be less than 800kb
        img_size = os.stat(tmp_dir / "img1.jpg").st_size
        assert img_size <= MAXSIZE_RASTER

        # Check gif is converted to mp4
        assert (tmp_dir / "vid1.mp4").exists()
        assert not (tmp_dir / "vid1.gif").exists()
