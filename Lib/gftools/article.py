"""
Fix images and gifs in google/fonts article directories.
"""

from PIL import Image
import os
import argparse
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString
import tempfile
import shutil
import ffmpeg
import logging

log = logging.getLogger("gftools.article")
LOG_FORMAT = "%(message)s"


# Taken from fontbakery.
# I have no clue why vector images can be larger than raster images.
# https://github.com/fonttools/fontbakery/blob/main/Lib/fontbakery/checks/vendorspecific/googlefonts/article/images.py#L27
MAX_WIDTH = 2048
MAX_HEIGHT = 1024
MAXSIZE_VECTOR = 1750 * 1024  # 1750kb
MAXSIZE_RASTER = 800 * 1024  # 800kb


def fix_image_dimensions(fp: Path, img: Image.Image):
    img_ratio = img.width / img.height
    if img.width > MAX_WIDTH:
        log.info(
            f"Resizing image from {img.width}x{img.height} to {MAX_WIDTH}x{int(MAX_WIDTH / img_ratio)}"
        )
        img = img.resize((MAX_WIDTH, int(MAX_WIDTH / img_ratio)), Image.LANCZOS)
        if fp.suffix == ".png":
            img.save(fp, optimize=True, compress_level=9)
        else:
            img.save(fp)
    if img.height > MAX_HEIGHT:
        log.info(
            f"Resizing image from {img.width}x{img.height} to {int(MAX_HEIGHT * img_ratio)}x{MAX_HEIGHT}"
        )
        img = img.resize((int(MAX_HEIGHT * img_ratio), MAX_HEIGHT), Image.LANCZOS)
        if fp.suffix == ".png":
            img.save(fp, optimize=True, compress_level=9)
        else:
            img.save(fp)
    return img


def fix_image_filesize(fp: Path, img: Image.Image):
    img_size = os.stat(fp).st_size
    if img_size <= MAXSIZE_RASTER:
        return fp
    # If an image is already a jpg, we don't want to compress it further
    # since it'll create compression artifacts.
    if img_size > MAXSIZE_RASTER and fp.suffix in [".jpg", ".jpeg"]:
        raise ValueError(
            f"Image '{fp}' is too large for a jpg: {img_size} > {MAXSIZE_RASTER}."
        )
    log.info("Converting '{fp}' to jpg")
    img = img.convert("RGB")
    new_fp = fp.with_suffix(".jpg")
    img.save(new_fp, "JPEG", quality=85)
    new_img_size = os.stat(new_fp).st_size
    if new_img_size > MAXSIZE_RASTER:
        raise ValueError(
            "Failed to convert image '{fp}' to jpg to fix filesize issue: {new_img_size} > {MAXSIZE_RASTER}."
        )
    return Path(new_fp)


def image_to_mp4(fp: Path):
    if fp.suffix != ".gif":
        return
    try:
        stream = ffmpeg.input(fp)
        out = fp.with_suffix(".mp4")
        stream = ffmpeg.output(stream, str(out))
        ffmpeg.run(stream)
    except FileNotFoundError:
        raise FileNotFoundError("ffmpeg not found. Please install ffmpeg.")
    return out


def update_hrefs(article: BeautifulSoup, media_map: list):
    for tag in article.find_all("img"):
        if tag["src"] in media_map:
            if tag["src"] == media_map[tag["src"]]:
                continue
            if tag["src"].endswith(".gif"):
                tag.name = "video"
                # We want the following tag:
                # <video loop autoplay muted src="file.mp4" type="video/mp4">
                #  Your browser does not support the video tag.
                # </video>
                # to get this we add a key for each attribute we want to include
                # and set the value to None. An empty string or false doesn't work.
                tag["loop"] = None
                tag["autoplay"] = None
                tag["muted"] = None
                tag["type"] = "video/mp4"
                tag.insert(
                    0, NavigableString("Your browser does not support the video tag.")
                )
            tag["src"] = media_map[tag["src"]]
    return article


def found_media(fp: Path, article: BeautifulSoup):
    res = []
    for tag in article.find_all("img"):
        res.append(fp / tag["src"])
    for tag in article.find_all("video"):
        res.append(fp / tag["src"])
    return res


def remove_unused_media(fp: Path, article: BeautifulSoup):
    found = found_media(fp, article)
    for media_fp in fp.glob("*"):
        if media_fp.suffix == ".html":
            continue
        if media_fp not in found:
            os.remove(media_fp)


def fix_article(
    fp: Path, out: Path = None, inplace: bool = False, dry_run: bool = False
):
    """Fix article media."""
    if out:
        if out.exists():
            shutil.rmtree(out)
        os.makedirs(out)

    # Work on a copy of every file so we can do a dry run if needed.
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir = Path(tmp_dir)
        shutil.copytree(fp, tmp_dir, dirs_exist_ok=True)

        article_fp = tmp_dir / "ARTICLE.en_us.html"
        if not article_fp.exists():
            raise FileNotFoundError(f"Article file not found: {article_fp}")
        with open(article_fp, encoding="utf-8") as doc:
            article = BeautifulSoup(doc, "html.parser")
            media = found_media(article_fp.parent, article)
            rename_map = {}
            for media_fp in media:
                if media_fp.suffix == ".mp4":
                    log.debug(f'skipping "{media_fp.name}", already mp4')
                    continue
                if media_fp.suffix in [".gif", ".apng"]:
                    new_fp = image_to_mp4(media_fp)
                    rename_map[media_fp.name] = new_fp.name
                # TODO fix/warn about vector images
                else:
                    img = Image.open(media_fp)
                    img = fix_image_dimensions(media_fp, img)
                    new_fp = fix_image_filesize(media_fp, img)
                    if os.stat(media_fp).st_size == os.stat(new_fp).st_size:
                        log.debug(f'skipping "{media_fp.name}", already optimized')
                        continue
                    rename_map[media_fp.name] = new_fp.name
            article = update_hrefs(article, rename_map)
            remove_unused_media(article_fp.parent, article)
        with open(article_fp, "w", encoding="utf-8") as doc:
            doc.write(str(article))
        if out:
            shutil.copytree(tmp_dir, out, dirs_exist_ok=True)
        elif inplace:
            shutil.rmtree(fp)
            shutil.copytree(tmp_dir, fp, dirs_exist_ok=True)
        elif dry_run:
            log.info("Dry run complete. No files were written.")
        else:
            raise ValueError("No output directory, inplace or dry_run flag set.")
