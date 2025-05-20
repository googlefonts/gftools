import pytest
import os
from gftools.scripts.fix_media import fix_media, MAX_WIDTH, MAX_HEIGHT, MAXSIZE_RASTER
from PIL import Image
import tempfile
from pathlib import Path


TEST_DATA = Path(os.path.join("data", "test", "article"))


def test_fix_media():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir = Path(tmp_dir)
        fix_media(
            TEST_DATA,
            out=tmp_dir,
        )
        # width should be 1024
        img_path = tmp_dir / "img1.jpg"
        img = Image.open(img_path)
        img_width, img_height = img.size
        assert img_width <= MAX_WIDTH
        assert img_height <= MAX_HEIGHT

        # Filesize should be less than 800kb
        img_size = os.stat(img_path).st_size
        assert img_size <= MAXSIZE_RASTER

        # Check gif is converted to mp4
        vid_path = tmp_dir / "vid1.mp4"
        assert (vid_path).exists()
        # Check olf gif is deleted
        old_gif = tmp_dir / "vid1.gif"
        assert not (old_gif).exists()
        img.close()
