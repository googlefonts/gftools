#!/usr/bin/env python3
"""QA script"""
from fontTools.ttLib import TTFont
from diffenator.diff import DiffFonts
from diffenator.font import DFont
from diffbrowsers.diffbrowsers import DiffBrowsers
from diffbrowsers.browsers import test_browsers
from statistics import mode
import argparse
import shutil
import os
from glob import glob
import subprocess
import tempfile
import logging
import requests
from io import BytesIO
from zipfile import ZipFile
from gftools.utils import (
    download_family_from_Google_Fonts,
    Google_Fonts_has_family,
    load_Google_Fonts_api_key,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


DIFFENATOR_THRESHOLDS = {
    "weak": dict(
        glyphs_thresh=0.02,
        marks_thresh=20,
        mkmks_thresh=20,
        kerns_thresh=30,
        render_diffs=True,
        ),
    "normal": dict(
        glyphs_thresh=0.01,
        marks_thresh=10,
        mkmks_thresh=10,
        kerns_thresh=15,
        render_diffs=True,
    ),
    "strict": dict(
        glyphs_thresh=0.00,
        marks_thresh=0,
        mkmks_thresh=0,
        kerns_thresh=1,
        render_diffs=True,
    )
}

def instances_in_font(ttfont):
    styles = []
    if 'fvar' in ttfont.keys():
        for instance in ttfont['fvar'].instances:
            nameid = instance.subfamilyNameID
            name = ttfont['name'].getName(nameid, 3, 1, 1033).toUnicode()
            name = name.replace(' ', '')
            styles.append(name)
    else:
        styles.append(os.path.basename(ttfont.reader.file.name).split('-')[1][:-4])
    return styles


def font_instances(ttfonts):
    styles = {}
    for ttfont in ttfonts:
        ttfont_styles = instances_in_font(ttfont)
        for style in ttfont_styles:
            styles[style] = ttfont.reader.file.name
    return styles


def _instance_coords_to_filename(d):
    name = ""
    for k, v in d.items():
        name += "{}_{}_".format(k, v)
    return name[:-1]


def family_name_from_fonts(fonts):
    try:
        family_name = mode([f['name'].getName(16, 3, 1, 1033).toUnicode() for f in
                           fonts]) 
    except AttributeError:        
        family_name = mode([f['name'].getName(1, 3, 1, 1033).toUnicode() for f in
            fonts]) 
    return family_name


def mkdir(path, overwrite=True):
    if os.path.isdir(path) and overwrite:
        shutil.rmtree(path)
    if not os.path.isdir(path):
        os.mkdir(path)


def get_bstack_credentials():
    """Return the users Browserstack credentials"""
    try:
        from diffbrowsers.utils import load_browserstack_credentials
        return load_browserstack_credentials()
    except:
        username = os.environ.get("BSTACK_USERNAME")
        access_key = os.environ.get("BSTACK_ACCESS_KEY")
        if all([username, access_key]):
            return (username, access_key)
        return False


def run_fontbakery(fonts_paths, out):
    fb_cmd = ["fontbakery", "check-googlefonts", "-l", "WARN"] + \
             fonts_paths + \
             ["-C"] + \
             ["--ghmarkdown", os.path.join(out, "report.md")]
    subprocess.call(fb_cmd)


def run_plot_glyphs(fonts, out):
    for font in fonts:
        font_filename = os.path.basename(font)[:-4]
        dfont = DFont(font)
        if dfont.is_variable:
            for coords in dfont.instances_coordinates:
                dfont.set_variations(coords)
                img_out = os.path.join(out, "%s_%s.png" % (
                    font_filename, _instance_coords_to_filename(coords) 
                    ))
                dfont.glyphs.to_png(img_out, limit=100000)
        else:
            img_out = os.path.join(out, font_filename + ".png")
            dfont.glyphs.to_png(dst=img_out)


def run_browser_previews(fonts, out, auth, local=False,
        gfr_url="http://159.65.243.73/"):
    browsers_to_test = test_browsers["vf_browsers"]
    for font_path in fonts:
        font_name = os.path.basename(font_path)[:-4]
        diff_browsers = DiffBrowsers(
                auth=auth,
                gfr_instance_url=gfr_url,
                dst_dir=os.path.join(out, font_name),
                browsers=browsers_to_test,
                gfr_is_local=local)
        diff_browsers.new_session([font_path], [font_path])
        diff_browsers.diff_view("waterfall")
        diff_browsers.diff_view("glyphs_all", pt=15)


def on_each_matching_font(func):
    def func_wrapper(fonts_before, fonts_after, out, *args, **kwargs):
        fonts_before_ttfonts = [TTFont(f) for f in fonts_before]
        fonts_after_ttfonts = [TTFont(f) for f in fonts_after]
        fonts_before_h = font_instances(fonts_before_ttfonts)
        fonts_after_h = font_instances(fonts_after_ttfonts)
        shared = set(fonts_before_h.keys()) & set(fonts_after_h.keys())
        if not shared:
            raise Exception(("Cannot find matching fonts. Are font "
                             "filenames the same?"))
        for font in shared:
            out_for_font = os.path.join(out, font)
            func(fonts_before_h[font], fonts_after_h[font], out_for_font,
                 *args, **kwargs)
    return func_wrapper


@on_each_matching_font
def run_diffbrowsers(font_before, font_after, out, auth, local=False,
                     gfr_url="http://159.65.243.73/"):
    browsers_to_test = test_browsers["vf_browsers"]
    diff_browsers = DiffBrowsers(
        auth=auth,
        gfr_instance_url=gfr_url,
        dst_dir=out,
        browsers=browsers_to_test,
        gfr_is_local=local)
    diff_browsers.new_session([font_before],
                              [font_after])
    diff_browsers.diff_view("waterfall")
    has_vfs = any([
        'fvar' in TTFont(font_before).keys(),
        'fvar' in TTFont(font_after).keys()
    ])
    if has_vfs:
        for i in range(14, 17):    
            diff_browsers.diff_view("glyphs_all", pt=i)


@on_each_matching_font
def run_diffenator(font_before, font_after, out, thresholds):
    font_before = DFont(font_before)
    font_after = DFont(font_after)
 
    if font_after.is_variable and not font_before.is_variable:
        font_after.set_variations_from_static(font_before)

    elif not font_after.is_variable and font_before.is_variable:
        font_before.set_variations_from_static(font_after)

    elif font_after.is_variable and font_before.is_variable:
        # TODO get wdth and slnt axis vals
        variations = {"wght": font_before.ttfont["OS/2"].usWeightClass}
        font_after.set_variations(variations)
        font_before.set_variations(variations)

    diff = DiffFonts(font_before, font_after, settings=thresholds)
    diff.to_gifs(dst=out)
    diff.to_txt(20, os.path.join(out, "report.txt"))
    diff.to_md(20, os.path.join(out, "report.md"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("fonts", nargs="+")
    before_group = parser.add_argument_group(title="Fonts before input")
    before_input_group = before_group.add_mutually_exclusive_group(required=False)
    before_input_group.add_argument('-fb', '--fonts-before', nargs="+",
                                  help="Fonts before paths")
    before_input_group.add_argument('-gf', '--from-googlefonts', action='store_true',
                               help="Diff against GoogleFonts instead of fonts_before")
    parser.add_argument("-o", "--out", default="out")
    parser.add_argument("-a", "--auto-qa", action="store_true",
            help="Determine which QA tools to run for fonts")
    parser.add_argument("--diffenator", action="store_true",
            help="Run Fontdiffenator")
    parser.add_argument("--diffbrowsers", action="store_true",
            help="Run diffbrowsers")
    parser.add_argument("--fontbakery", action="store_true",
            help="Run FontBakery")
    parser.add_argument("--plot-glyphs", action="store_true",
            help="Gen images of full charset, useful for new familes")
    parser.add_argument("--browser-previews", action="store_true",
            help="Gen images on diff platforms, useful for new families")
    parser.add_argument("-dm", "--diff-mode", choices=("weak", "normal", "strict"),
                        default="normal")
    parser.add_argument("-l", "--gfr-is-local", action="store_true", default=False)
    parser.add_argument("-rd", "--render-diffs", action="store_true", default=False)
    args = parser.parse_args()

    mkdir(args.out, overwrite=False)

    fonts_to_check = args.fonts
    fonts_previous = any([args.fonts_before, args.from_googlefonts])

    if args.gfr_is_local:
        gfr_url = "http://0.0.0.0:5000"
    else:
        # This instance of GFR can only view waterfalls and all glyphs views.
        # To view font diffs in a browser, run GFR locally. This script gens
        # font diffs using diffenator's to_gifs method, which relies on the
        # free rendering stack.
        gfr_url = "http://159.65.243.73/"

    bstack_credentials = get_bstack_credentials()

    fonts_to_check_ttfonts = [TTFont(f) for f in fonts_to_check]
    family_name = family_name_from_fonts(fonts_to_check_ttfonts)

    if fonts_previous:
        if args.from_googlefonts:
            fonts_before = download_family_from_Google_Fonts(
                    family_name, tempfile.mkdtemp())
        else:
            fonts_before = args.fonts_before

    # auto-qa
    family_on_gf = Google_Fonts_has_family(family_name)
    if args.auto_qa and family_on_gf:
        logging.info("Family exists on GF. Running regression checks")
        fonts_before = download_family_from_Google_Fonts(
                family_name, tempfile.mkdtemp())

        fb_out_dir = os.path.join(args.out, "Fontbakery")
        mkdir(fb_out_dir)
        run_fontbakery(fonts_to_check, fb_out_dir)

        diff_out_dir = os.path.join(args.out, "Diffenator")
        mkdir(diff_out_dir)
        run_diffenator(fonts_before, fonts_to_check, diff_out_dir,
                thresholds=DIFFENATOR_THRESHOLDS[args.diff_mode])

        if not bstack_credentials:
            logger.warning(("Skipping Diffbrowsers. No browserstack "
                            "credentials found. See diffbrowsers readme"))
        else:
            browser_out_dir = os.path.join(args.out, "Diffbrowsers")
            mkdir(browser_out_dir)
            run_diffbrowsers(fonts_before, fonts_to_check, browser_out_dir,
                             bstack_credentials, args.gfr_is_local, gfr_url=gfr_url)
        return
    elif args.auto_qa and not family_on_gf:
        logging.info(("Family does not exist on GF. Running plot_glyphs and "
            "browser_previews"))
        fb_out_dir = os.path.join(args.out, "Fontbakery")
        mkdir(fb_out_dir)
        run_fontbakery(fonts_to_check, fb_out_dir)

        glyphs_out_dir = os.path.join(args.out, "Plot_Glyphs")
        mkdir(glyphs_out_dir)
        run_plot_glyphs(fonts_to_check, glyphs_out_dir)

        if not bstack_credentials:
            logger.warning(("Skipping Browser Previews. No browserstack "
            "credentials found. See diffbrowsers readme"))
        else:
            browser_out_dir = os.path.join(args.out, "Browser_Previews")
            mkdir(browser_out_dir)
            run_browser_previews(fonts_to_check, browser_out_dir,
                    bstack_credentials, args.gfr_is_local, gfr_url=gfr_url)
        return

    # Run FB
    if args.fontbakery:
        fb_out_dir = os.path.join(args.out, "Fontbakery")
        mkdir(fb_out_dir)
        run_fontbakery(fonts_to_check, fb_out_dir)
    else:
        logger.info("Skipping fontbakery")

    # Font Diffenator
    if args.diffenator and fonts_previous:
        diff_out_dir = os.path.join(args.out, "Diffenator")
        mkdir(diff_out_dir)
        run_diffenator(fonts_before, fonts_to_check, diff_out_dir,
                thresholds=DIFFENATOR_THRESHOLDS[args.diff_mode])
    else:
        logger.info("Skipping diffenator")

    # Run DiffBrowsers
    if all([args.diffbrowsers, fonts_previous, bstack_credentials]):
        browser_out_dir = os.path.join(args.out, "Diffbrowsers")
        mkdir(browser_out_dir)
        run_diffbrowsers(fonts_before, fonts_to_check, browser_out_dir,
                         bstack_credentials, args.gfr_is_local, gfr_url=gfr_url)
    elif args.diffbrowsers and not bstack_credentials:
        logger.warning(("Skipping Diffbrowsers. No browserstack credentials "
                        "found. See diffbrowsers readme"))
    else:
        logger.info("Skipping Diffbrowsers")

    # Plot Glyphs
    if args.plot_glyphs:
        glyphs_out_dir = os.path.join(args.out, "Plot_Glyphs")
        mkdir(glyphs_out_dir)
        run_plot_glyphs(fonts_to_check, glyphs_out_dir)
    else:
        logger.info("Skipping Glyphs plot")

    # Browser Previews
    if args.browser_previews and bstack_credentials:
        browser_out_dir = os.path.join(args.out, "Browser_Previews")
        mkdir(browser_out_dir)
        run_browser_previews(fonts_to_check, browser_out_dir,
                             bstack_credentials, args.gfr_is_local, gfr_url=gfr_url)
    elif args.browser_previews and not bstack_credentials:
        logger.warning(("Skipping Browser Previews. No browserstack credentials "
                        "found. See diffbrowsers readme"))
    else:
        logger.info("Skipping browser_previews")


if __name__ == "__main__":
    main()

