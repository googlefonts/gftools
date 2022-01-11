#!/bin/bash
# Retrieve the latest axis registry and lang data from google/fonts. This
# script should be run before packaging a new release of
# gftools for pypi

AXIS_DST="Lib/gftools/axisregistry"
LANG_DST="Lib/gftools/lang"

rm -rf $AXIS_DST
# TODO (Marc F) don't use svn
echo "Downloading axis registry from github.com/google/fonts"
svn export --force https://github.com/google/fonts/trunk/axisregistry $AXIS_DST
svn export --force https://github.com/google/fonts/trunk/lang $LANG_DST
