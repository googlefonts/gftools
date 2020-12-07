from gftools.fix import font_familyname, font_stylename, WEIGHT_NAMES, get_name_record
from gftools.utils import font_sample_text, download_file, gen_gifs
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
from http.server import *
import logging
import time
from copy import copy


__all__ = [
    "CSSElement",
    "css_font_faces",
    "css_font_classes",
    "HtmlProof",
    "HtmlDiff",
    "simple_server",
    "start_daemon_server",
    "browserstack_local",
]


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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


def css_font_faces(ttFonts, server_dir=None, position=None):
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

        if "fvar" in ttFont:
            fvar = ttFont["fvar"]
            axes = {a.axisTag: a for a in fvar.axes}
            font_family = family_name if not position else f"{family_name}-{position}"
            if "wght" in axes:
                min_weight = int(axes["wght"].minValue)
                max_weight = int(axes["wght"].maxValue)
                font_weight = f"{min_weight} {max_weight}"
            if "wdth" in axes:
                min_width = int(axes["wdth"].minValue)
                max_width = int(axes["wdth"].maxValue)
        #                    font_stretch = f"{min_width}% {max_width}%"
        # TODO ital, slnt
        else:
            psname = get_name_record(ttFont, 6)
            font_family = psname if not position else f"{psname}-{position}"
            font_weight = ttFont["OS/2"].usWeightClass
        #               font_stretch = "100%"
        font_style = "italic" if "Italic" in style_name else "normal"
        font_face = CSSElement(
            "@font-face",
            src=src,
            font_family=font_family,
            font_weight=font_weight,
            #              font_stretch=font_stretch,
            font_style=font_style,
        )
        results.append(font_face)
    return results


def css_font_classes(ttFonts, position=None):
    results = []
    for ttFont in ttFonts:
        if "fvar" in ttFont:
            results += _css_font_classes_from_vf(ttFont, position=position)
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


def _css_font_classes_from_vf(ttFont, position=None):
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


class HtmlTemplater(object):

    BROWSERSTACK_CONFIG = {
	"url":"http://www.google.com",
        "local": True,
	"browsers":[
	  {
		"os":"Windows",
		"browser_version":"8.0",
		"browser":"ie",
		"os_version":"7"
	  }
	]
    }

    def __init__(
        self,
        out="out",
        browserstack_username=None,
        browserstack_access_key=None,
        template_dir=resource_filename("gftools", "templates"),
        browserstack_config=None,
    ):
        self.template_dir = template_dir
        self.jinja = Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=select_autoescape(["html", "xml"]),
        )
        self.out = out
        self.documents = {}
        self.has_browserstack = (
            True
            if any([browserstack_access_key, os.environ["BSTACK_ACCESS_KEY"]])
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

    def build_pages(self, pages, dst=None, **kwargs):
        # XXX add nav functionatality
        for page in pages:
            self.build_page(page, dst=dst, **kwargs)

    def build_page(self, filename, dst=None, **kwargs):
        if filename not in os.listdir(self.template_dir):
            raise ValueError(f"'{filename}' not in dir '{self.template_dir}'")
        jinja_kwargs = {**self.__dict__, **kwargs}
        page = self._render_html(filename, dst=dst, **jinja_kwargs)
        page_name = filename[:-5]
        self.documents[page_name] = page

    def _render_html(self, filename, dst=None, **kwargs):
        html_template = self.jinja.get_template(filename)

        html = html_template.render(
            **kwargs,
        )
        dst = dst if dst else os.path.join(self.out, filename)
        with open(dst, "w") as html_file:
            html_file.write(html)
        return dst

    def _mkdir(self, path):
        if not os.path.isdir(path):
            os.mkdir(path)
        return path

    def save_imgs(self):
        img_dir = self._mkdir(os.path.join(self.out, "img"))

        start_daemon_server()
        with browserstack_local():
            for name, paths in self.documents.items():
                out = os.path.join(img_dir, name)
                self._mkdir(out)
                self._save_img(paths, out)

    def _save_img(self, path, dst):
        assert hasattr(self, "screenshot")
        # Don't use os.path on this since urls are always forward slashed
        url = f"http://0.0.0.0:8000/{path}"
        self.screenshot.take(url, dst)


class HtmlProof(HtmlTemplater):
    def __init__(self, fonts, out="out"):
        """Proof a single family"""
        super().__init__(out)
        self.fonts = fonts

        self.css_font_faces = css_font_faces(fonts, self.out)
        self.css_font_classes = css_font_classes(fonts)

        self.sample_text = " ".join(font_sample_text(self.fonts[0]))


class HtmlDiff(HtmlTemplater):
    def __init__(self, fonts_before, fonts_after, out="out"):
        """Compare two families"""
        super().__init__(out=out)
        self.fonts_before = fonts_before
        self.fonts_after = fonts_after

        self.css_font_faces_before = css_font_faces(
            fonts_before, self.out, position="before"
        )
        self.css_font_faces_after = css_font_faces(
            fonts_after, self.out, position="after"
        )

        self.css_font_classes_before = css_font_classes(fonts_before, "before")
        self.css_font_classes_after = css_font_classes(fonts_after, "after")

        self._match_css_font_classes()

        self.sample_text = " ".join(font_sample_text(self.fonts_before[0]))

    def _match_css_font_classes(self):
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
        filename,
        **kwargs,
    ):
        html_template = self.jinja.get_template(filename)

        combined = html_template.render(
            include_ui=True,
            **kwargs,
        )
        combined_path = os.path.join(self.out, filename)
        with open(combined_path, "w") as combined_html:
            combined_html.write(combined)

        before_kwargs = copy(kwargs)
        before_kwargs.pop("css_font_classes_after")
        before = html_template.render(
            **before_kwargs,
        )
        before_filename = f"{filename[:-5]}-before.html"
        before_path = os.path.join(self.out, before_filename)
        with open(before_path, "w") as before_html:
            before_html.write(before)

        after_kwargs = copy(kwargs)
        after_kwargs.pop("css_font_classes_before")
        after = html_template.render(
            **after_kwargs,
        )
        after_filename = f"{filename[:-5]}-after.html"
        after_path = os.path.join(self.out, after_filename)
        with open(after_path, "w") as after_html:
            after_html.write(after)

        return (before_path, after_path)

    def _save_img(self, document, dst):
        before_url = f"http://0.0.0.0:8000/{document[0]}"
        after_url = f"http://0.0.0.0:8000/{document[1]}"
        with tempfile.TemporaryDirectory() as before_dst, tempfile.TemporaryDirectory() as after_dst:
            self.screenshot.take(before_url, before_dst)
            self.screenshot.take(after_url, after_dst)
            gen_gifs(before_dst, after_dst, dst)


def simple_server(server_class=HTTPServer, handler_class=SimpleHTTPRequestHandler):
    server_address = ("", 8000)
    httpd = server_class(server_address, handler_class)
    httpd.serve_forever()


def start_daemon_server():
    th = threading.Thread(target=simple_server)
    th.daemon = True
    th.start()


@contextmanager
def browserstack_local():
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
    download files"""

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
