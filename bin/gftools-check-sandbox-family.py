#!/usr/bin/env python3
"""
Make a diff/gif image of a site by swapping the GF production families
with the same families hosted on the sandbox server.


Usage:
gftools check-sandbox-family https://www.somesite.com
"""
import os
import sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options 
from PIL import Image, ImageDraw, ImageFont
import argparse
from urllib.parse import urlsplit
from io import BytesIO
import time


SWAP_FONT_JS = """
links = document.getElementsByTagName('link');
for (i in links) {
    if (typeof(links[i].href) != 'undefined') {
         if (links[i].href.indexOf("fonts.googleapis.com") > -1)             
             links[i].href = links[i].href.replace("fonts.googleapis", "fonts.sandbox.google");
    }
}
"""
WIDTH = 1024


def get_font_for_os():
    if sys.platform.startswith("linux"):
        return os.path.join(
                "usr", "share", "font", "truetype", "noto"
                "NotoMono-Regular.ttf")
    elif sys.platform.startswith("darwin"):
        return os.path.join("Library", "Fonts", "Arial.ttf")
    elif sys.platform.startswith("win"):
        return os.path.join("c:", "\\", "Windows", "Fonts", "arial.ttf")
    else:
        raise NotImplementedError("Please use OSX, Ubuntu or Win")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("-o", "--out",
                        help="Gif out path e.g ~/Desktop/site1.gif")
    parser.add_argument("-l", "--limit", type=int,
                        help="limit diff height")
    args = parser.parse_args()

    chrome_options = Options()
    chrome_options.add_argument("--headless")

    with webdriver.Chrome(options=chrome_options) as driver:
        driver.get(args.url)
        required_height = driver.execute_script('return document.body.parentNode.scrollHeight')
        if args.limit and required_height > args.limit:
            required_height = args.limit
        driver.set_window_size(WIDTH, required_height)

        try:
            families_in_use = driver.find_elements_by_xpath(
                    '//link[contains(@href, "fonts.googleapis.com/css")]'
            )
            for family in families_in_use:
                print("Changing GF url %s to %s" % (
                    family.get_attribute("href"), family.get_attribute("href").replace(
                        "fonts.googleapis.com", "fonts.sandbox.google.com")
                ))
        except:
            raise Exception("No hosted GF families found on %s" % args.url)

        time.sleep(2)
        before_img = driver.get_screenshot_as_png()
        driver.execute_script(SWAP_FONT_JS)
        time.sleep(2)
        after_img = driver.get_screenshot_as_png()

        if args.out:
            gif_path = args.out
        else:
            gif_path = urlsplit(args.url).netloc + ".gif"

        with Image.open(BytesIO(before_img)) as before, Image.open(BytesIO(after_img)) as after:
            font_path = get_font_for_os()
            font = ImageFont.truetype(font_path, 32)
            before_draw = ImageDraw.Draw(before)
            before_draw.rectangle((0, 0, WIDTH, 50), fill=(0, 0, 0))
            before_draw.text((10, 10), "Production",
                             (255, 0, 0), font=font)
            after_draw = ImageDraw.Draw(after)
            after_draw.rectangle((0, 0, WIDTH, 50), fill=(0, 0, 0))
            after_draw.text((10, 10), "Sandbox",
                            (255, 0, 0), font=font)
            before.save(
                    gif_path,
                    save_all=True,
                    append_images=[after],
                    loop=10000,
                    duration=1000,
            )


if __name__ == "__main__":
    main()

