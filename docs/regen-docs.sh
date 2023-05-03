#!/bin/sh
PYTHONPATH=../Lib python3 -c 'import gftools.builder; print(gftools.builder.__doc__)' | pandoc -f rst  -t markdown > gftools-builder/README.md
