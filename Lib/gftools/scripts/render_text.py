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
"""Render strings from a font as a waterfall PNG, or diff two fonts.

Subcommands:
  proof  Render a single font as a waterfall PNG.
  diff   Render before+after waterfalls plus difference image and animated GIF.

Backend defaults to the platform-native rasterizer (CoreText on macOS,
DirectWrite on Windows, FreeType on Linux). Override with ``--backend``.
"""

from __future__ import annotations

import sys
from argparse import ArgumentParser
from pathlib import Path

from gftools.render_text import (
    default_backend,
    diff_image,
    is_variable,
    iter_fvar_instances,
    output_dir_for_all,
    output_dir_for_diff,
    output_path_for,
    output_path_for_instance,
    output_subdir_for_instance,
    pad_to_match,
    parse_variations,
    render_waterfall,
    save_animation,
)


BACKENDS = ("coretext", "directwrite", "freetype")


def main(args=None):
    parser = ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)

    proof = subs.add_parser("proof", help="Render a font as a waterfall PNG.")
    proof.add_argument("font", type=Path, help="Path to a .ttf/.otf font")
    proof.add_argument("text", help="String to render")
    proof.add_argument(
        "-o",
        "--output",
        help=(
            "Output PNG path. With --all, treated as an output directory. "
            "Defaults to <font_stem>.png (or <font_stem>_imgs/ for --all)."
        ),
    )
    group = proof.add_mutually_exclusive_group()
    group.add_argument(
        "--variations",
        help='Variation location, e.g. "wght=400,wdth=75". Default instance if omitted.',
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Render one image per fvar instance.",
    )
    proof.add_argument(
        "--backend",
        choices=BACKENDS,
        default=None,
        help="Rendering backend. Defaults to the platform-native backend.",
    )
    proof.set_defaults(func=_run_proof)

    diff = subs.add_parser(
        "diff",
        help="Render before+after waterfalls plus a difference image and animated GIF.",
    )
    diff.add_argument("before", type=Path, help="Path to the 'before' font")
    diff.add_argument("after", type=Path, help="Path to the 'after' font")
    diff.add_argument("text", help="String to render")
    diff.add_argument(
        "-o",
        "--output",
        help="Output directory. Default: <after_stem>_diff/ next to the after font.",
    )
    diff_group = diff.add_mutually_exclusive_group()
    diff_group.add_argument(
        "--variations",
        help='Variation location applied to both fonts, e.g. "wght=400".',
    )
    diff_group.add_argument(
        "--all",
        action="store_true",
        help="Produce a diff bundle per fvar instance of the after font.",
    )
    diff.add_argument(
        "--backend",
        choices=BACKENDS,
        default=None,
        help="Rendering backend. Defaults to the platform-native backend.",
    )
    diff.set_defaults(func=_run_diff)

    opts = parser.parse_args(args)
    opts.func(opts)


def _run_proof(opts) -> None:
    backend = opts.backend or default_backend()
    if opts.all:
        _render_all(opts.font, opts.text, opts.output, backend)
        return
    variations = parse_variations(opts.variations) if opts.variations else None
    out = output_path_for(opts.font, variations=variations, output=opts.output)
    img = render_waterfall(opts.font, opts.text, variations=variations, backend=backend)
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


def _run_diff(opts) -> None:
    backend = opts.backend or default_backend()
    out_dir = output_dir_for_diff(opts.after, output_dir=opts.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    if opts.all and not is_variable(opts.after):
        print(
            f"warning: {opts.after} is a static font — rendering default style only.",
            file=sys.stderr,
        )

    if opts.all and is_variable(opts.after):
        for instance_name, location in iter_fvar_instances(opts.after):
            subdir = output_subdir_for_instance(out_dir, instance_name)
            subdir.mkdir(parents=True, exist_ok=True)
            _emit_diff_bundle(
                opts.before, opts.after, opts.text, location, backend, subdir
            )
    else:
        variations = parse_variations(opts.variations) if opts.variations else None
        _emit_diff_bundle(
            opts.before, opts.after, opts.text, variations, backend, out_dir
        )


def _emit_diff_bundle(
    before_path: Path,
    after_path: Path,
    text: str,
    variations: dict | None,
    backend: str,
    out_dir: Path,
) -> None:
    before_img = render_waterfall(
        before_path, text, variations=variations, backend=backend
    )
    after_img = render_waterfall(
        after_path, text, variations=variations, backend=backend
    )
    before_pad, after_pad = pad_to_match([before_img, after_img])
    diff_img = diff_image(before_pad, after_pad)

    before_pad.save(out_dir / "before.png")
    after_pad.save(out_dir / "after.png")
    diff_img.save(out_dir / "diff.png")
    save_animation(
        [before_pad, after_pad],
        out_dir / "anim.gif",
        labels=["before", "after"],
    )

    for name in ("before.png", "after.png", "diff.png", "anim.gif"):
        print(out_dir / name)


if __name__ == "__main__":
    main()
