#!/usr/bin/env python3
#
# Copyright 2026 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Render a string from a font as a waterfall PNG.

The rendering backend is selected from the host platform by default
(CoreText on macOS, DirectWrite on Windows, FreeType on Linux). Use
``--backend`` to override.
"""

from __future__ import annotations

import sys
from argparse import ArgumentParser
from pathlib import Path

from gftools.render_text import (
    default_backend,
    is_variable,
    iter_fvar_instances,
    output_dir_for_all,
    output_path_for,
    output_path_for_instance,
    parse_variations,
    render_waterfall,
)


def main(args=None):
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("font", type=Path, help="Path to a .ttf/.otf font")
    parser.add_argument("text", help="String to render")
    parser.add_argument(
        "-o",
        "--output",
        help=(
            "Output PNG path. With --all, treated as an output directory. "
            "Defaults to <font_stem>.png (or <font_stem>_imgs/ for --all)."
        ),
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--variations",
        help='Variation location, e.g. "wght=400,wdth=75". Default instance if omitted.',
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Render one image per fvar instance.",
    )
    parser.add_argument(
        "--backend",
        choices=("coretext", "directwrite", "freetype"),
        default=None,
        help="Rendering backend. Defaults to the platform-native backend.",
    )

    opts = parser.parse_args(args)
    backend = opts.backend or default_backend()

    if opts.all:
        _render_all(opts.font, opts.text, opts.output, backend)
    else:
        variations = parse_variations(opts.variations) if opts.variations else None
        out = output_path_for(opts.font, variations=variations, output=opts.output)
        img = render_waterfall(
            opts.font, opts.text, variations=variations, backend=backend
        )
        img.save(out)
        print(out)


def _render_all(font: Path, text: str, output: str | None, backend: str) -> None:
    if not is_variable(font):
        print(
            f"warning: {font} is a static font — rendering default style only.",
            file=sys.stderr,
        )
        out = output_path_for(font, output=output)
        img = render_waterfall(font, text, backend=backend)
        img.save(out)
        print(out)
        return

    out_dir = output_dir_for_all(font, output_dir=output)
    out_dir.mkdir(parents=True, exist_ok=True)
    for instance_name, location in iter_fvar_instances(font):
        out = output_path_for_instance(font, instance_name, out_dir)
        img = render_waterfall(font, text, variations=location, backend=backend)
        img.save(out)
        print(out)


if __name__ == "__main__":
    main()
