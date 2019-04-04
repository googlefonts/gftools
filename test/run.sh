#/usr/bin/env bash

set -e

gftools add-font ./data/mock_googlefonts/ofl/abel
gftools build-ofl ./data/mock_googlefonts/ofl/abel/
gftools check-bbox ./data/Montserrat-Regular.ttf --glyphs
gftools check-category $GF_API_KEY ./data/mock_googlefonts/ofl/
gftools check-copyright-notices ./data/Montserrat-Regular.ttf
gftools check-font-version "Lora"
# gftools check-gf-github does not work for two factor auth accounts
gftools check-name ./data/Montserrat-Regular.ttf
gftools check-vf-avar --static-fonts ./data/Lora-Regular.ttf --variable-fonts ./data/Lora-Roman-VF.ttf -o out.html
gftools check-vtt-compatibility ./data/Lora-Regular.ttf ./data/Lora-Regular.ttf
gftools compare-font ./data/Lora-Regular.ttf ./data/Lora-Regular.ttf
gftools dump-names ./data/Lora-Regular.ttf
gftools-family-html-snippet.py $GF_API_KEY "Abel" "Hello world"
# gftools-find-features.py Missing GsubLookupTypeName function
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
gftools-metadata-vs-api.py $GF_API_KEY ./data/mock_googlefonts
# gftools-namelist.py
gftools nametable-from-filename ./data/Lora-Regular.ttf
gftools ots ./data/mock_googlefonts/
# gftools qa ./data/Lora-Regular.ttf --plot-glyphs
gftools-rangify.py ./data/arabic_unique-glyphs.nam
gftools-sanity-check.py ./data/mock_googlefonts/ofl/abel/
# gftools-test-gf-coverage.py
# gftools-ttf2cp.py
# gftools-unicode-names.py
# gftools-update-families.py
gftools update-version ./data/Lora-Regular.ttf 1.000 2.000
gftools varfont-info ./data/Lora-Roman-VF.ttf
gftools what-subsets ./data/Lora-Regular.ttf
rm -f ./data/*.fix ./data/out.ttf ./data/*gasp.ttf ots_gf_results.txt out.ttf out.html possible_variable_fonts/
