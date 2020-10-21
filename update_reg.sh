#!/bin/bash
# Retrieve the latest axis registry from google/fonts. This
# script should be run before packagaing a new release of
# gftools for pypi

AXIS_DST="Lib/gftools/axisregistry"

rm -rf $AXIS_DST
# TODO (Marc F) don't use svn
echo "Downloading axis registry from github.com/google/fonts"
svn export https://github.com/google/fonts/trunk/axisregistry $AXIS_DST
