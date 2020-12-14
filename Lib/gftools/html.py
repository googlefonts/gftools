from fontTools.ttLib import TTFont
import browserstack_screenshots
from pkg_resources import resource_filename
from jinja2 import Environment, FileSystemLoader, select_autoescape
import pathlib
from browserstack.local import Local
import tempfile
import sys
import os
import threading
from contextlib import contextmanager
import http.server
from http.server import *
import logging
import time
from copy import copy
import pathlib
import shutil
from gftools.utils import (
    font_sample_text,
    download_file,
    gen_gifs,
    font_familyname,
    font_stylename,
    get_name_record,
)


__all__ = [
    "CSSElement",
    "css_font_class_from_static",
    "css_font_classes_from_vf",
    "css_font_faces",
    "css_font_classes",
    "HtmlTemplater",
    "HtmlProof",
    "HtmlDiff",
    "simple_server",
    "start_daemon_server",
    "browserstack_local",
]


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


WIDTH_CLASS_TO_CSS = {
    1: "50%",
    2: "62.5%",
    3: "75%",
    4: "87.5%",
    5: "100%",
    6: "112.5%",
    7: "125%",
    8: "150%",
    9: "200%",
}


class CSSElement(object):
    """Create a CSSElement. CSSElements include a render method which
    renders the class as a string so it can be used in html templates.

    Args:
      selector: The css selector e.g h1, h2, class-name, @font0face
      **kwargs: css properties and their property values e.g
        font_family="MyFamily"

    Example:
      | >>> bold = CSSElement("bold", font_weight=700, font_style="normal")
      | >>> bold.render()
      | >>> 'bold { font-weight: 700; font-style: normal; }'
    """

    def __init__(self, selector, **kwargs):
        self.selector = selector
        for k, v in kwargs.items():
            setattr(self, k, v)
        self.declerations = {k.replace("_", "-"): v for k, v in kwargs.items()}

    def render(self):
        decleration_strings = " ".join(
            f"{k}: {v};" for k, v in self.declerations.items() if not k.startswith("-")
        )
        return f"{self.selector} {{ { decleration_strings } }}"


def css_font_faces(ttFonts, server_dir=None, position=None):
    """Generate @font-face CSSElements for a collection of fonts

    Args:
      ttFonts: a list containing ttFont instances
      server_dir: optional. A path to the root directory of the server.
        @font-face src urls are relative to the server's root dir.
      position: optional. Adds a suffix to the font-family name

    Returns:
      A list of @font-face CSSElements
    """
    results = []
    for ttFont in ttFonts:
        family_name = font_familyname(ttFont)
        style_name = font_stylename(ttFont)
        font_path = ttFont.reader.file.name
        path = (
            font_path
            if not server_dir
            else os.path.relpath(font_path, start=server_dir)
        )
        src = f"url({path})"
        font_family = _class_name(family_name, style_name, position)
        font_style = "italic" if "Italic" in style_name else "normal"
        font_stretch = WIDTH_CLASS_TO_CSS[ttFont["OS/2"].usWidthClass]

        if "fvar" in ttFont:
            fvar = ttFont["fvar"]
            axes = {a.axisTag: a for a in fvar.axes}
            if "wght" in axes:
                min_weight = int(axes["wght"].minValue)
                max_weight = int(axes["wght"].maxValue)
                font_weight = f"{min_weight} {max_weight}"
            if "wdth" in axes:
                min_width = int(axes["wdth"].minValue)
                max_width = int(axes["wdth"].maxValue)
                font_stretch = f"{min_width}% {max_width}%"
            if "ital" in axes:
                pass
            if "slnt" in axes:
                min_angle = int(axes["slnt"].minValue)
                max_angle = int(sex["slnt"].maxValue)
                font_style = f"oblique {min_angle}deg {max_angle}deg"
        else:
            font_weight = ttFont["OS/2"].usWeightClass
        font_face = CSSElement(
            "@font-face",
            src=src,
            font_family=font_family,
            font_weight=font_weight,
            font_stretch=font_stretch,
            font_style=font_style,
        )
        results.append(font_face)
    return results


def css_font_classes(ttFonts, position=None):
    """Generate class CSSElements for a collection of fonts

    Args:
      ttFonts: a list containing ttFont instances
      position: optional. Adds a suffix to the font-family name

    Returns:
      A list of class CSSElements
    """
    results = []
    for ttFont in ttFonts:
        if "fvar" in ttFont:
            results += css_font_classes_from_vf(ttFont, position)
        else:
            results.append(css_font_class_from_static(ttFont, position))
    return results


def _class_name(family_name, style_name, position=None):
    string = f"{family_name}-{style_name}".replace(" ", "-")
    return string if not position else f"{string}-{position}"


def css_font_class_from_static(ttFont, position=None):
    family_name = font_familyname(ttFont)
    style_name = font_stylename(ttFont)

    class_name = _class_name(family_name, style_name, position)
    font_family = class_name
    font_weight = ttFont["OS/2"].usWeightClass
    font_style = "normal" if "Italic" not in style_name else "italic"
    font_stretch = WIDTH_CLASS_TO_CSS[ttFont["OS/2"].usWidthClass]
    return CSSElement(
        class_name,
        _style=f"{family_name} {style_name}",
        font_family=font_family,
        font_weight=font_weight,
        font_style=font_style,
        font_stretch=font_stretch,
    )


def css_font_classes_from_vf(ttFont, position=None):
    instances = ttFont["fvar"].instances
    nametable = ttFont["name"]
    family_name = font_familyname(ttFont)
    style_name = font_stylename(ttFont)

    results = []
    for instance in instances:
        nameid = instance.subfamilyNameID
        inst_style = nametable.getName(nameid, 3, 1, 0x409).toUnicode()

        class_name = _class_name(family_name, inst_style, position)
        font_family = _class_name(family_name, style_name, position)
        font_weight = int(instance.coordinates["wght"])
        font_style = "italic" if "Italic" in inst_style else "normal"
        font_stretch = (
            "100%"
            if not "wdth" in instance.coordinates
            else f"{int(instance.coordinates['wdth'])}%"
        )
        font_class = CSSElement(
            class_name,
            _style=f"{family_name} {inst_style}",
            font_family=font_family,
            font_weight=font_weight,
            font_style=font_style,
            font_stretch=font_stretch,
        )
        results.append(font_class)
    return results


class HtmlTemplater(object):

    BROWSERSTACK_CONFIG = {
        "url": None,
        "local": True,
        "browsers": [
            {
                "os": "Windows",
                "browser_version": "71.0",
                "browser": "chrome",
                "os_version": "10",
            }
        ],
    }

    TEMPLATES = None

    def __init__(
        self,
        out="out",
        template_dir=resource_filename("gftools", "templates"),
        browserstack_username=None,
        browserstack_access_key=None,
        browserstack_config=None,
    ):
        """
        Generate html documents from Jinja2 templates and optionally
        screenshot the results on different browsers, using the
        Browserstack Screenshot api.

        When saving images, two brackground processes are started. A local
        server which serves the populated html documents
        and browserstack local. This allows Browserstack to take local
        screenshots.

        The main purpose of this class is to allow developers to
        write their own template generators by using inheritance e.g

        ```
        class MyTemplate(HtmlTemplater):
            def __init__(self, forename, surname, out):
                super().__init__(self, out)
                self.forename = forename
                self.surname = surname

        html = MyTemplate("Joe", "Doe")
        html.build_pages()
        ```

        template:
        <p>Hello {{ forename }} {{ surname }}.</p>

        result:
        <p>Hello Joe Doe.</p>

        For more complex examples, see HtmlProof and HtmlDiff in this
        module.

        All html docs and assets are saved into the specified out
        directory. Packaging the assets together makes it easier to share
        and we don't have to worry about absolute vs relative paths. This
        can be problematic for some assets such as webfonts where the path
        must be related to the local server, not the user's system.

        Args:
          out: output dir for generated html documents
          template_dir: the directory containing the html templates
          browserstack_username: optional. Browserstack username
          browserstack_access_key: optional. Browserstack access key
          browserstack_config: optional. Browserstack config file. See
            api docs for more info:
            https://www.browserstack.com/screenshots/api
        """
        self.template_dir = template_dir
        self.templates = []
        # TODO we may want to make this an arg
        self.server_url = "http://0.0.0.0:8000"
        self.jinja = Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=select_autoescape(["html", "xml"]),
        )

        self.out = self.mkdir(out)
        self.documents = {}

        self.has_browserstack = (
            True
            if any([browserstack_access_key, "BSTACK_ACCESS_KEY" in os.environ])
            else False
        )

        if self.has_browserstack:
            auth = (
                browserstack_username or os.environ["BSTACK_USERNAME"],
                browserstack_access_key or os.environ["BSTACK_ACCESS_KEY"],
            )
            self.browserstack_config = (
                browserstack_config if browserstack_config else self.BROWSERSTACK_CONFIG
            )
            self.screenshot = ScreenShot(auth=auth, config=self.browserstack_config)
        else:
            logger.warning("No Browserstack credentials found. Image output disabled")

    def build_pages(self, pages=None, dst=None, **kwargs):
        if not pages:
            if not self.TEMPLATES:
                raise ValueError("No templates specified")
            pages = self.TEMPLATES
        for page in pages:
            self.build_page(page, dst=dst, **kwargs)

    def build_page(self, filename, dst=None, **kwargs):
        if filename not in os.listdir(self.template_dir):
            raise ValueError(f"'{filename}' not in dir '{self.template_dir}'")
        # Combine self.__dict__ attributes with function kwargs. This allows Jinja
        # templates to access the class attributes
        jinja_kwargs = {**self.__dict__, **kwargs}
        page = self._render_html(filename, dst=dst, **jinja_kwargs)
        self.documents[filename] = page

    def _render_html(self, filename, dst=None, **kwargs):
        html_template = self.jinja.get_template(filename)
        html = html_template.render(**kwargs)
        dst = dst if dst else os.path.join(self.out, filename)
        with open(dst, "w") as html_file:
            html_file.write(html)
        return dst

    def mkdir(self, path):
        if not os.path.isdir(path):
            os.mkdir(path)
        return path

    def copy_files(self, srcs, dst):
        [shutil.copy(f, dst) for f in srcs]
        return [os.path.join(dst, os.path.basename(f)) for f in srcs]

    def save_imgs(self):
        assert hasattr(self, "screenshot")
        img_dir = self.mkdir(os.path.join(self.out, "img"))

        start_daemon_server(directory=self.out)
        with browserstack_local():
            for name, paths in self.documents.items():
                out = os.path.join(img_dir, name)
                self.mkdir(out)
                self._save_img(paths, out)

    def _save_img(self, path, dst):
        page = os.path.relpath(path, start=self.out)
        url = f"{self.server_url}/{page}"
        self.screenshot.take(url, dst)


GF_TEMPLATES = ["waterfall.html", "text.html"]


class HtmlProof(HtmlTemplater):

    TEMPLATES = GF_TEMPLATES

    def __init__(self, fonts, out="out"):
        """Proof a single family."""
        super().__init__(out)
        fonts_dir = os.path.join(out, "fonts")
        self.mkdir(fonts_dir)

        self.fonts = self.copy_files(fonts, fonts_dir)
        self.ttFonts = [TTFont(f) for f in self.fonts]

        self.css_font_faces = css_font_faces(self.ttFonts, self.out)
        self.css_font_classes = css_font_classes(self.ttFonts)

        self.sample_text = " ".join(font_sample_text(self.ttFonts[0]))


class HtmlDiff(HtmlTemplater):

    TEMPLATES = GF_TEMPLATES

    def __init__(self, fonts_before, fonts_after, out="out"):
        """Compare two families"""
        super().__init__(out=out)
        fonts_before_dir = os.path.join(out, "fonts_before")
        fonts_after_dir = os.path.join(out, "fonts_after")
        self.mkdir(fonts_before_dir)
        self.mkdir(fonts_after_dir)

        self.fonts_before = self.copy_files(fonts_before, fonts_before_dir)
        self.ttFonts_before = [TTFont(f) for f in self.fonts_before]

        self.fonts_after = self.copy_files(fonts_after, fonts_after_dir)
        self.ttFonts_after = [TTFont(f) for f in self.fonts_after]

        self.css_font_faces_before = css_font_faces(
            self.ttFonts_before, self.out, position="before"
        )
        self.css_font_faces_after = css_font_faces(
            self.ttFonts_after, self.out, position="after"
        )

        self.css_font_classes_before = css_font_classes(self.ttFonts_before, "before")
        self.css_font_classes_after = css_font_classes(self.ttFonts_after, "after")
        self._match_css_font_classes()

        self.sample_text = " ".join(font_sample_text(self.ttFonts_before[0]))

    def _match_css_font_classes(self):
        """Match css font classes by full names for static fonts and
        family name + instance name for fvar instances"""
        styles_before = {s._style: s for s in self.css_font_classes_before}
        styles_after = {s._style: s for s in self.css_font_classes_after}
        shared_styles = set(styles_before) & set(styles_after)

        self.css_font_classes_before = sorted(
            [s for k, s in styles_before.items() if k in shared_styles],
            key=lambda s: (s.font_weight, s._style),
        )
        self.css_font_classes_after = sorted(
            [s for k, s in styles_after.items() if k in shared_styles],
            key=lambda s: (s.font_weight, s._style),
        )
        if not all([self.css_font_classes_before, self.css_font_classes_after]):
            raise ValueError("No matching fonts found")

    def _render_html(
        self,
        filename,
        **kwargs,
    ):
        html_template = self.jinja.get_template(filename)

        # This document is intended for humans. It includes a button
        # to toggle which set of fonts is visible.
        combined = html_template.render(include_ui=True, **kwargs)
        combined_path = os.path.join(self.out, filename)
        with open(combined_path, "w") as combined_html:
            combined_html.write(combined)

        # This document contains fonts_before. It solely exists for
        # screenshot generation purposes
        before_kwargs = copy(kwargs)
        before_kwargs.pop("css_font_classes_after")
        before = html_template.render(**before_kwargs)
        before_filename = f"{filename[:-5]}-before.html"
        before_path = os.path.join(self.out, before_filename)
        with open(before_path, "w") as before_html:
            before_html.write(before)

        # This document contains fonts_after. It solely exists for
        # screenshot generation purposes
        after_kwargs = copy(kwargs)
        after_kwargs.pop("css_font_classes_before")
        after = html_template.render(**after_kwargs)
        after_filename = f"{filename[:-5]}-after.html"
        after_path = os.path.join(self.out, after_filename)
        with open(after_path, "w") as after_html:
            after_html.write(after)

        return (before_path, after_path)

    def _save_img(self, document, dst):
        # Output results as a gif
        before_page = os.path.relpath(document[0], start=self.out)
        after_page = os.path.relpath(document[1], start=self.out)
        before_url = f"{self.server_url}/{before_page}"
        after_url = f"{self.server_url}/{after_page}"
        with tempfile.TemporaryDirectory() as before_dst, tempfile.TemporaryDirectory() as after_dst:
            self.screenshot.take(before_url, before_dst)
            self.screenshot.take(after_url, after_dst)
            gen_gifs(before_dst, after_dst, dst)


def simple_server(directory="."):
    """A simple python web server which can be served from a specific
    directory

    Args:
      directory: start the server from a specified directory. Default is '.'
    """

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=directory, **kwargs)

    server_address = ("", 8000)
    httpd = HTTPServer(server_address, Handler)
    httpd.serve_forever()


def start_daemon_server(directory="."):
    """Start a simple_server in a new background thread.
    Server will be stopped once a script has finished.

    Args:
      directory: start the server from a specified directory. Default is '.'
    """
    th = threading.Thread(target=simple_server, args=[directory])
    th.daemon = True
    th.start()


@contextmanager
def browserstack_local():
    """Start browserstack local tool as a background process"""
    # TODO This can be deprecated once
    # https://github.com/browserstack/browserstack-local-python/pull/28 is
    # merged (it may not be merged because it's a relatively inactive repo)
    local = Local(key=os.environ["BSTACK_ACCESS_KEY"])
    try:
        local.start()
        yield local
    finally:
        local.stop()


class ScreenShot(browserstack_screenshots.Screenshots):
    """Expansion for browserstack screenshots Lib. Adds ability to
    download files."""

    # TODO it may be better to write our own wrapper
    # since this tool isn't being developed. Code migrated from
    # https://github.com/googlefonts/diffbrowsers

    def take(self, url, dst_dir):
        """take a screenshot from a url and save it to the dst_dir"""
        self.config["url"] = url
        logger.info("Taking screenshot for url: %s" % url)
        generate_resp_json = self.generate_screenshots()
        job_id = generate_resp_json["job_id"]

        logger.info(
            "Browserstack is processing: "
            "http://www.browserstack.com/screenshots/%s" % job_id
        )
        screenshots_json = self.get_screenshots(job_id)
        while screenshots_json == False:  # keep refreshing until browerstack is done
            time.sleep(3)
            screenshots_json = self.get_screenshots(job_id)
        for screenshot in screenshots_json["screenshots"]:
            filename = self._build_filename_from_browserstack_json(screenshot)
            base_image = os.path.join(dst_dir, filename)
            try:
                download_file(screenshot["image_url"], base_image)
            except:
                logger.info(
                    "Skipping {} BrowserStack timed out".format(screenshot["image_url"])
                )

    def _build_filename_from_browserstack_json(self, j):
        """Build useful filename for an image from the screenshot json
        metadata"""
        filename = ""
        device = j["device"] if j["device"] else "Desktop"
        if j["state"] == "done" and j["image_url"]:
            detail = [
                device,
                j["os"],
                j["os_version"],
                j["browser"],
                j["browser_version"],
                ".png",
            ]
            filename = "_".join(item.replace(" ", "_") for item in detail if item)
        else:
            logger.info("screenshot timed out, ignoring this result")
        return filename
