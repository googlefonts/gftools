import logging
import os
import re
import subprocess

from gftools.github import GitHubClient
from gftools.utils import mkdir
from gftools.html import HtmlProof, HtmlDiff
try:
    from diffenator.diff import DiffFonts
    from diffenator.font import DFont
    from diffbrowsers.utils import load_browserstack_credentials as bstack_creds
except ModuleNotFoundError:
    raise ModuleNotFoundError(("gftools was installed without the QA "
        "dependencies. To install the dependencies, see the ReadMe, "
        "https://github.com/googlefonts/gftools#installation"))

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

        html = HtmlDiff(
            out=dst,
            fonts_before=[f.reader.file.name for f in self.fonts_before],
            fonts_after=[f.reader.file.name for f in self.fonts],
        )
        html.build_pages(["waterfall.html", "text.html"])
        html.build_pages(["glyphs.html"], pt_size=16)
        html.save_imgs()

    def fontbakery(self, profile="googlefonts", html=False, extra_args=None):
        logger.info("Running Fontbakery")
        out = os.path.join(self.out, "Fontbakery")
        mkdir(out)
        cmd = (
            ["fontbakery", "check-"+profile, "-l", "INFO", "--succinct"]
            + [f.reader.file.name for f in self.fonts]
            + ["-C"]
            + ["--ghmarkdown", os.path.join(out, "report.md")]
        )
        if html:
            cmd.extend(["--html", os.path.join(out, "report.html")])
        if extra_args:
            cmd.extend(extra_args)
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
        html = HtmlProof(
            out=out,
            fonts=[f.reader.file.name for f in self.fonts]
        )
        html.build_pages(["waterfall.html", "text.html"])
        html.build_pages(["glyphs.html"], pt_size=16)
        html.save_imgs()

    def googlefonts_upgrade(self):
        self.fontbakery()
        self.diffenator()
        self.diffbrowsers()

    def googlefonts_new(self):
        self.fontbakery()
        self.plot_glyphs()
        self.browser_previews()

    def post_to_github(self, url):
        """Post Fontbakery report as a new issue or as a comment to an open
        PR"""
        # Parse url tokens
        url_split = url.split("/")
        repo_owner = url_split[3]
        repo_name = url_split[4]
        issue_number = url_split[-1] if "pull" in url else None

        fontbakery_report = os.path.join(self.out, "Fontbakery", "report.md")
        if not os.path.isfile(fontbakery_report):
            logger.warning(
                "Cannot Post Github message because no Fontbakery report exists"
            )
            return
        
        client = GitHubClient(repo_owner, repo_name)

        with open(fontbakery_report) as doc:
            msg = doc.read()
            if issue_number:
                client.create_issue_comment(issue_number, msg)
            else:
                client.create_issue("Google Font QA report", msg)
