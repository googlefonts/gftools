"""
gftools font tag editor.
"""

import os
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import argparse
import tempfile
import shutil
from importlib.resources import as_file, files


class HTTPRequestPostHandler(SimpleHTTPRequestHandler):

    def do_POST(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

        message = '{"status": "ok"}'
        self.wfile.write(bytes(message, "utf8"))

        file_length = int(self.headers["Content-Length"])
        data = self.rfile.read(file_length)
        with open("families.csv", "wb") as f:
            f.write(data)


def main(args=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "repo_path", type=Path, help="Path to the google/fonts repository"
    )
    args = parser.parse_args(args)

    tagging_fp = args.repo_path / "tags" / "all" / "families.csv"
    with (
        tempfile.TemporaryDirectory() as tmpdirname,
        as_file(files("gftools.tag-templates").joinpath("index.html")) as index_fp,
    ):
        shutil.copy(index_fp, tmpdirname)
        # create a symlink to the families.csv file in the google/fonts repo since
        # our server dir is a temporary directory
        os.symlink(tagging_fp, Path(tmpdirname) / "families.csv")
        os.chdir(tmpdirname)

        with HTTPServer(("", 8000), HTTPRequestPostHandler) as server:
            print("Server started at http://localhost:8000")
            print("Please keep this server running while you edit the tags.")
            print(
                "Once you're done editing, remember to commit the changes in "
                "your google/fonts repo and open a pr."
            )
            server.serve_forever()


if __name__ == "__main__":
    main()
