import logging
import os
import subprocess

from gftools.gfgithub import GitHubClient
from gftools.utils import mkdir
try:
    from diffenator2 import ninja_diff, ninja_proof
except ModuleNotFoundError:
    raise ModuleNotFoundError(("gftools was installed without the QA "
        "dependencies. To install the dependencies, see the ReadMe, "
        "https://github.com/googlefonts/gftools#installation"))

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class FontQA:
    def __init__(self, fonts, fonts_before=None, out="out", url=None):
        self.fonts = fonts
        self.fonts_before = fonts_before
        self.out = out
        self.url = url

    def diffenator(self, **kwargs):
        logger.info("Running Diffenator")
        if not self.fonts_before:
            logger.warning(
                "Cannot run Diffenator since there are no fonts before"
            )
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

    def diffbrowsers(self, imgs=False):
        logger.info("Running Diffbrowsers")
        if not self.fonts_before:
            logger.warning(
                "Cannot run diffbrowsers since there are no fonts before"
            )
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

    def fontbakery(self, profile="googlefonts", html=False, extra_args=None):
        logger.info("Running Fontbakery")
        out = os.path.join(self.out, "Fontbakery")
        mkdir(out)
        cmd = (
            ["fontbakery", "check-"+profile, "-l", "INFO", "--succinct"]
            + [f.path for f in self.fonts]
            + ["-C"]
            + ["--ghmarkdown", os.path.join(out, "report.md")]
        )
        if html:
            cmd.extend(["--html", os.path.join(out, "report.html")])
        if extra_args:
            cmd.extend(extra_args)
        subprocess.call(cmd)

        fontbakery_report = os.path.join(self.out, "Fontbakery", "report.md")
        if not os.path.isfile(fontbakery_report):
            logger.warning(
                "Cannot Post Github message because no Fontbakery report exists"
            )
            return
        with open(fontbakery_report) as doc:
            msg = doc.read()
            self.post_to_github(msg)

    def googlefonts_upgrade(self, imgs=False):
        self.fontbakery()
        self.diffenator()
        self.diffbrowsers(imgs)

    def googlefonts_new(self, imgs=False):
        self.fontbakery()
        self.proof(imgs)

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

        if issue_number:
            client.create_issue_comment(issue_number, text)
        else:
            client.create_issue("Google Font QA report", text)
