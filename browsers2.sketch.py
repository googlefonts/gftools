"""
gftools html aka diffbrowser's successor.

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
import threading
import sys
from gftools.fix import font_familyname, font_stylename, WEIGHT_NAMES


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
        self.path = ttFont.reader.file.name
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


def render_view(
    template, font_faces_before, font_faces_after, styles_before, styles_after, **kwargs
):
    """
    """
    template = env.get_template(template)

    before = template.render(font_faces_before, styles_before, **kwargs)
    after = template.render(font_faces_after, styles_after, **kwargs)


def create_server(server_class=HTTPServer, handler_class=BaseHTTPRequestHandler):
    server_address = ('', 8000)
    httpd = server_class(server_address, handler_class)
    httpd.serve_forever()


def start_server():
    th=threading.Thread(target=create_server)
    th.daemon = True
    th.start()


def main():
    fonts_before = [TTFont(f) for f in args.fonts_before]
    fonts_after = [TTFont(f) for f in args.fonts_after]
    views = args.views

    gen_html(fonts_before, fonts_after, views, args.out)

    if args.run_browserstack:
        start_server()



def gen_html(fonts_before, fonts_after, views=["waterfall", "text", "glyphs"], out="out"):
    font_faces_before = css_family_font_faces(ttFonts_before, "before")
    font_faces_after = css_family_font_faces(ttFonts_after, "after")

    styles_before = css_family_classes(ttFonts_before, "before")
    styles_after = css_family_classes(ttFonts_after, "after")

    shared_styles = styles_before & styles_after & filter_syles


    if "waterfall" in views:
        render_view(
            "waterfall.html",
            font_faces_before,
            font_face_after,
            styles_before,
            styles_after,
            text="This is the sample text.",
        )
    if "text" in views:
        text = udhr_words_in_fonts(args.font_before[0])
        render_view(
            "text.html",
            font_faces_before,
            font_face_after,
            styles_before,
            styles_after,
            text=text,
        )
    if "glyphs" in views:
        glyphs = glyphs_in_fonts(fonts_before)
        render_view(
            "glyphs.html",
            font_faces_before,
            font_face_after,
            styles_before,
            styles_after,
            glyphs=glyphs,
        )

    sys.exit()


if __name__ == "__main__":
    import threading
    th=threading.Thread(target=create_server)
    th.daemon = True
    th.start()
    template = env.get_template("test.html")
    before = template.render(name="Matthew")
    print(before)
    after = template.render(name="John")
    print(after)
    font1 = TTFont('/Users/marcfoley/Type/upstream_families/Roboto/fonts/web/static/Roboto-Regular.ttf')
    font2 = TTFont('/Users/marcfoley/Type/upstream_families/Roboto/fonts/web/static/Roboto-Regular.ttf')
    fonts = [font1, font2]
    cs = css_family_classes(fonts, "before")
    cd = css_family_font_faces(fonts, "before")
    for i in cd:
        print(i.render())
    sys.exit()
