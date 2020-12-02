"""
gftools html aka diffbrowsers2.

Produce html test pages which compare two families of fonts.

Optionally use diffbrowsers to produce gifs

Examples:
gftools html waterfall fonts_before fonts
gftools html glyphs fonts_before fonts
gftools html text fonts_before fonts
"""
from fontTools.ttLib import TTFont
from jinja2 import Environment, PackageLoader, select_autoescape
from http.server import *
import pathlib
from glob import glob
import os
import threading
import sys
import argparse
from gftools.fix import font_familyname, font_stylename, WEIGHT_NAMES
from gftools.utils import udhr_font_words
import shutil


VIEWS = ["waterfall", "text", "glyphs"]


env = Environment(
    loader=PackageLoader("gftools", "templates"),
    autoescape=select_autoescape(["html", "xml"]),
)


class CSSFontClass(object):
    def __init__(self, ttFont, class_name=None, font_name=None, font_weight=None):
        self.name = class_name or f"{font_name}{style_name}".replace(" ", "")
        self.font_name = font_name or font_familyname(ttFont)
        self.font_weight = font_weight or WEIGHT_NAMES[font_stylename(ttFont)]

    def render(self):
        return f"""
            .{self.name}{{
                font-family: {self.font_name};
                font-weight: {self.font_weight}
            }}
        """


class CSSFontFace(object):
    def __init__(self, ttFont, font_name=None, font_weight=None):
        stylename = font_stylename(ttFont)
        self.path = pathlib.Path(ttFont.reader.file.name)
        self.path = pathlib.Path(*self.path.parts[1:])
        self.font_name = font_name or font_familyname(ttFont)
        self.font_weight = font_weight or WEIGHT_NAMES[stylename]

    def render(self):
        return f"""
            @font-face {{
                src: url({self.path});
                font-family: {self.font_name};
                font-weight: {self.font_weight};
            }}
        """


def create_server(server_class=HTTPServer, handler_class=SimpleHTTPRequestHandler):
    server_address = ("", 8000)
    httpd = server_class(server_address, handler_class)
    httpd.serve_forever()


def start_daemon_server(loc):
    th = threading.Thread(target=create_server)
    th.daemon = True
    th.start()


class HtmlTestPageBuilder(object):

    def __init__(self, fonts, out="out"):
        self.fonts = fonts
        self.input_font = self.fonts[0]
        self.out = out

        self.css_font_faces = self._css_font_faces(fonts)
        self.css_font_classes = self._css_font_classes(fonts)

        self.views = []

    def _css_font_classes(self, ttFonts, position=None):
        results = []
        for ttFont in ttFonts:
            font_name = f"{font_familyname(ttFont)}-{font_stylename(ttFont)}".replace(
                " ", ""
            )
            if "fvar" in ttFont:
                raise NotImplementedError("TODO")
            else:
                class_name = font_name if not position else f"{font_name}-{position}"
                results.append(CSSFontClass(ttFont, class_name, class_name))
        return results

    def _css_font_faces(self, ttFonts, position=None):
        results = []
        for ttFont in ttFonts:
            font_name = f"{font_familyname(ttFont)}-{font_stylename(ttFont)}".replace(
                " ", ""
            )
            font_name = font_name if not position else f"{font_name}-{position}"
            results.append(CSSFontFace(ttFont, font_name))
        return results

    def build_page(self, view, pt_size):
        if view == "waterfall":
            page = self._render_html(
                "waterfall",
                "waterfall.html",
            )
        elif view == "text":
            sample_words = " ".join(udhr_font_words(self.input_font))
            sample_text = sample_words.lower() + " " + sample_words.upper()
            page = self._render_html(
                "text", "text.html", pt_size=pt_size, text=sample_text
            )
        else:
            raise NotImplementedError(f"'{view}' view not implemented")
        self.views.append(page)

    def _render_html(
        self,
        name,
        template,
        **kwargs,
    ):
        html_template = env.get_template(template)

        html = html_template.render(
            font_faces=self.css_font_faces,
            font_classes=self.css_font_classes,
            **kwargs,
        )
        page_filename = f"{name}.html"
        path = os.path.join(self.out, page_filename)
        with open(path, "w") as html_file:
            html_file.write(html)


class HtmlDiffPageBuilder(HtmlTestPageBuilder):

    def __init__(self, fonts_before, fonts_after, out):
        self.fonts_before = fonts_before
        self.css_font_faces_before = self._css_font_faces(fonts_before, "before")
        self.css_font_classes_before = self._css_font_classes(fonts_before, "before")

        self.fonts_after = fonts_after
        self.css_font_faces_after = self._css_font_faces(fonts_after, "after")
        self.css_font_classes_after = self._css_font_classes(fonts_after, "after")

        self.input_font = self.fonts_before[0]

        self.out = out
        self._match_css_font_classes()
        self.views = []

    def _match_css_font_classes(self):
        if not self.fonts_before:
            return
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
        html_template = env.get_template(template)

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

        return [before_path, after_path]


def _create_package(fonts, out="out"):
    if os.path.isdir(out):
        shutil.rmtree(out)
    fonts_dir = os.path.join(out, "fonts")
    for d in (out, fonts_dir):
        os.mkdir(d)
    for f in fonts:
        shutil.copy(f, fonts_dir)
    return (glob(os.path.join(fonts_dir, "*.ttf")), out)


def _create_diff_package(fonts, fonts_before, out="out"):
    if os.path.isdir(out):
        shutil.rmtree(out)
    fonts_dir = os.path.join(out, "fonts")
    fonts_before_dir = os.path.join(out, "fonts_before")
    for d in (out, fonts_dir, fonts_before_dir):
        os.mkdir(d)

    for f in fonts:
        shutil.copy(f, fonts_dir)
    for f in fonts_before:
        shutil.copy(f, fonts_before_dir)

    return (
        glob(os.path.join(fonts_before_dir, "*.ttf")),
        glob(os.path.join(fonts_dir, "*.ttf")),
        out,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("fonts", nargs="+")
    parser.add_argument("--fonts-before", "-fb", nargs="+")
    parser.add_argument("--views", nargs="+", choices=VIEWS, default=VIEWS)
    parser.add_argument("--pt-size", "-pt", help="pt size of text", default=14)
    parser.add_argument(
        "--imgs",
        action="store_true",
        help="Output images using Browserstack.",
    )
    parser.add_argument("--out", "-o", help="Output dir", default="diffbrowsers")
    args = parser.parse_args()

    if args.fonts_before:
        fonts_before, fonts_after, out = _create_diff_package(
            args.fonts_before, args.fonts, args.out
        )
        ttFonts_before = [TTFont(f) for f in fonts_before]
        ttFonts_after = [TTFont(f) for f in fonts_after]
        html_builder = HtmlDiffPageBuilder(ttFonts_before, ttFonts_after, out)
    else:
        fonts, out = _create_package(args.fonts, args.out)
        ttFonts = [TTFont(f) for f in fonts]
        html_builder = HtmlTestPageBuilder(ttFonts, out)

    for view in args.views:
        html_builder.build_page(view, args.pt_size)

    if args.imgs:
        start_daemon_server(args.out)
        for view_before, view_after in html_builder.views:
            gen_browserstack_gif(view_before, view_after)


def gen_browserstack_gif(view_before, view_after):
    import subprocess

    url_before = f"http://0.0.0.0:8000/{view_before}"
    subprocess.call(["curl", url_before])


def gen_browsrstack_img(view):
    pass


if __name__ == "__main__":
    main()
