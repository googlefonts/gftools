"""
gftools html aka diffbrowsers2.

Produce html test pages which compare two families of fonts.

Optionally use diffbrowsers to produce gifs

Examples:
gftools html waterfall fonts_before fonts_after
gftools html glyphs fonts_before fonts_after
gftools html text fonts_before fonts_after
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


def css_family_classes(ttFonts, position):
    results = []
    for ttFont in ttFonts:
        font_name = font_familyname(ttFont)
        if "fvar" in ttFont:
            raise NotImplementedError("TODO")
        else:
            class_name = f"{font_name}-{position}"
            results.append(CSSFontClass(ttFont, class_name, class_name))
    return results


def css_family_font_faces(ttFonts, position):
    results = []
    for ttFont in ttFonts:
        font_name = font_familyname(ttFont)
        font_name = f"{font_name}-{position}"
        results.append(CSSFontFace(ttFont, font_name))
    return results


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


def start_server(loc):
    th = threading.Thread(target=create_server)
    th.daemon = True
    th.start()


def _render_view(
    template,
    font_faces_before,
    font_faces_after,
    styles_before,
    styles_after,
    out,
    **kwargs,
):
    html_template = env.get_template(template)

    before = html_template.render(
        css_family_font_faces=font_faces_before,
        css_family_classes=styles_before,
        **kwargs,
    )

    after = html_template.render(
        css_family_font_faces=font_faces_after,
        css_family_classes=styles_after,
        **kwargs,
    )
    before_filename = f"{template[:-5]}-before.html"
    before_path = os.path.join(out, before_filename)
    with open(before_path, "w") as before_html:
        before_html.write(before)

    after_filename = f"{template[:-5]}-after.html"
    after_path = os.path.join(out, after_filename)
    with open(after_path, "w") as after_html:
        after_html.write(after)

    return [before_path, after_path]


def _create_package(fonts_before, fonts_after, out):
    if os.path.isdir(out):
        shutil.rmtree(out)
    fonts_before_dir = os.path.join(out, "fonts_before")
    fonts_after_dir = os.path.join(out, "fonts_after")
    for d in (out, fonts_before_dir, fonts_after_dir):
        os.mkdir(d)
    # Copy source fonts into package
    for f in fonts_before:
        shutil.copy(f, fonts_before_dir)
    for f in fonts_after:
        shutil.copy(f, fonts_after_dir)

    return [
        glob(os.path.join(fonts_before_dir, "*.ttf")),
        glob(os.path.join(fonts_after_dir, "*.ttf")),
        out
    ]


def gen_html(fonts_before, fonts_after, out="diffbrowsers"):
    # Assemble dirs and copy fonts
    fonts_before, fonts_after, out = _create_package(fonts_before, fonts_after, out)

    fonts_before = [TTFont(f) for f in fonts_before]
    fonts_after = [TTFont(f) for f in fonts_after]

    font_faces_before = css_family_font_faces(fonts_before, "before")
    font_faces_after = css_family_font_faces(fonts_after, "after")

    styles_before = css_family_classes(fonts_before, "before")
    styles_after = css_family_classes(fonts_after, "after")

    waterfall = _render_view(
        "waterfall.html",
        font_faces_before,
        font_faces_after,
        styles_before,
        styles_after,
        out,
    )

    text = _render_view(
        "text.html",
        font_faces_before,
        font_faces_after,
        styles_before,
        styles_after,
        out,
        pt_size="24",
        text="This will be the text from the UDHR"
    )
    return waterfall


def gen_gif(view):
    pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fonts-before", "-fb", nargs="+", required=True)
    parser.add_argument("--fonts-after", "-fa", nargs="+", required=True)
    parser.add_argument("--views", nargs="+", choices=VIEWS, default=VIEWS)
    parser.add_argument("--pt-size", "-pt", help="pt size of text", default=16)
    parser.add_argument(
        "--gifs", action='store_true', help="Output before and after gifs using Browserstack"
    )
    parser.add_argument("--out", "-o", help="Output dir", default="diffbrowsers")
    args = parser.parse_args()

    html_docs = gen_html(args.fonts_before, args.fonts_after, args.out)
#    html_docs = HtmlTestPageBuilder(args.fonts_before, args.fonts_after, args.out)
#    for view in args.views:
#        html_docs.gen_pages(view, args.pt_size)

#    if args.gifs:
#        start_simple_server(args.out)
#        for view in html_docs.views:
#            gen_gif(view)


if __name__ == "__main__":
    main()
