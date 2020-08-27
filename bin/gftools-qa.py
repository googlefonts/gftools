#!/usr/bin/env python3
"""Check a font family using Google Fonts QA tools.

Examples:
Check a local family against the same family hosted on Google Fonts:
`gftools qa -f [fonts.ttf] -gfb -a -o qa`

Check a local family against another local family and generate reports
for Font Diffenator only:
`gftools qa -f [fonts_a.ttf] -fb [fonts_b.ttf] --diffenator -o qa`

Check a local family against the same family hosted on Google Fonts and
generate reports for Diffbrowsers only:
`gftools qa -f [fonts.ttf] -gf --diffbrowsers -o qa

Compare a pull request against the same family hosted on Google Fonts:
`gftools qa -pr www.github.com/user/repo/pull/1 -gfb -a -o qa`

Compare a github folder of fonts against the same family hosted on Google
Fonts:
`gftools qa -gh www.github.com/user/repo/tree/fonts/ttf -gfb -a -o qa`
"""
from fontTools.ttLib import TTFont
import argparse
import shutil
import os
from glob import glob
import subprocess
import logging
from uuid import uuid4
import re
import requests
from io import BytesIO
import json
from zipfile import ZipFile
import time
from gftools.utils import (
    download_family_from_Google_Fonts,
    download_files_in_github_pr,
    download_files_in_github_dir,
    download_file,
    Google_Fonts_has_family,
    load_Google_Fonts_api_key,
    mkdir,
)
try:
    from diffenator.diff import DiffFonts
    from diffenator.font import DFont
    from diffbrowsers.diffbrowsers import DiffBrowsers
    from diffbrowsers.browsers import test_browsers
    from diffbrowsers.utils import load_browserstack_credentials as bstack_creds
except ModuleNotFoundError:
    raise ModuleNotFoundError(("gftools was installed without the QA "
        "dependencies. To install the dependencies, see the ReadMe, "
        "https://github.com/googlefonts/gftools#installation"))

__version__ = "2.1.3"
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def load_browserstack_credentials():
    """Return the user's Browserstack credentials"""
    credentials = bstack_creds()
    if not credentials:
        username = os.environ.get("BSTACK_USERNAME")
        access_key = os.environ.get("BSTACK_ACCESS_KEY")
        if all([username, access_key]):
            return (username, access_key)
        return False
    return credentials


class FontQA:

    GFR_URL = "http://35.238.63.0/"

    def __init__(self, fonts, fonts_before=None, out="out"):
        self.fonts = fonts
        self.fonts_before = fonts_before

        self.instances = self._instances_in_fonts(self.fonts)
        self.instances_before = self._instances_in_fonts(self.fonts_before)
        self.matching_instances = self._matching_instances()

        self._bstack_auth = load_browserstack_credentials()
        self.out = out

    def _instances_in_fonts(self, ttfonts):
        """Get all font instances from a collection of fonts.

        This function works for both a static and variable font collections.
        If a font is variable, it will retrieve the font's instances
        using the fvar table. If a font is static, it will only return a
        single instance by using the font's filename.
        """
        if not ttfonts:
            return None
        results = {}
        for ttfont in ttfonts:
            if "fvar" in ttfont:
                for instance in ttfont['fvar'].instances:
                    nameid = instance.subfamilyNameID
                    name = ttfont['name'].getName(nameid, 3, 1, 1033).toUnicode()
                    name = name.replace(" ", "")
                    results[name] = {
                        "coordinates": instance.coordinates,
                        "filename": ttfont.reader.file.name
                    }
            else:
                filename = os.path.basename(ttfont.reader.file.name)
                name = filename.split("-")[1]
                name = re.sub(".ttf|.otf", "", name)
                results[name] = {
                    "coordinates": {"wght": ttfont['OS/2'].usWeightClass},
                    "filename": ttfont.reader.file.name
                }
        return results

    def _matching_instances(self):
        if not self.fonts_before:
            logger.info(
                "No regression checks possible since there are no previous fonts."
            )
            return None
        shared = set(self.instances_before.keys()) & set(self.instances.keys())
        new = set(self.instances.keys()) - set(self.instances_before.keys())
        missing = set(self.instances_before.keys()) - set(self.instances.keys())
        if new:
            logger.warning("New fonts: {}".format(", ".join(new)))
        if missing:
            logger.warning("Missing fonts: {}".format(", ".join(missing)))
        if not shared:
            raise Exception(
                (
                    "Cannot find matching fonts!\n"
                    "fonts: [{}]\nfonts_before: [{}]".format(
                        ", ".join(set(self.instances.keys())),
                        ", ".join(set(self.instances_before.keys()))
                     )
                )
            )
        return shared

    def diffenator(self, **kwargs):
        logger.info("Running Diffenator")
        dst = os.path.join(self.out, "Diffenator")
        mkdir(dst)
        for style in self.matching_instances:
            font_before = DFont(self.instances_before[style]['filename'])
            font_after = DFont(self.instances[style]['filename'])
            out = os.path.join(dst, style)
            if font_after.is_variable and not font_before.is_variable:
                font_after.set_variations_from_static(font_before)

            elif not font_after.is_variable and font_before.is_variable:
                font_before.set_variations_from_static(font_after)

            elif font_after.is_variable and font_before.is_variable:
                coordinates = self.instances_before[style]['coordinates']
                font_after.set_variations(coordinates)
                font_before.set_variations(coordinates)

            # TODO add settings
            diff = DiffFonts(font_before, font_after, {"render_diffs": True})
            diff.to_gifs(dst=out)
            diff.to_txt(20, os.path.join(out, "report.txt"))
            diff.to_md(20, os.path.join(out, "report.md"))
            diff.to_html(20, os.path.join(out, "report.html"), image_dir=".")

    @staticmethod
    def chunkify(items, size):
        return [items[i : i + size] for i in range(0, len(items), size)]

    def _diffbrowsers_job(self, dst, group, browsers_to_test):
        styles = [i[0] for i in group]
        dir_name = "_".join(styles)
        fonts_before = [i[1] for i in group]
        fonts_after = [i[2] for i in group]
        out = os.path.join(dst, dir_name)
        diff_browsers = DiffBrowsers(
            auth=self._bstack_auth,
            gfr_instance_url=self.GFR_URL,
            dst_dir=out,
            browsers=browsers_to_test,
        )
        diff_browsers.new_session(set(fonts_before), set(fonts_after))

        waterfall_diff_view = diff_browsers.diff_view("waterfall", styles=styles)
        glyphs_all_diff_view = diff_browsers.diff_view("glyphs_all", pt=16, styles=styles)

        poll_jobs = []
        generators = [waterfall_diff_view, glyphs_all_diff_view]
        for gen in generators:
            status, jobs = next(gen)
            assert status == 'poll jobs'
            poll_jobs.extend(jobs)

        yield 'poll jobs', poll_jobs
        # finalize, only the result of waterfall_diff_view_stats will be captured
        try:
            next(waterfall_diff_view)
            raise Exception('StopIteration expected.')
        except StopIteration as e:
            waterfall_diff_view_stats = e.value
        info = os.path.join(out, "info.json")
        json.dump(waterfall_diff_view_stats, open(info, "w"))
        # finish all properly
        for gen in generators:
            yield from gen

    def _poll_jobs(self, poll_jobs):
        jobs_active = {}
        jobs_done = set()
        started = 0
        suspend = 0

        while len(jobs_active) or started < len(poll_jobs):
            if started < len(poll_jobs):
                for job in poll_jobs:
                    if suspend > time.time():
                        break;
                    if job in jobs_active or job in jobs_done:
                        continue
                    status, min_wait_time = next(job)
                    # yield 'suspend', generate_resp_json['Retry-After']
                    if status == 'suspend':
                        suspend = time.time() + min_wait_time
                        break
                    assert status == 'initial'
                    started += 1
                    jobs_active[job] = (time.time(), min_wait_time)

            min_next = 0
            for job in list(jobs_active):
                last_tick, min_wait_time = jobs_active[job]
                now = time.time()
                schedule = last_tick + min_wait_time
                if now >= schedule:
                    # due for an iteration
                    try:
                        status, min_wait_time = next(job)
                        assert status == 'pending'
                        jobs_active[job] = (time.time(), min_wait_time)
                    except StopIteration:
                        # this one is done
                        del jobs_active[job]
                        jobs_done.add(job)
                else:
                    min_next = min(min_next, min_wait_time)
            sleep_time = min_next - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)

    def diffbrowsers(self, **kwargs):
        """Test fonts on GFR regression and take screenshots using
        diffbrowsers. A browserstack account is required."""
        logger.info("Running Diffbrowsers")
        if not self._bstack_auth:
            logger.info("Skipping. No Browserstack credentials. "
                    "See https://github.com/googlefonts/"
                    "diffbrowsers#installation on how to add them.")
            return
        dst = os.path.join(self.out, "Diffbrowsers")
        mkdir(dst)
        browsers_to_test = test_browsers["vf_browsers"]
        fonts = [(k, self.instances_before[k]['filename'],
                     self.instances[k]['filename']) for k in self.matching_instances]
        font_groups = self.chunkify(sorted(fonts), 4)

        poll_jobs = []
        generators = []
        for group in font_groups:
            generators.append(self._diffbrowsers_job(dst, group, browsers_to_test))
        for gen in generators:
            status, jobs = next(gen)
            assert status == 'poll jobs'
            poll_jobs.extend(jobs)

        self._poll_jobs(poll_jobs)

        for gen in generators:
            # finalize all generators
            for _ in gen: pass


    def fontbakery(self):
        logger.info("Running Fontbakery")
        out = os.path.join(self.out, "Fontbakery")
        mkdir(out)
        cmd = (
            ["fontbakery", "check-googlefonts", "-l", "WARN"]
            + [f.reader.file.name for f in self.fonts]
            + ["-C"]
            + ["--ghmarkdown", os.path.join(out, "report.md")]
        )
        subprocess.call(cmd)

    def plot_glyphs(self):
        logger.info("Running plot glyphs")
        out = os.path.join(self.out, "plot_glyphs")
        mkdir(out)
        fonts = [f.reader.file.name for f in self.fonts]
        for font in fonts:
            font_filename = os.path.basename(font)[:-4]
            dfont = DFont(font)
            if dfont.is_variable:
                for _, coords in dfont.instances_coordinates.items():
                    dfont.set_variations(coords)
                    img_out = os.path.join(
                        out,
                        "%s_%s.png"
                        % (font_filename, self._instance_coords_to_filename(coords)),
                    )
                    dfont.glyphs.to_png(img_out, limit=100000)
            else:
                img_out = os.path.join(out, font_filename + ".png")
                dfont.glyphs.to_png(dst=img_out)

    def _instance_coords_to_filename(self, d):
        name = ""
        for k, v in d.items():
            name += "{}_{}_".format(k, v)
        return name[:-1]

    def browser_previews(self, **kwargs):
        """Use GFR and diffbrowsers to take screenshots of how the fonts
        will look on different browsers. A Browserstack account is
        required."""
        logger.info("Running browser previews")
        if not self._bstack_auth:
            logger.info("Skipping. No Browserstack credentials. "
                    "See https://github.com/googlefonts/"
                    "diffbrowsers#installation on how to add them.")
            return
        out = os.path.join(self.out, "browser_previews")
        mkdir(out)
        browsers_to_test = test_browsers["vf_browsers"]
        font_groups = self.chunkify(list([i['filename'] for i in self.instances.values()]), 4)
        name_groups = self.chunkify(list(self.instances.keys()), 4)
        for name_group, font_group in zip(name_groups, font_groups):
            name = "_".join(sorted(name_group))
            diff_browsers = DiffBrowsers(
                auth=self._bstack_auth,
                gfr_instance_url=FontQA.GFR_URL,
                dst_dir=os.path.join(out, name),
                browsers=browsers_to_test,
                gfr_is_local=False,
            )
            diff_browsers.new_session(font_group, font_group)
            diff_browsers.diff_view("waterfall", styles=name_group)
            diff_browsers.diff_view("glyphs_all", styles=name_group, pt=15)

    def googlefonts_upgrade(self):
        self.fontbakery()
        self.diffenator()
        self.diffbrowsers()

    def googlefonts_new(self):
        self.fontbakery()
        self.plot_glyphs()
        self.browser_previews()

    def post_to_github(self, url):
        """Zip and post the check results as a comment to the github
        issue or pr."""
        report_zip = shutil.make_archive(self.out, "zip", self.out)
        uuid = str(uuid4())
        zip_url = self._post_media_to_gfr([report_zip], uuid)

        url_split = url.split("/")
        repo_slug = "{}/{}".format(url_split[3], url_split[4])
        pull = url_split[-1] if "pull" in url else None

        fontbakery_report = os.path.join(self.out, "Fontbakery", "report.md")
        if os.path.isfile(fontbakery_report):
            with open(fontbakery_report, "r") as fb:
                msg = "{}\n\n## Diff images: [{}]({})".format(
                    fb.read(), os.path.basename(zip_url[0]), zip_url[0]
                )
        else:
            msg = "## Diff images: [{}]({})".format(
                os.path.basename(zip_url[0]), zip_url[0]
            )
        self._post_gh_msg(msg, repo_slug, pull)

    def _post_media_to_gfr(self, paths, uuid):
        """Post images to GF Regression"""
        url_endpoint = self.GFR_URL + "/api/upload-media"
        payload = [("files", open(path, "rb")) for path in paths]
        r = requests.post(
            url_endpoint,
            data={"uuid": uuid},
            files=payload,
            headers={"Access-Token": os.environ["GFR_TOKEN"]},
        )
        return [os.path.join(self.GFR_URL, i) for i in r.json()["items"]]

    def _post_gh_msg(self, msg, repo_slug=None, pull_id=None):
        if pull_id:
            url = "https://api.github.com/repos/{}/issues/{}/comments".format(
                repo_slug, pull_id
            )
            r = requests.post(
                url,
                data=json.dumps({"body": msg}),
                headers={"Authorization": "token {}".format(os.environ["GH_TOKEN"])},
            )
        else:
            url = "https://api.github.com/repos/{}/issues".format(repo_slug)
            r = requests.post(
                url,
                data=json.dumps({"title": "Google Fonts QA report", "body": msg}),
                headers={"Authorization": "token {}".format(os.environ["GH_TOKEN"])},
            )


def family_name_from_fonts(fonts):
    results = []
    for font in fonts:
        family_name = font["name"].getName(1, 3, 1, 1033)
        typo_family_name = font["name"].getName(16, 3, 1, 1033)

        if typo_family_name:
            results.append(typo_family_name.toUnicode())
        elif family_name:
            results.append(family_name.toUnicode())
        else:
            raise Exception(
                "Font: {} has no family name records".format(
                    os.path.basename(font.reader.file.name)
                )
            )
    if len(set(results)) > 1:
        raise Exception("Multiple family names found: [{}]".format(", ".join(results)))
    return results[0]


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )

    font_group = parser.add_argument_group(title="Fonts to qa")
    font_input_group = font_group.add_mutually_exclusive_group(required=True)
    font_input_group.add_argument("-f", "--fonts", nargs="+",
        help="Paths to fonts")
    font_input_group.add_argument("-pr", "--pull-request",
        help="Get fonts from a Github pull request")
    font_input_group.add_argument("-gh", "--github-dir",
        help="Get fonts from a Github directory")
    font_input_group.add_argument("-gf", "--googlefonts",
        help="Get fonts from Google Fonts")

    font_before_group = parser.add_argument_group(title="Fonts before input")
    font_before_input_group = font_before_group.add_mutually_exclusive_group(
        required=False
    )
    font_before_input_group.add_argument(
        "-fb", "--fonts-before", nargs="+",
        help="Paths to previous fonts"
    )
    font_before_input_group.add_argument("-prb", "--pull-request-before",
        help="Get previous fonts from a Github pull request")
    font_before_input_group.add_argument("-ghb", "--github-dir-before",
        help="Get previous fonts from a Github dir")
    font_before_input_group.add_argument(
        "-gfb",
        "--googlefonts-before",
        action="store_true",
        help="Get previous fonts from Google Fonts",
    )

    check_group = parser.add_argument_group(title="QA checks")
    check_group.add_argument(
        "-a",
        "--auto-qa",
        action="store_true",
        help="Check fonts against against the same fonts hosted on Google Fonts",
    )
    check_group.add_argument(
        "--diffenator", action="store_true", help="Run Fontdiffenator"
    )
    check_group.add_argument(
        "--diffbrowsers", action="store_true", help="Run Diffbrowsers"
    )
    check_group.add_argument(
        "--fontbakery", action="store_true", help="Run FontBakery"
    )
    check_group.add_argument(
        "--plot-glyphs",
        action="store_true",
        help="Gen images of full charset, useful for new familes",
    )
    check_group.add_argument(
        "--browser-previews",
        action="store_true",
        help="Gen images on diff browsers, useful for new families",
    )
    check_group.add_argument(
        "-dm", "--diff-mode", choices=("weak", "normal", "strict"), default="normal"
    )
    parser.add_argument("-re", "--filter-fonts", help="Filter fonts by regex")
    parser.add_argument(
        "-o", "--out", default="out", help="Output path for check results"
    )
    parser.add_argument(
        "-ogh",
        "--out-github",
        action="store_true",
        help=(
            "Post report data to either the pull request as a comment "
            "open a new issue. This can only be used if fonts have been "
            "fetched from either a pull request or github dir."
        ),
    )
    parser.add_argument(
        "--out-url",
        help=(
            "Post report data to a github pr. This can be used with any font "
            "fetching method."
        )
    )
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args()
    if args.out_github and not any([args.pull_request, args.github_dir]):
        raise Exception(
            "Cannot upload results to a github issue or pr. "
            "Font input must either a github dir or a pull request"
        )
    if not any([args.auto_qa,
                args.fontbakery,
                args.plot_glyphs,
                args.diffbrowsers,
                args.diffenator,
                args.browser_previews]):
        raise Exception("Terminating. No checks selected. Run gftools qa "
                        "--help to see all possible commands.")


    # Retrieve fonts and store in out dir
    mkdir(args.out)
    fonts_dir = os.path.join(args.out, "fonts")
    mkdir(fonts_dir)
    if args.fonts:
        [shutil.copy(f, fonts_dir) for f in args.fonts]
        fonts = args.fonts
    elif args.pull_request:
        fonts = download_files_in_github_pr(
            args.pull_request,
            fonts_dir,
            ignore_static_dir=False,
        )
        if not fonts:
            logger.info("No fonts found in pull request. Skipping")
            return
    elif args.github_dir:
        fonts = download_files_in_github_dir(args.github_dir, fonts_dir)
        if not fonts:
            logger.info("No fonts found in github dir. Skipping")
            return
    elif args.googlefonts:
        fonts = download_family_from_Google_Fonts(args.googlefonts, fonts_dir)

    if args.filter_fonts:
        re_filter = re.compile(args.filter_fonts)
        fonts = [f for f in fonts if re_filter.search(f)]

    ttfonts = [TTFont(f) for f in fonts if f.endswith((".ttf", ".otf"))
               and "static" not in f]
    family_name = family_name_from_fonts(ttfonts)
    family_on_gf = Google_Fonts_has_family(family_name)

    # Retrieve fonts_before and store in out dir
    fonts_before = None
    if any([args.fonts_before, args.pull_request_before, args.github_dir_before]) or \
           (args.googlefonts_before and family_on_gf):
        fonts_before_dir = os.path.join(args.out, "fonts_before")
        mkdir(fonts_before_dir, overwrite=False)
    if args.fonts_before:
        [shutil.copy(f, fonts_before_dir) for f in args.fonts_before]
        fonts_before = args.fonts_before
    elif args.pull_request_before:
        fonts_before = download_files_in_github_pr(
            args.pull_request_before,
            fonts_before_dir,
            ignore_static_dir=False
        )
    elif args.github_dir_before:
        fonts_before = download_files_in_github_dir(
            args.github_dir_before, fonts_before_dir
        )
    elif args.googlefonts_before and family_on_gf:
        fonts_before = download_family_from_Google_Fonts(
            family_name, fonts_before_dir
        )

    if fonts_before:
        ttfonts_before = [TTFont(f) for f in fonts_before if f.endswith((".ttf", ".otf"))
                          and "static" not in f]
        qa = FontQA(ttfonts, ttfonts_before, args.out)
    else:
        qa = FontQA(ttfonts, out=args.out)

    if args.auto_qa and family_on_gf:
        qa.googlefonts_upgrade()
    elif args.auto_qa and not family_on_gf:
        qa.googlefonts_new()
    if args.plot_glyphs:
        qa.plot_glyphs()
    if args.browser_previews:
        qa.browser_previews()
    if args.fontbakery:
        qa.fontbakery()
    if args.diffenator:
        qa.diffenator()
    if args.diffbrowsers:
        qa.diffbrowsers()

    if args.out_url:
        qa.post_to_github(args.out_url)
    elif args.out_github and args.pull_request:
        qa.post_to_github(args.pull_request)
    elif args.out_github and args.github_dir:
        qa.post_to_github(args.github_dir)


if __name__ == "__main__":
    main()
