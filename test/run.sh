#/usr/bin/env bash

set -e

# gftools add-font ./data/mock_googlefonts/ofl/abel
gftools build-ofl ./data/mock_googlefonts/ofl/abel/
gftools check-bbox ./data/Montserrat-Regular.ttf --glyphs
# gftools check-category requires gf api_key
gftools check-copyright-notices ./data/Montserrat-Regular.ttf
gftools check-font-version "Lora"
# gftools check-gf-github
gftools check-name ./data/Montserrat-Regular.ttf
gftools check-vf-avar --static-fonts ./data/Lora-Regular.ttf --variable-fonts ./data/Lora-Roman-VF.ttf -o out.html
gftools check-vtt-compatibility ./data/Lora-Regular.ttf ./data/Lora-Regular.ttf
gftools compare-font ./data/Lora-Regular.ttf ./data/Lora-Regular.ttf
gftools dump-names ./data/Lora-Regular.ttf
# gftools-family-html-snippet.py
# gftools-find-features.py
gftools fix-ascii-fontmetadata ./data/Lora-Regular.ttf
gftools fix-dsig ./data/Lora-Regular.ttf --autofix
gftools fix-familymetadata ./data/Lora-Regular.ttf
gftools fix-fsselection ./data/Lora-Regular.ttf
gftools fix-fstype ./data/Lora-Regular.ttf
gftools fix-gasp ./data/Montserrat-Regular.ttf
gftools fix-glyph-private-encoding ./data/Lora-Regular.ttf
gftools fix-glyphs ./data/Lora.glyphs
gftools fix-hinting ./data/Lora-Regular.ttf
gftools-fix-isfixedpitch.py --fonts ./data/Lora-Regular.ttf
gftools-fix-nameids.py ./data/Lora-Regular.ttf
gftools fix-nonhinting ./data/Lora-Roman-VF.ttf ./data/out.ttf
gftools fix-ttfautohint ./data/Lora-Regular.ttf
gftools fix-vendorid ./data/Lora-Regular.ttf
gftools fix-vertical-metrics ./data/Lora-Regular.ttf
gftools fix-vf-meta ./data/Lora-Roman-VF.ttf
gftools font-diff ./data/Lora-Regular.ttf ./data/Lora-Regular.ttf
gftools font-weights-coverage ./data/mock_googlefonts/ofl/abel/
gftools list-italicangle ./data/Lora-Regular.ttf
gftools list-panose ./data/Lora-Regular.ttf
gftools list-variable-source ./data/Lora-Roman-VF.ttf
gftools list-weightclass ./data/Lora-Regular.ttf
gftools list-widthclass ./data/Lora-Regular.ttf
# gftools-metadata-vs-api.py
# gftools-namelist.py
gftools nametable-from-filename ./data/Lora-Regular.ttf
gftools ots ./data/mock_googlefonts/
# gftools qa ./data/Lora-Regular.ttf --plot-glyphs
# gftools-rangify.py
# gftools-sanity-check.py
# gftools-test-gf-coverage.py
# gftools-ttf2cp.py
# gftools-unicode-names.py
# gftools-update-families.py
gftools update-version ./data/Lora-Regular.ttf 1.000 2.000
gftools varfont-info ./data/Lora-Roman-VF.ttf
gftools what-subsets ./data/Lora-Regular.ttf
rm ./data/*.fix ./data/out.ttf ./data/*gasp.ttf
