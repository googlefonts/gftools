#!/usr/bin/env python3
"""Add or update a designer entry in the Google Fonts catalog.

Designer profiles are stored in the google/fonts repo:
https://github.com/google/fonts/tree/main/catalog/designers

This script is intended to help onboarders quickly create individual designer
profiles.

Designer Profiles are visible to the public. They are included in the the about
section for each family e.g:
https://fonts.google.com/specimen/Roboto#about

In 2021, Rosalie Wagner created an online form for us to collect designer
information from the general public. The form populates a private spreadsheet.

There is also an image directory where the designer's profile pics are uploaded into.

In order to use the spreadsheet command in this script, you will need to
download the folder which contains the spreadsheet and designer images.
You can then use the ``--spreadsheet`` arg.

Usage:
# Add or update a designer entry. User will need to hand complete the bio.html.
$ gftools add-designer path/to/local/clone/fonts/catalog/designers "Theo Salvadore" --img_path path/to/img.png

# Add or update a designer entry using the spreadsheet.
$ gftools add-designer path/to/local/clone/fonts/catalog/designers "Theo Salvador" --img_path path/to/img.png --spreadsheet ./GFDesigners.xlsx
"""
import argparse
from glob import glob
import os
from unidecode import unidecode
from PIL import Image
from gftools.designers_pb2 import DesignerInfoProto
from google.protobuf import text_format
from gftools.utils import remove_url_prefix


def process_image(fp):
    if not os.path.isfile(fp):
        raise ValueError(f"{fp} is not a file")
    img = Image.open(fp)
    width, height = img.size
    if width != height:
        print("warning: img is rectangular when it should be square")
    if width < 300 or height < 300:
        print("warning: img is smaller than 300x300px")
        return img

    print("resizing image")
    img.thumbnail((300, 300))
    return img


def gen_info(designer, img_path=None, link=""):
    # Write info.pb
    info = DesignerInfoProto()
    info.designer = designer
    info.link = ""
    if img_path:
        info.avatar.file_name = img_path

    text_proto = text_format.MessageToString(info, as_utf8=True, use_index_order=True)
    return text_proto


def parse_urls(string):
    urls = string.split()
    res = []
    for url in urls:
        if not url.startswith("http"):
            url = "https://" + url
        res.append(url)
    return res


def gen_hrefs(urls):
    res = {}
    for url in urls:
        if "twitter" in url:
            res[url] = "Twitter"
        elif "facebook" in url:
            res[url] = "Facebook"
        elif "instagram" in url:
            res[url] = "Instagram"
        elif "github" in url:
            res[url] = "Github"
        else:
            # https://www.mysite.com --> mysite.com
            res[url] = remove_url_prefix(url)
    return " | ".join(f'<a href="{k}">{v}</a>' for k, v in res.items())


def make_designer(
    designer_directory,
    name,
    img_path=None,
    bio=None,
    urls=None,
):
    designer_dir_name = unidecode(name.lower().replace(" ", "").replace("-", ""))
    designer_dir = os.path.join(designer_directory, designer_dir_name)
    if not os.path.isdir(designer_dir):
        print(f"{name} isn't in catalog. Creating new dir {designer_dir}")
        os.mkdir(designer_dir)

    existing_imgs = glob(os.path.join(designer_dir, "*[.png|.jpg|.jpeg]"))
    if not img_path and existing_imgs:
        img_path = existing_imgs[0]
    img_dst = os.path.join(designer_dir, f"{designer_dir_name}.png")

    if img_path and img_path in existing_imgs:
        print("Skipping image processing")
    elif img_path:
        print(f"processing image {img_path}")
        # remove any existing images
        if existing_imgs:
            [os.remove(i) for i in existing_imgs]
        image = process_image(img_path)
        image.save(img_dst)

    print(f"Generating info.pb file")
    info_pb = gen_info(
        name, os.path.basename(img_dst) if os.path.isfile(img_dst) else None
    )
    filename = os.path.join(designer_dir, "info.pb")
    with open(filename, "w") as f:
        f.write(info_pb)

    # write/update bio.html
    bio_file = os.path.join(designer_dir, "bio.html")
    html_text = None
    if bio:
        print("Generating bio.html")
        html_text = f"<p>{bio}</p>"
        if urls:
            hrefs = gen_hrefs(urls)
            html_text += "\n" + f"<p>{hrefs}</p>"
    elif os.path.isfile(bio_file):
        print("Skipping. No bio text supplied but bio.html already exists")
    else:
        print(f"Please manually update the bio.html file")
        html_text = "N/A"
    if html_text:
        with open(bio_file, "w") as f:
            f.write(html_text)
    print(f"Finished profile {designer_dir}")


def main(args=None):
    parser = argparse.ArgumentParser(usage=__doc__)
    parser.add_argument("designers_directory", help="path to google/fonts designer dir")
    parser.add_argument("name", help="Designer name e.g 'Steve Matteson'")
    parser.add_argument(
        "--img_path", help="Optional path to profile image", default=None
    )
    parser.add_argument(
        "--spreadsheet", help="Optional path to the Google Drive spreadsheet"
    )
    args = parser.parse_args(args)

    if args.spreadsheet:
        try:
            import pandas as pd
        except ImportError as e:
            raise ValueError(
                "The pandas library is required to read Excel spreadsheets"
            )

        df = pd.read_excel(args.spreadsheet)
        entry = df.loc[df["Designer Name"] == args.name]
        if len(entry) == 0:
            raise ValueError(f"Spreadsheet doesn't contain name '{args.name}'")
        bio = entry["Bio"].item()
        urls = entry["Link"].item()
        if isinstance(urls, float):  # pandas DF sets empty cells to a float
            urls = None
        else:
            urls = parse_urls(urls)

        if isinstance(bio, float):
            bio = None
    else:
        bio = None
        urls = None

    make_designer(args.designers_directory, args.name, args.img_path, bio, urls)


if __name__ == "__main__":
    main()
