#!/usr/bin/env python3
"""Check a font family.

Generate test reports for FontBakery, Font Diffenator and Diffbrowsers.

:

Check a family against the same family hosted on Google Fonts:
`gftools qa [fonts.ttf] -a -o qa`

Check a family against another local family and generate reports for
Font Diffenator only:
`gftools qa [fonts_a.ttf] -fb [fonts_b.ttf] --diffenator -o qa`

Check a family against the same family hosted on Google Fonts and
generate reports for Diffbrowserrs only:
`gftools qa [fonts.ttf] -gf --diffbrowsers -o qa
"""
from fontTools.ttLib import TTFont
from diffenator.diff import DiffFonts
from diffenator.font import DFont
from diffbrowsers.diffbrowsers import DiffBrowsers
from diffbrowsers.utils import load_browserstack_credentials
from diffbrowsers.browsers import test_browsers
import argparse
import shutil
import os
from glob import glob
import subprocess
import tempfile
import logging
from uuid import uuid4
import requests
from io import BytesIO
import json
from zipfile import ZipFile
from gftools.utils import (
    download_family_from_Google_Fonts,
    download_file,
    Google_Fonts_has_family,
    load_Google_Fonts_api_key,
)
import re

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

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
    results = []
    for font in fonts:
        family_name = font['name'].getName(1, 3, 1, 1033)
        typo_family_name = font['name'].getName(16, 3, 1, 1033)

        if typo_family_name:
            results.append(typo_family_name.toUnicode())
        elif family_name:
            results.append(family_name.toUnicode())
        else:
            raise Exception("Font: {} has no family name records".format(
                os.path.basename(font.reader.file.name))
            )
    if len(set(results)) > 1:
        raise Exception("Multiple family names found: [{}]".format(", ".join(results)))
    return results[0]


def mkdir(path, overwrite=True):
    if os.path.isdir(path) and overwrite:
        shutil.rmtree(path)
    if not os.path.isdir(path):
        os.mkdir(path)


def get_bstack_credentials():
    """Return the users Browserstack credentials"""
    credentials = load_browserstack_credentials()
    if not credentials:
        username = os.environ.get("BSTACK_USERNAME")
        access_key = os.environ.get("BSTACK_ACCESS_KEY")
        if all([username, access_key]):
            return (username, access_key)
        return False
    return credentials


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
        gfr_url="http://35.188.158.120/"):
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
                     gfr_url="http://35.188.158.120/"):
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
    info = os.path.join(out, "info.json")
    json.dump(diff_browsers.stats, open(info, "w"))
    if has_vfs:
        for i in range(15, 17):    
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
    diff.to_html(20, os.path.join(out, "report.html"), image_dir=".")


def get_fonts_in_pr(repo_slug=None, pull_id=None):
    # TODO Add context manager
    api_url = "https://api.github.com/repos/{}/pulls/{}/files?page={}&per_page=30"

    # Find last api page
    r = requests.get(api_url.format(repo_slug, str(pull_id), "1"),
        headers={'Authorization': 'token {}'.format(os.environ['GH_TOKEN'])})
    if 'link' in r.headers:
        pages = re.search(
            r'(?<=page\=)[0-9]{1,5}(?<!\&per_page=50\>\; rel="last")',
            r.headers['link']).group(0)
    else:
        pages = 1

    dst_dir = tempfile.mkdtemp()
    font_paths = []
    for page in range(1, int(pages) + 2):
        r = requests.get(api_url.format(repo_slug, str(pull_id), page),
            headers={'Authorization': 'token {}'.format(os.environ['GH_TOKEN'])})
        for item in r.json():
            download_url = item['raw_url']
            filename = item['filename']
            if "static" in filename:
                continue
            if filename.endswith('.ttf') and item['status'] != 'removed':
                dst = os.path.join(dst_dir, os.path.basename(filename))
                download_file(download_url, dst)
                font_paths.append(dst)
    return font_paths


def get_fonts_in_github_dir(url):
    url = url.replace('https://github.com/', 'https://api.github.com/repos/')
    url = url.replace("tree/master", "contents")
    font_paths = []
    r = requests.get(url,
        headers={'Authorization': 'token {}'.format(os.environ['GH_TOKEN'])})
    dst_dir = tempfile.mkdtemp()
    for item in r.json():
        if item['name'].endswith(".ttf"):
            f = item['download_url']
            dst = os.path.join(dst_dir, os.path.basename(f))
            download_file(f, dst)
            font_paths.append(dst)
    return font_paths


def post_media_to_gfr(paths, uuid):
    """Post images to GF Regression"""
    GFR_URL = 'http://35.188.158.120'
    url_endpoint = GFR_URL + '/api/upload-media'
    payload = [('files', open(path, 'rb')) for path in paths]
    r = requests.post(
        url_endpoint,
        data={'uuid': uuid},
        files=payload,
        headers={"Access-Token": os.environ["GFR_TOKEN"]}
    )
    return [os.path.join(GFR_URL, i) for i in r.json()['items']]


def post_gh_msg(msg, repo_slug=None, pull_id=None):
    if pull_id:
        url = "https://api.github.com/repos/{}/issues/{}/comments".format(repo_slug, pull_id)
        r = requests.post(url,
            data=json.dumps({'body': msg}),
            headers={'Authorization': 'token {}'.format(os.environ['GH_TOKEN'])})
    else:
        url = "https://api.github.com/repos/{}/issues".format(repo_slug)
        r = requests.post(url,
            data=json.dumps({'title': 'Google Fonts QA report', 'body': msg}),
            headers={'Authorization': 'token {}'.format(os.environ['GH_TOKEN'])})


def main():
    parser = argparse.ArgumentParser(
            description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter)

    after_group = parser.add_argument_group(title="Fonts after input")
    after_input_group = after_group.add_mutually_exclusive_group(required=True)
    after_input_group.add_argument("-fa", "--fonts-after", nargs="+")
    after_input_group.add_argument("-pr", "--pull-request")
    after_input_group.add_argument("-gh", "--github-dir")

    before_group = parser.add_argument_group(title="Fonts before input")
    before_input_group = before_group.add_mutually_exclusive_group(required=False)
    before_input_group.add_argument('-fb', '--fonts-before', nargs="+",
                                  help="Fonts before paths")
    before_input_group.add_argument('-gf', '--from-googlefonts', action='store_true',
                               help="Diff against GoogleFonts instead of fonts_before")

    parser.add_argument("-a", "--auto-qa", action="store_true",
            help="Check the fonts against against the same fonts hosted on Google Fonts")
    parser.add_argument("--diffenator", action="store_true",
            help="Run Fontdiffenator")
    parser.add_argument("--diffbrowsers", action="store_true",
            help="Run diffbrowsers")
    parser.add_argument("--fontbakery", action="store_true",
            help="Run FontBakery")
    parser.add_argument("--plot-glyphs", action="store_true",
            help="Gen images of full charset, useful for new familes")
    parser.add_argument("--browser-previews", action="store_true",
            help="Gen images on diff browsers, useful for new families")
    parser.add_argument("-dm", "--diff-mode", choices=("weak", "normal", "strict"),
                        default="normal")
    parser.add_argument("-l", "--gfr-is-local", action="store_true", default=False,
            help="Use locally run GFRefgression")
    parser.add_argument("-rd", "--render-diffs", action="store_true", default=False,
            help=("Calculate glyph differences by rendering them then "
                  "counting the pixel difference"))
    parser.add_argument("-o", "--out", default="out",
            help="Output path for check results")
    parser.add_argument("-ogh", "--out-github", action="store_true",
            help=("Post report data to either the pull request as a comment "
                 "open a new issue"))
    args = parser.parse_args()

    mkdir(args.out, overwrite=False)

    fonts_to_check = args.pull_request if args.pull_request else args.fonts_after
    if args.pull_request:
        url_split = args.pull_request.split("/")
        repo_slug = "{}/{}".format(url_split[3], url_split[4])
        repo_pull_id = url_split[-1]
        if "pull" not in args.pull_request:
            raise Exception("{} is not a valid github pull request url".format(
                args.pull_request))
        logging.warning("Downloading fonts from pr {}".format(args.pull_request))
        fonts_to_check = get_fonts_in_pr(repo_slug, repo_pull_id)
    elif args.github_dir:
        url_split = args.github_dir.split("/")
        repo_slug = "{}/{}".format(url_split[3], url_split[4])
        repo_pull_id = url_split[-1]
        if "github" not in args.github_dir:
            raise Exception("{} is not a valid github dir".format(args.github_dir))
        logger.warning("Downloading fonts from github dir {}".format(args.github_dir))
        fonts_to_check = get_fonts_in_github_dir(args.github_dir)

    fonts_previous = any([args.fonts_before, args.from_googlefonts])

    if args.gfr_is_local:
        gfr_url = "http://0.0.0.0:5000"
    else:
        # This instance of GFR can only view waterfalls and all glyphs views.
        # To view font diffs in a browser, run GFR locally. This script gens
        # font diffs using diffenator's to_gifs method, which relies on the
        # free rendering stack.
        gfr_url = "http://35.188.158.120/"

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

    # Post results to github
    if args.out_github and (args.pull_request or args.github_dir):
        logging.warning("Posting report and file to github")
        report_zip = shutil.make_archive(args.out, "zip", args.out)
        uuid = str(uuid4())
        zip_url = post_media_to_gfr([report_zip], uuid)
        with open(os.path.join(args.out, "Fontbakery", "report.md"), "r") as fb:
            msg = "{}\n\n## Diff images: [{}]({})".format(
                    fb.read(), os.path.basename(zip_url[0]), zip_url[0])
            if args.pull_request:
                post_gh_msg(msg, repo_slug, repo_pull_id)
            elif args.github_dir:
                post_gh_msg(msg, repo_slug)


if __name__ == "__main__":
    main()

