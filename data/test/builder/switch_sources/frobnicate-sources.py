"""Silly script to copy-paste input to output, for testing source switching."""

from __future__ import annotations

import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("input", type=Path)
parser.add_argument("output", type=Path)
parsed_args = parser.parse_args()

input_path: Path = parsed_args.input
output_path: Path = parsed_args.output

output_path.write_text(input_path.read_text())
