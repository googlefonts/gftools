import logging
import os
from pathlib import Path
import subprocess
import traceback
from typing import List, Optional, Sequence

from gftools.gfgithub import GitHubClient
from gftools.utils import mkdir

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def has_interpolatable() -> bool:
    """Check if the interpolatable tool is available."""
    try:
        subprocess.run(
            ["interpolatable", "--version"], check=True, stdout=subprocess.PIPE
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def is_variable(font_path: str) -> bool:
    """Check if the font is a variable font."""
    try:
        from fontTools.ttLib import TTFont

        with TTFont(font_path) as font:
            return "fvar" in font
    except Exception as e:
        logger.warning(f"Failed to check if {font_path} is a variable font: {e}")
        return False


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


def all_relevant_files(fonts: Sequence[str]) -> List[str]:
    """Returns a list of all relevant files for the given fonts."""
    files = []
    relevant_globs = [
        "METADATA.pb",
        "OFL.txt",
        "LICENSE.txt",
        "DESCRIPTION.en_us.html",
        "article/*",
    ]

    for font in fonts:
        path = Path(font)
        files.append(str(path))
        for glob in relevant_globs:
            for file in path.parent.glob(glob):
                if str(file) not in files:
                    files.append(str(file))
    return files


class FontQA:
    def __init__(
        self,
        fonts: List[str],
        fonts_before: Optional[List[str]] = None,
        out="out",
        url=None,
    ):
        if fonts_before is None:
            fonts_before = []
        self.fonts = fonts
        self.fonts_before = fonts_before
        self.out = out
        self.url = url
        self.has_error = False

    @report_exceptions
    def diffenator3(self):
        logger.info("Running Diffenator3")
        if not self.fonts_before:
            logger.warning("Cannot run Diffenator since there are no fonts before")
            return
        assert len(self.fonts) >= len(self.fonts_before)
        for f, f_before in zip(
            sorted(self.fonts),
            sorted(self.fonts_before),
        ):
            cmd = [
                "diffenator3",
                "--html",
                "--instance",
                "*",
                "--output",
                os.path.join(self.out, "Diffenator"),
                f_before,
                f,
            ]
            process = subprocess.run(cmd, check=False)
            if process.returncode != 0:
                self.has_error = True
                return

    @report_exceptions
    def diffbrowsers(self):
        logger.info("Running Diffbrowsers")
        if not self.fonts_before:
            logger.warning("Cannot run diffbrowsers since there are no fonts before")
            return
        dst = os.path.join(self.out, "Diffbrowsers")
        mkdir(dst)
        assert len(self.fonts) >= len(self.fonts_before)
        for f, f_before in zip(
            sorted(self.fonts),
            sorted(self.fonts_before),
        ):
            cmd = [
                "diff3proof",
                "--output",
                dst,
                f_before,
                f,
            ]
            process = subprocess.run(cmd, check=False)
            if process.returncode != 0:
                self.has_error = True
            os.rename(
                os.path.join(dst, "diff3proof.html"),
                os.path.join(dst, f"diff3proof-{Path(f).stem}.html"),
            )
        return

    @report_exceptions
    def proof(self):
        logger.info("Running proofing tools")
        dst = os.path.join(self.out, "Proof")
        mkdir(dst)
        for font in self.fonts:
            cmd = [
                "diff3proof",
                "--output",
                dst,
                font,
            ]
            process = subprocess.run(cmd, check=False)
            os.rename(
                os.path.join(dst, "diff3proof.html"),
                os.path.join(dst, f"diff3proof-{Path(font).stem}.html"),
            )

            if process.returncode != 0:
                self.has_error = True
                return

    @report_exceptions
    def interpolations(self):
        dst = os.path.join(self.out, "Interpolations")
        if not any(is_variable(f) for f in self.fonts):
            return
        mkdir(dst)
        for font in self.fonts:
            font_dst = os.path.join(dst, f"{os.path.basename(font[:-4])}.pdf")
            if not is_variable(font):
                continue
            if has_interpolatable():
                cmd = ["interpolatable", font, "--pdf", font_dst]
            else:
                cmd = [
                    "fonttools",
                    "varLib.interpolatable",
                    self.fonts,
                    "--pdf",
                    font_dst,
                ]
            subprocess.call(cmd)

    @report_exceptions
    def fontbakery(self, profile="googlefonts", html=False, extra_args=None):
        logger.info("Running Fontbakery")
        out = os.path.join(self.out, "Fontbakery")
        mkdir(out)
        cmd = (
            ["fontbakery", "check-" + profile, "-l", "INFO", "--succinct"]
            + [f for f in self.fonts]
            + ["-C"]
            + ["--ghmarkdown", os.path.join(out, "report.md")]
            + ["-e", "FATAL"]
        )
        if html:
            cmd.extend(["--html", os.path.join(out, "report.html")])
        if extra_args:
            cmd.extend(extra_args)
        process = subprocess.run(cmd, check=False)

        fontbakery_report = os.path.join(self.out, "Fontbakery", "report.md")
        if not os.path.isfile(fontbakery_report):
            logger.warning(
                "Cannot Post Github message because no Fontbakery report exists"
            )
            return
        with open(fontbakery_report, encoding="utf8") as doc:
            msg = doc.read()
            self.post_to_github(msg)

        if process.returncode != 0:
            self.has_error = True

    @report_exceptions
    def fontspector(self, profile="googlefonts", html=False, extra_args=None):
        logger.info("Running Fontspector")
        out = os.path.join(self.out, "Fontspector")
        mkdir(out)
        cmd = (
            [
                "fontspector",
                "--profile",
                profile,
                "-l",
                "info",
                "--succinct",
                "-e",
                "error",
            ]
            + all_relevant_files(self.fonts)
            + ["--ghmarkdown", os.path.join(out, "report.md")]
        )
        if html:
            cmd.extend(["--html", os.path.join(out, "report.html")])
        if extra_args:
            cmd.extend(extra_args)
        process = subprocess.run(cmd, check=False)

        fontspector_report = os.path.join(self.out, "Fontspector", "report.md")
        if not os.path.isfile(fontspector_report):
            logger.warning(
                "Cannot Post Github message because no Fontspector report exists"
            )
            return
        with open(fontspector_report, encoding="utf8") as doc:
            msg = doc.read()
            self.post_to_github(msg)

        if process.returncode != 0:
            self.has_error = True

    def googlefonts_upgrade(self):
        self.fontspector()
        self.diffenator3()
        self.diffbrowsers()
        self.interpolations()

    def googlefonts_new(self):
        self.fontspector()
        self.diffenator3()
        self.proof()
        self.interpolations()

    def render(self):
        if self.fonts_before:
            self.diffbrowsers()
        else:
            self.proof()

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
            logger.warning(
                "Cannot post QA report!\n"
                "Most likely, the repository may lack a GH_TOKEN secret, or "
                "the pull request has come from a forked repo which "
                "is not allowed to access the repo's secrets for "
                f"security reasons. Full traceback:\n{e}"
            )
