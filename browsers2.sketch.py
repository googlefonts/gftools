"""
gftools gen-html aka diffbrowsers2.

Generate html proofing pages for a family or diff pages which compares
two families.

Examples:
# Generate test pages for a single font
gftools gen-html proof font1.ttf

# Generate test pages for a family of fonts
gftools gen-html proof font1.ttf font2.ttf font3.ttf

# Output test pages to a dir
gftools gen-html proof font1.ttf -o ~/Desktop/myFamily

# Generate test pages and output images using Browserstack
# (a subscription is required)
gftools gen-html proof font1.ttf --imgs

# Generate diff comparison (font stylenames/fvar instance names must match!)
gftools gen-html diff ./fonts_after/font1.ttf -fb ./fonts_before/font1.ttf
"""
from gftools.fix import font_familyname, font_stylename, WEIGHT_NAMES, get_name_record
from gftools.utils import (
    font_sample_text,
    start_daemon_server,
    browserstack_local,
    gen_gifs,
)
from diffbrowsers.screenshot import ScreenShot
from fontTools.ttLib import TTFont
from jinja2 import Environment, PackageLoader, select_autoescape
import pathlib
from glob import glob
import os
import sys
import argparse
import shutil
from browserstack.local import Local
import tempfile


JINJA_ENV = Environment(
    loader=PackageLoader("gftools", "templates"),
    autoescape=select_autoescape(["html", "xml"]),
)


class CSSElement(object):
    def __init__(self, selector, **kwargs):
        self.selector = selector
        for k, v in kwargs.items():
            setattr(self, k, v)
        self.declerations = {k.replace("_", "-"): v for k, v in kwargs.items()}

    def render(self):
        decleration_strings = "\n".join(
            f"{k}: {v};" for k, v in self.declerations.items()
        )
        return f"{self.selector} {{ { decleration_strings } }}"


class HtmlProof(object):

    VIEWS = frozenset(["waterfall", "text"])

    def __init__(self, fonts, out="out"):
        self.fonts = fonts
        # Font used to generate sample text, glyphs all etc
        self.input_font = self.fonts[0]
        self.out = out

        self.css_font_faces = self.css_font_faces(fonts)
        self.css_font_classes = self.css_font_classes(fonts)

        self.views = {}

    def css_font_faces(self, ttFonts, position=None):
        results = []
        for ttFont in ttFonts:
            family_name = font_familyname(ttFont)
            style_name = font_stylename(ttFont)
            path = pathlib.Path(ttFont.reader.file.name)
            path = pathlib.Path(*path.parts[1:])
            src = f"url({path})"

            if "fvar" in ttFont:
                fvar = ttFont["fvar"]
                axes = {a.axisTag: a for a in fvar.axes}
                font_family = (
                    family_name if not position else f"{family_name}-{position}"
                )
                if "wght" in axes:
                    min_weight = int(axes["wght"].minValue)
                    max_weight = int(axes["wght"].maxValue)
                    font_weight = f"{min_weight} {max_weight}"
                if "wdth" in axes:
                    min_width = int(axes["wdth"].minValue)
                    max_width = int(axes["wdth"].maxValue)
                # TODO ital, slnt, stretch
            else:
                psname = get_name_record(ttFont, 6)
                font_family = psname if not position else f"{psname}-{position}"
                font_weight = ttFont["OS/2"].usWeightClass
            font_style = "italic" if "Italic" in style_name else "normal"
            font_face = CSSElement(
                "@font-face",
                src=src,
                font_family=font_family,
                font_weight=font_weight,
                font_style=font_style,
            )
            results.append(font_face)
        return results

    def css_font_classes(self, ttFonts, position=None):
        results = []
        for ttFont in ttFonts:
            if "fvar" in ttFont:
                results += self._css_font_classes_from_vf(ttFont, position=position)
            else:
                psname = get_name_record(ttFont, 6)  # poscript name
                name = psname if not position else f"{psname}-{position}"
                font_family = name
                font_weight = ttFont["OS/2"].usWeightClass
                font_style = "italic" if "Italic" in psname else "normal"
                font_class = CSSElement(
                    name,
                    font_family=font_family,
                    font_weight=font_weight,
                    font_style=font_style,
                )
                results.append(font_class)
        return results

    def _css_font_classes_from_vf(self, ttFont, position=None):
        assert "fvar" in ttFont
        instances = ttFont["fvar"].instances
        nametable = ttFont["name"]
        family_name = font_familyname(ttFont)
        results = []
        for instance in instances:
            nameid = instance.subfamilyNameID
            inst_style = nametable.getName(nameid, 3, 1, 0x409).toUnicode()

            name = f"{family_name}-{inst_style}".replace(" ", "")
            name = name if not position else f"{name}-{position}"
            font_weight = instance.coordinates["wght"]
            font_family = family_name if not position else f"{family_name}-{position}"
            font_style = "italic" if "Italic" in inst_style else "normal"
            font_class = CSSElement(
                name,
                font_family=font_family,
                font_weight=font_weight,
                font_style=font_style,
            )
            results.append(font_class)
        return results

    def build_page(self, view, pt_size):
        if view == "waterfall":
            page = self._render_html(
                "waterfall",
                "waterfall.html",
            )
        elif view == "text":
            sample_words = " ".join(font_sample_text(self.input_font))
            sample_text = f"{sample_words.lower()} {sample_words.upper()}"
            page = self._render_html(
                "text", "text.html", pt_size=pt_size, text=sample_text
            )
        else:
            raise NotImplementedError(f"'{view}' view not implemented")
        self.views[view] = page

    def _render_html(
        self,
        name,
        template,
        **kwargs,
    ):
        html_template = JINJA_ENV.get_template(template)

        html = html_template.render(
            font_faces=self.css_font_faces,
            font_classes=self.css_font_classes,
            **kwargs,
        )
        page_filename = f"{name}.html"
        path = os.path.join(self.out, page_filename)
        with open(path, "w") as html_file:
            html_file.write(html)
        return (path,)

    def _mkdir(self, path):
        if not os.path.isdir(path):
            os.mkdir(path)
        return path

    def save_imgs(self):
        img_dir = self._mkdir(os.path.join(self.out, "img"))

        start_daemon_server()
        with browserstack_local():
            for view in self.views:
                dst = self._mkdir(os.path.join(img_dir, view))
                self.save_img(view, dst)

    def save_img(self, view, dst):
        # Don't use os.path on this since urls are always forward slashed
        url = f"http://0.0.0.0:8000/{self.views[view][0]}"
        auth = (os.environ["BSTACK_USERNAME"], os.environ["BSTACK_ACCESS_KEY"])
        config = ScreenShot.DEFAULT_CONFIG
        config["local"] = True
        screenshot = ScreenShot(auth=auth, config=config)
        screenshot.take(url, dst)


class HtmlDiff(HtmlProof):
    def __init__(self, fonts_before, fonts_after, out):
        self.fonts_before = fonts_before
        self.fonts_after = fonts_after
        # Font used to generate sample text, glyphs all etc
        self.input_font = self.fonts_before[0]

        self.css_font_faces_before = self.css_font_faces(fonts_before, "before")
        self.css_font_faces_after = self.css_font_faces(fonts_after, "after")

        self.css_font_classes_before = self.css_font_classes(fonts_before, "before")
        self.css_font_classes_after = self.css_font_classes(fonts_after, "after")

        self.out = out
        self._match_css_font_classes()
        self.views = {}

    def _match_css_font_classes(self):
        if not self.fonts_before:
            return
        # TODO drop weight, use stylename
        styles_after = set(s.font_weight for s in self.css_font_classes_after)
        styles_before = set(s.font_weight for s in self.css_font_classes_before)
        shared_styles = styles_before & styles_after

        self.css_font_classes_before = sorted(
            [s for s in self.css_font_classes_before if s.font_weight in shared_styles],
            key=lambda k: k.font_weight,
        )
        self.css_font_classes_after = sorted(
            [s for s in self.css_font_classes_after if s.font_weight in shared_styles],
            key=lambda k: k.font_weight,
        )

        if not all([self.css_font_classes_before, self.css_font_classes_after]):
            raise ValueError("No matching fonts found")

    def _render_html(
        self,
        name,
        template,
        **kwargs,
    ):
        html_template = JINJA_ENV.get_template(template)

        before = html_template.render(
            font_faces=self.css_font_faces_before,
            font_classes=self.css_font_classes_before,
            **kwargs,
        )
        before_filename = f"{name}-before.html"
        before_path = os.path.join(self.out, before_filename)
        with open(before_path, "w") as before_html:
            before_html.write(before)

        after = html_template.render(
            font_faces=self.css_font_faces_after,
            font_classes=self.css_font_classes_after,
            **kwargs,
        )
        after_filename = f"{name}-after.html"
        after_path = os.path.join(self.out, after_filename)
        with open(after_path, "w") as after_html:
            after_html.write(after)

        combined = html_template.render(
            font_faces_before=self.css_font_faces_before,
            font_faces=self.css_font_faces_after,
            font_classes_before=self.css_font_classes_before,
            font_classes=self.css_font_classes_after,
            include_ui=True,
            **kwargs,
        )
        combined_filename = f"{name}.html"
        combined_path = os.path.join(self.out, combined_filename)
        with open(combined_path, "w") as combined_html:
            combined_html.write(combined)
        return (before_path, after_path)

    def save_img(self, view, dst):
        before_url = f"http://0.0.0.0:8000/{self.views[view][0]}"
        after_url = f"http://0.0.0.0:8000/{self.views[view][1]}"
        auth = (os.environ["BSTACK_USERNAME"], os.environ["BSTACK_ACCESS_KEY"])
        config = ScreenShot.DEFAULT_CONFIG
        config["browsers"] = [
            {
                "os": "Windows",
                "os_version": "10",
                "browser": "chrome",
                "device": None,
                "browser_version": "71.0",
                "real_mobile": None,
            }
        ]
        config["local"] = True
        screenshot = ScreenShot(auth=auth, config=config)
        with tempfile.TemporaryDirectory() as before_dst, tempfile.TemporaryDirectory() as after_dst:
            screenshot.take(before_url, before_dst)
            screenshot.take(after_url, after_dst)
            gen_gifs(before_dst, after_dst, dst)


def create_package(fonts, out="out"):
    if os.path.isdir(out):
        shutil.rmtree(out)

    fonts_dir = os.path.join(out, "fonts")

    [os.mkdir(d) for d in (out, fonts_dir)]
    [shutil.copy(f, fonts_dir) for f in fonts]

    return (glob(os.path.join(fonts_dir, "*.ttf")), out)


def create_diff_package(fonts_before, fonts_after, out="out"):
    if os.path.isdir(out):
        shutil.rmtree(out)

    fonts_before_dir = os.path.join(out, "fonts_before")
    fonts_after_dir = os.path.join(out, "fonts_after")

    [os.mkdir(d) for d in (out, fonts_after_dir, fonts_before_dir)]
    [shutil.copy(f, fonts_before_dir) for f in fonts_before]
    [shutil.copy(f, fonts_after_dir) for f in fonts_after]

    return (
        glob(os.path.join(fonts_before_dir, "*.ttf")),
        glob(os.path.join(fonts_after_dir, "*.ttf")),
        out,
    )


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(
        dest="command", required=True, metavar='"proof" or "diff"'
    )

    # Optional args which can be used in all subparsers
    universal_options_parser = argparse.ArgumentParser(add_help=False)
    universal_options_parser.add_argument(
        "--views",
        nargs="+",
        choices=HtmlProof.VIEWS,
        default=HtmlProof.VIEWS,
    )
    universal_options_parser.add_argument(
        "--pt-size", "-pt", help="pt size of text", default=14
    )
    universal_options_parser.add_argument(
        "--imgs",
        action="store_true",
        help="Output images using Browserstack.",
    )
    universal_options_parser.add_argument(
        "--out", "-o", help="Output dir", default="diffbrowsers"
    )

    proof_parser = subparsers.add_parser(
        "proof",
        parents=[universal_options_parser],
        help="produce html proofing pages for a single set of fonts",
    )
    proof_parser.add_argument("fonts", nargs="+")

    diff_parser = subparsers.add_parser(
        "diff",
        parents=[universal_options_parser],
        help="produce html diff pages which compare two sets of fonts. "
        "Fonts are matched by style name or instance style name",
    )
    diff_parser.add_argument("--fonts-before", "-fa", nargs="+", required=True)
    diff_parser.add_argument("--fonts-after", "-fb", nargs="+", required=True)

    args = parser.parse_args()

    if args.command == "proof":
        fonts, out = create_package(args.fonts, args.out)
        ttFonts = [TTFont(f) for f in fonts]
        html = HtmlProof(ttFonts, out)

    elif args.command == "diff":
        fonts_before, fonts_after, out = create_diff_package(
            args.fonts_before, args.fonts_after, args.out
        )
        ttFonts_before = [TTFont(f) for f in fonts_before]
        ttFonts_after = [TTFont(f) for f in fonts_after]
        html = HtmlDiff(ttFonts_before, ttFonts_after, out)

    for view in args.views:
        html.build_page(view, args.pt_size)

    if args.imgs:
        html.save_imgs()


if __name__ == "__main__":
    main()
