"""
gftools html aka diffbrowsers2.

Generate html test pages for a family or test pages which compares two families.

Examples:
# Generate test pages for a single font
gftools html font1.ttf

# Generate test pages for a family of fonts
gftools html font1.ttf font2.ttf font3.ttf

# Output test pages to a dir
gftools html font1.ttf -o ~/Desktop/myFamily

# Generate test pages and output images using Browserstack
# (a subscription is required)
gftools html font1.ttf --imgs

# Generate diff comparison (font stylenames/fvar instance names must match!)
gftools html ./fonts_after/font1.ttf -fb ./fonts_before/font1.ttf
"""
from gftools.fix import font_familyname, font_stylename, WEIGHT_NAMES, get_name_record
from gftools.utils import font_sample_text
from fontTools.ttLib import TTFont
from jinja2 import Environment, PackageLoader, select_autoescape
from http.server import *
import pathlib
from glob import glob
import os
import threading
import sys
import argparse
import shutil


VIEWS = ["waterfall", "text"]


JINJA_ENV = Environment(
    loader=PackageLoader("gftools", "templates"),
    autoescape=select_autoescape(["html", "xml"]),
)


class CSSFontClass(object):

    def __init__(self, name, font_family=None, font_weight=None):
        self.name = name
        self.font_family = font_family
        self.font_weight = font_weight

    def render(self):
        return f"""
            .{self.name}{{
                font-family: {self.font_family};
                font-weight: {self.font_weight}
            }}
        """


class CSSFontFace(object):

    def __init__(self, path, family_name=None, font_weight=None, font_stretch=None):
        self.path = path
        self.family_name = family_name
        self.font_weight = font_weight
        self.font_stretch = font_stretch

    def render(self):
        string = f"""
            @font-face {{
                src: url({self.path});
                font-family: {self.family_name};
                font-weight: {self.font_weight};
        """
        if self.font_stretch:
            string += f"font-stretch: {self.font_stretch}"
            string += "}"
        return string


def create_simple_server(server_class=HTTPServer, handler_class=SimpleHTTPRequestHandler):
    server_address = ("", 8000)
    httpd = server_class(server_address, handler_class)
    httpd.serve_forever()


def start_daemon_server():
    th = threading.Thread(target=create_simple_server)
    th.daemon = True
    th.start()


class HtmlTestPageBuilder(object):

    def __init__(self, fonts, out="out"):
        self.fonts = fonts
        # Font used to generate sample text, glyphs all etc
        self.input_font = self.fonts[0]
        self.out = out

        self.css_font_faces = self.css_font_faces(fonts)
        self.css_font_classes = self.css_font_classes(fonts)

        self.views = []

    def css_font_faces(self, ttFonts, position=None):
        results = []
        for ttFont in ttFonts:
            family_name = font_familyname(ttFont)
            path = pathlib.Path(ttFont.reader.file.name)
            path = pathlib.Path(*path.parts[1:])
            if "fvar" in ttFont:
                fvar = ttFont["fvar"]
                axes = {a.axisTag: a for a in fvar.axes}
                family_name = family_name if not position else f"{family_name}-{position}"
                if "wght" in axes:
                    min_weight = int(axes["wght"].minValue)
                    max_weight = int(axes["wght"].maxValue)
                    font_weight = f"{min_weight} {max_weight}"
                if "wdth" in axes:
                    min_width = int(axes["wdth"].minValue)
                    max_width = int(axes["wdth"].maxValue)
                    font_stretch = f"{min_width}% {max_width}%"
            else:
                psname = get_name_record(ttFont, 6)
                family_name = psname if not position else f"{psname}-{position}"
                font_weight = ttFont["OS/2"].usWeightClass
                font_stretch = "100%"
            results.append(CSSFontFace(path, family_name, font_weight, font_stretch))
        return results

    def css_font_classes(self, ttFonts, position=None):
        results = []
        for ttFont in ttFonts:
            if "fvar" in ttFont:
                results += self._css_font_classes_from_instances(ttFont, position=position)
            else:
                psname = get_name_record(ttFont, 6)  # poscript name
                name = psname if not position else f"{psname}-{position}"
                font_family = name
                font_weight = ttFont["OS/2"].usWeightClass
                font_class = CSSFontClass(name, font_family, font_weight)
                results.append(font_class)
        return results

    def _css_font_classes_from_instances(self, ttFont, position=None):
        assert 'fvar' in ttFont
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
            font_class = CSSFontClass(name, font_family, font_weight)
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


class HtmlDiffPageBuilder(HtmlTestPageBuilder):

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
    fonts_after_dir = os.path.join(out, "fonts_after")
    fonts_before_dir = os.path.join(out, "fonts_before")
    for d in (out, fonts_after_dir, fonts_before_dir):
        os.mkdir(d)

    for f in fonts:
        shutil.copy(f, fonts_after_dir)
    for f in fonts_before:
        shutil.copy(f, fonts_before_dir)

    return (
        glob(os.path.join(fonts_before_dir, "*.ttf")),
        glob(os.path.join(fonts_after_dir, "*.ttf")),
        out,
    )


def gen_browserstack_gif(view_before, view_after):
    import subprocess

    url_before = f"http://0.0.0.0:8000/{view_before}"
    subprocess.call(["curl", url_before])


def gen_browsrstack_img(view):
    pass


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
        start_daemon_server()
        for view_before, view_after in html_builder.views:
            gen_browserstack_gif(view_before, view_after)


if __name__ == "__main__":
    main()
