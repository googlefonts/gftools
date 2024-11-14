import logging
import os
import subprocess
import traceback

from gftools.gfgithub import GitHubClient
from gftools.utils import mkdir
import sys

try:
    from diffenator2 import ninja_diff, ninja_proof
except ModuleNotFoundError:
    raise ModuleNotFoundError(
        (
            "gftools was installed without the QA "
            "dependencies. To install the dependencies, see the ReadMe, "
            "https://github.com/googlefonts/gftools#installation"
        )
    )

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def report_exceptions(meth):
    def safe_call(self, *args, **kwargs):
        try:
            meth(self, *args, **kwargs)
        except Exception as e:
            msg = f"Call to {meth.__name__} failed:\n{e}"
            print(msg)
            print()
            print(traceback.format_exc())
            self.post_to_github(msg + "\n\n" + "See CI logs for more details")

    return safe_call


class FontQA:
    def __init__(self, fonts, fonts_before=None, out="out", url=None):
        self.fonts = fonts
        self.fonts_before = fonts_before
        self.out = out
        self.url = url
        self.has_error = False

    @report_exceptions
    def diffenator(self, **kwargs):
        logger.info("Running Diffenator")
        if not self.fonts_before:
            logger.warning("Cannot run Diffenator since there are no fonts before")
            return
        dst = os.path.join(self.out, "Diffenator")
        ninja_diff(
            self.fonts_before,
            self.fonts,
            out=dst,
            imgs=False,
            user_wordlist=None,
            filter_styles=None,
            diffenator=True,
            diffbrowsers=False,
        )

    @report_exceptions
    def diffbrowsers(self, imgs=False):
        logger.info("Running Diffbrowsers")
        if not self.fonts_before:
            logger.warning("Cannot run diffbrowsers since there are no fonts before")
            return
        dst = os.path.join(self.out, "Diffbrowsers")
        mkdir(dst)
        ninja_diff(
            self.fonts_before,
            self.fonts,
            out=dst,
            imgs=imgs,
            filter_styles=None,
            user_wordlist=None,
            diffenator=False,
            diffbrowsers=True,
        )

    @report_exceptions
    def proof(self, imgs=False):
        logger.info("Running proofing tools")
        dst = os.path.join(self.out, "Proof")
        mkdir(dst)
        ninja_proof(
            self.fonts,
            out=dst,
            imgs=imgs,
            filter_styles=None,
        )

    @report_exceptions
    def interpolations(self):
        dst = os.path.join(self.out, "Interpolations")
        if not any(f.is_variable() for f in self.fonts):
            return
        mkdir(dst)
        for font in self.fonts:
            font_dst = os.path.join(dst, f"{os.path.basename(font.path[:-4])}.pdf")
            if not font.is_variable():
                continue
            cmd = ["fonttools", "varLib.interpolatable", font.path, "--pdf", font_dst]
            subprocess.call(cmd)

    @report_exceptions
    def fontbakery(self, profile="googlefonts", html=False, extra_args=None):
        logger.info("Running Fontbakery")
        out = os.path.join(self.out, "Fontbakery")
        mkdir(out)
        cmd = (
            ["fontbakery", "check-" + profile, "-l", "INFO", "--succinct"]
            + [f.path for f in self.fonts]
            + ["-C"]
            + ["--ghmarkdown", os.path.join(out, "report.md")]
            + ["-e", "FATAL"]
        )
        if html:
            cmd.extend(["--html", os.path.join(out, "report.html")])
        if extra_args:
            cmd.extend(extra_args)
        process = subprocess.run(cmd)

        fontbakery_report = os.path.join(self.out, "Fontbakery", "report.md")
        if not os.path.isfile(fontbakery_report):
            logger.warning(
                "Cannot Post Github message because no Fontbakery report exists"
            )
            return
        with open(fontbakery_report) as doc:
            msg = doc.read()
            self.post_to_github(msg)

        if process.returncode != 0:
            self.has_error = True

    def googlefonts_upgrade(self, imgs=False):
        self.fontbakery()
        self.diffenator()
        self.diffbrowsers(imgs)
        self.interpolations()

    def googlefonts_new(self, imgs=False):
        self.fontbakery()
        self.proof(imgs)
        self.interpolations()

    def render(self, imgs=False):
        if self.fonts_before:
            self.diffbrowsers(imgs)
        else:
            self.proof(imgs)

    def post_to_github(self, text):
        """Post text as a new issue or as a comment to an open
        PR"""
        if not self.url:
            return
        # Parse url tokens
        url_split = self.url.split("/")
        repo_owner = url_split[3]
        repo_name = url_split[4]
        issue_number = url_split[-1] if "pull" in self.url else None

        client = GitHubClient(repo_owner, repo_name)

        try:
            if issue_number:
                client.create_issue_comment(issue_number, text)
            else:
                client.create_issue("Google Font QA report", text)
        except Exception as e:
            logger.warn(
                "Cannot post Fontbakery report!\n"
                "Most likely, the repository may lack a GH_TOKEN secret, or "
                "the pull request has come from a forked repo which "
                "is not allowed to access the repo's secrets for "
                f"security reasons. Full traceback:\n{e}"
            )
