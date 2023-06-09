#!/usr/bin/env python3
"""
Generate the to_production.txt and to_sandbox.txt server files in a local
google/fonts repository.

to_production.txt file tells the engineers which directories need to be pushed
to the production server. Likewise, the to_sandbox.txt file is for directories
to be pushed to the sandbox server.

In order for this script to work, the traffic jam must be kept up to date and
pull requests must use labels.

Usage:
gftools gen-push-lists /path/to/google/fonts
"""
from gftools.push import parse_server_file
from github import Github
from collections import defaultdict
import os
import re
import sys
from pathlib import Path
from gftools.push import repo_path_to_google_path

data = {'data': {'organization': {'projectV2': {'id': 'PVT_kwDOABR6NM4ARPDn', 'title': 'Fonts Traffic Jam', 'items': {'nodes': [{'id': 'PVTI_lADOABR6NM4ARPDnzgHMY1o', 'status': {'name': 'Live'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc5HRc94', 'files': {'nodes': [{'path': 'ofl/sofiasans/DESCRIPTION.en_us.html'}, {'path': 'ofl/sofiasans/METADATA.pb'}, {'path': 'ofl/sofiasans/SofiaSans-Italic[wght].ttf'}, {'path': 'ofl/sofiasans/SofiaSans[wght].ttf'}]}, 'url': 'https://github.com/google/fonts/pull/5776', 'labels': {'nodes': [{'name': 'I Small Fix'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMY1s', 'status': {'name': 'Live'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc5Fh91j', 'files': {'nodes': [{'path': 'ofl/baskervville/Baskervville-Italic.ttf'}, {'path': 'ofl/baskervville/Baskervville-Regular.ttf'}, {'path': 'ofl/baskervville/METADATA.pb'}, {'path': 'ofl/baskervville/upstream.yaml'}]}, 'url': 'https://github.com/google/fonts/pull/5718', 'labels': {'nodes': [{'name': 'I Small Fix'}, {'name': 'III Improve rendering / layout'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMY1w', 'status': {'name': 'Live'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc5HRx6-', 'files': {'nodes': [{'path': 'ofl/sofiasanssemicondensed/DESCRIPTION.en_us.html'}, {'path': 'ofl/sofiasanssemicondensed/METADATA.pb'}, {'path': 'ofl/sofiasanssemicondensed/SofiaSansSemiCondensed-Italic[wght].ttf'}, {'path': 'ofl/sofiasanssemicondensed/SofiaSansSemiCondensed[wght].ttf'}]}, 'url': 'https://github.com/google/fonts/pull/5778', 'labels': {'nodes': [{'name': 'I Small Fix'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMY14', 'status': {'name': 'Live'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc5HRzqx', 'files': {'nodes': [{'path': 'ofl/sofiasanscondensed/DESCRIPTION.en_us.html'}, {'path': 'ofl/sofiasanscondensed/METADATA.pb'}, {'path': 'ofl/sofiasanscondensed/SofiaSansCondensed-Italic[wght].ttf'}, {'path': 'ofl/sofiasanscondensed/SofiaSansCondensed[wght].ttf'}]}, 'url': 'https://github.com/google/fonts/pull/5779', 'labels': {'nodes': [{'name': 'I Small Fix'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMY18', 'status': {'name': 'Live'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc5Feudu', 'files': {'nodes': [{'path': 'ofl/hankengrotesk/METADATA.pb'}]}, 'url': 'https://github.com/google/fonts/pull/5715', 'labels': {'nodes': [{'name': 'I Description/Metadata/OFL'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMY2A', 'status': {'name': 'Live'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc5HRvtD', 'files': {'nodes': [{'path': 'ofl/sofiasansextracondensed/DESCRIPTION.en_us.html'}, {'path': 'ofl/sofiasansextracondensed/METADATA.pb'}, {'path': 'ofl/sofiasansextracondensed/SofiaSansExtraCondensed-Italic[wght].ttf'}, {'path': 'ofl/sofiasansextracondensed/SofiaSansExtraCondensed[wght].ttf'}]}, 'url': 'https://github.com/google/fonts/pull/5777', 'labels': {'nodes': [{'name': 'I Small Fix'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMY2E', 'status': {'name': 'Live'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc5FUy-T', 'files': {'nodes': [{'path': '.ci/run.sh'}, {'path': 'axisregistry/Lib/axisregistry/data/mutation.textproto'}, {'path': 'axisregistry/Lib/axisregistry/data/optical_size.textproto'}, {'path': 'axisregistry/tests/data/RobotoFlex[GRAD,XOPQ,XTRA,YOPQ,YTAS,YTDE,YTFI,YTLC,YTUC,opsz,slnt,wdth,wght].ttf'}, {'path': 'axisregistry/tests/data/RobotoFlex[GRAD,XOPQ,XTRA,YOPQ,YTAS,YTDE,YTFI,YTLC,YTUC,opsz,slnt,wdth,wght]_STAT.ttx'}]}, 'url': 'https://github.com/google/fonts/pull/5704', 'labels': {'nodes': [{'name': 'I Axis Registry'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMY2M', 'status': {'name': 'Live'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc5E84IM', 'files': {'nodes': [{'path': 'ofl/bizudmincho/BIZUDMincho-Bold.ttf'}, {'path': 'ofl/bizudmincho/BIZUDMincho-Regular.ttf'}, {'path': 'ofl/bizudmincho/METADATA.pb'}, {'path': 'ofl/bizudmincho/upstream.yaml'}, {'path': 'ofl/bizudpmincho/BIZUDPMincho-Bold.ttf'}, {'path': 'ofl/bizudpmincho/BIZUDPMincho-Regular.ttf'}, {'path': 'ofl/bizudpmincho/METADATA.pb'}, {'path': 'ofl/bizudpmincho/article/hero.png'}, {'path': 'ofl/bizudpmincho/upstream.yaml'}]}, 'url': 'https://github.com/google/fonts/pull/5697', 'labels': {'nodes': [{'name': 'III Expand styles'}, {'name': 'I Font Upgrade'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMY2Q', 'status': {'name': 'Live'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc5FgMlC', 'files': {'nodes': [{'path': 'ofl/allura/Allura-Regular.ttf'}, {'path': 'ofl/allura/METADATA.pb'}, {'path': 'ofl/allura/upstream.yaml'}]}, 'url': 'https://github.com/google/fonts/pull/5716', 'labels': {'nodes': [{'name': 'I Small Fix'}, {'name': 'III Improve rendering / layout'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMY2g', 'status': {'name': 'Live'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc5EphC8', 'files': {'nodes': [{'path': 'ofl/intertight/InterTight-Italic[wght].ttf'}, {'path': 'ofl/intertight/InterTight[wght].ttf'}, {'path': 'ofl/intertight/METADATA.pb'}]}, 'url': 'https://github.com/google/fonts/pull/5681', 'labels': {'nodes': [{'name': 'I Small Fix'}, {'name': 'III Improve rendering / layout'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMY2w', 'status': {'name': 'Live'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc5Ej8Ll', 'files': {'nodes': [{'path': 'axisregistry/.github/ISSUE_TEMPLATE/1_add-axis.md'}, {'path': 'axisregistry/.github/ISSUE_TEMPLATE/2_anything-else.md'}, {'path': 'axisregistry/CHANGELOG.md'}, {'path': 'axisregistry/Lib/axisregistry/__init__.py'}, {'path': 'axisregistry/Lib/axisregistry/data/bounce.textproto'}, {'path': 'axisregistry/Lib/axisregistry/data/informality.textproto'}, {'path': 'axisregistry/Lib/axisregistry/data/spacing.textproto'}, {'path': 'axisregistry/Lib/axisregistry/data/x_rotation.textproto'}, {'path': 'axisregistry/Lib/axisregistry/data/y_rotation.textproto'}, {'path': 'axisregistry/setup.py'}]}, 'url': 'https://github.com/google/fonts/pull/5677', 'labels': {'nodes': [{'name': 'I Axis Registry'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMY24', 'status': {'name': 'Live'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc5EJ5lb', 'files': {'nodes': [{'path': 'catalog/designers/alfredomarcopradil/alfredomarcopradil.png'}, {'path': 'catalog/designers/alfredomarcopradil/bio.html'}, {'path': 'catalog/designers/alfredomarcopradil/info.pb'}, {'path': 'catalog/designers/hankendesignco/bio.html'}, {'path': 'catalog/designers/hankendesignco/hankendesignco.png'}, {'path': 'catalog/designers/hankendesignco/info.pb'}]}, 'url': 'https://github.com/google/fonts/pull/5669', 'labels': {'nodes': [{'name': 'I Designer profile'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMY3A', 'status': {'name': 'Live'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc5EgWQ9', 'files': {'nodes': [{'path': 'ofl/padyakkeexpandedone/DESCRIPTION.en_us.html'}, {'path': 'ofl/padyakkeexpandedone/METADATA.pb'}, {'path': 'ofl/padyakkeexpandedone/OFL.txt'}, {'path': 'ofl/padyakkeexpandedone/PadyakkeExpandedOne-Regular.ttf'}, {'path': 'ofl/padyakkeexpandedone/upstream.yaml'}]}, 'url': 'https://github.com/google/fonts/pull/5676', 'labels': {'nodes': [{'name': 'I New Font'}, {'name': 'II Indic / Brahmic / Thai / Tai'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMY3I', 'status': {'name': 'Live'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc5EdQdK', 'files': {'nodes': [{'path': 'ofl/artifika/Artifika-Regular.ttf'}, {'path': 'ofl/artifika/DESCRIPTION.en_us.html'}, {'path': 'ofl/artifika/METADATA.pb'}, {'path': 'ofl/artifika/OFL.txt'}, {'path': 'ofl/artifika/upstream.yaml'}]}, 'url': 'https://github.com/google/fonts/pull/5675', 'labels': {'nodes': [{'name': 'I Small Fix'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMY3Q', 'status': {'name': 'Live'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc5En5YJ', 'files': {'nodes': [{'path': 'ofl/amiri/Amiri-Bold.ttf'}, {'path': 'ofl/amiri/Amiri-BoldItalic.ttf'}, {'path': 'ofl/amiri/Amiri-Italic.ttf'}, {'path': 'ofl/amiri/Amiri-Regular.ttf'}, {'path': 'ofl/amiri/DESCRIPTION.en_us.html'}, {'path': 'ofl/amiri/METADATA.pb'}, {'path': 'ofl/amiri/OFL.txt'}]}, 'url': 'https://github.com/google/fonts/pull/5679', 'labels': {'nodes': [{'name': 'I Font Upgrade'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMY3U', 'status': {'name': 'Live'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc5EEJV5', 'files': {'nodes': [{'path': 'ofl/dmserifdisplay/DESCRIPTION.en_us.html'}, {'path': 'ofl/dmserifdisplay/METADATA.pb'}]}, 'url': 'https://github.com/google/fonts/pull/5660', 'labels': {'nodes': [{'name': 'I Description/Metadata/OFL'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMY3c', 'status': {'name': 'Live'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc5DCre9', 'files': {'nodes': [{'path': 'lang/CHANGELOG.md'}, {'path': 'lang/Lib/gflanguages/data/languages/bug_Latn.textproto'}, {'path': 'lang/Lib/gflanguages/data/languages/ccp_Beng.textproto'}, {'path': 'lang/Lib/gflanguages/data/languages/ku_Cyrl.textproto'}, {'path': 'lang/Lib/gflanguages/data/languages/shi_Arab.textproto'}, {'path': 'lang/Lib/gflanguages/data/languages/shi_Tfng.textproto'}, {'path': 'lang/Lib/gflanguages/data/languages/tk_Arab.textproto'}, {'path': 'lang/Lib/gflanguages/data/scripts/Chrs.textproto'}, {'path': 'lang/dev-requirements.txt'}, {'path': 'lang/setup.py'}]}, 'url': 'https://github.com/google/fonts/pull/5557', 'labels': {'nodes': [{'name': 'I Lang'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMY3k', 'status': {'name': 'Live'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc5E0bg-', 'files': {'nodes': [{'path': 'ofl/alexbrush/AlexBrush-Regular.ttf'}, {'path': 'ofl/alexbrush/METADATA.pb'}, {'path': 'ofl/alexbrush/upstream.yaml'}]}, 'url': 'https://github.com/google/fonts/pull/5686', 'labels': {'nodes': [{'name': 'I Font Upgrade'}, {'name': 'III Improve rendering / layout'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMY3s', 'status': {'name': 'Live'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc5EEKEK', 'files': {'nodes': [{'path': 'ofl/dmseriftext/DESCRIPTION.en_us.html'}, {'path': 'ofl/dmseriftext/METADATA.pb'}]}, 'url': 'https://github.com/google/fonts/pull/5661', 'labels': {'nodes': [{'name': 'I Description/Metadata/OFL'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMY30', 'status': {'name': 'Live'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc5DKX0J', 'files': {'nodes': [{'path': 'ofl/sofiasans/DESCRIPTION.en_us.html'}, {'path': 'ofl/sofiasans/METADATA.pb'}, {'path': 'ofl/sofiasans/SofiaSans-Italic[wdth,wght].ttf'}, {'path': 'ofl/sofiasans/SofiaSans-Italic[wght].ttf'}, {'path': 'ofl/sofiasans/SofiaSans[wdth,wght].ttf'}, {'path': 'ofl/sofiasans/SofiaSans[wght].ttf'}, {'path': 'ofl/sofiasans/upstream.yaml'}]}, 'url': 'https://github.com/google/fonts/pull/5580', 'labels': {'nodes': [{'name': 'I New Font'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMY34', 'status': {'name': 'Live'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc5DKWfS', 'files': {'nodes': [{'path': 'ofl/sofiasanssemicondensed/DESCRIPTION.en_us.html'}, {'path': 'ofl/sofiasanssemicondensed/METADATA.pb'}, {'path': 'ofl/sofiasanssemicondensed/OFL.txt'}, {'path': 'ofl/sofiasanssemicondensed/SofiaSansSemiCondensed-Italic[wght].ttf'}, {'path': 'ofl/sofiasanssemicondensed/SofiaSansSemiCondensed[wght].ttf'}, {'path': 'ofl/sofiasanssemicondensed/upstream.yaml'}]}, 'url': 'https://github.com/google/fonts/pull/5579', 'labels': {'nodes': [{'name': 'I New Font'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMY4E', 'status': {'name': 'Live'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc5DJ4MK', 'files': {'nodes': [{'path': 'ofl/fraunces/METADATA.pb'}, {'path': 'ofl/gulzar/METADATA.pb'}, {'path': 'ofl/recursive/METADATA.pb'}, {'path': 'ofl/spacegrotesk/METADATA.pb'}]}, 'url': 'https://github.com/google/fonts/pull/5570', 'labels': {'nodes': [{'name': 'I Description/Metadata/OFL'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMY4I', 'status': {'name': 'Live'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc5DKUpx', 'files': {'nodes': [{'path': 'ofl/sofiasanscondensed/DESCRIPTION.en_us.html'}, {'path': 'ofl/sofiasanscondensed/METADATA.pb'}, {'path': 'ofl/sofiasanscondensed/OFL.txt'}, {'path': 'ofl/sofiasanscondensed/SofiaSansCondensed-Italic[wght].ttf'}, {'path': 'ofl/sofiasanscondensed/SofiaSansCondensed[wght].ttf'}, {'path': 'ofl/sofiasanscondensed/upstream.yaml'}]}, 'url': 'https://github.com/google/fonts/pull/5577', 'labels': {'nodes': [{'name': 'I New Font'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMY4Q', 'status': {'name': 'Live'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc5DKV01', 'files': {'nodes': [{'path': 'ofl/sofiasansextracondensed/DESCRIPTION.en_us.html'}, {'path': 'ofl/sofiasansextracondensed/METADATA.pb'}, {'path': 'ofl/sofiasansextracondensed/OFL.txt'}, {'path': 'ofl/sofiasansextracondensed/SofiaSansExtraCondensed-Italic[wght].ttf'}, {'path': 'ofl/sofiasansextracondensed/SofiaSansExtraCondensed[wght].ttf'}, {'path': 'ofl/sofiasansextracondensed/upstream.yaml'}]}, 'url': 'https://github.com/google/fonts/pull/5578', 'labels': {'nodes': [{'name': 'I New Font'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMZ5c', 'status': {'name': 'PR GF'}, 'type': 'PULL_REQUEST', 'content': {'id': 'MDExOlB1bGxSZXF1ZXN0NTY2NzM3NjI0', 'files': {'nodes': [{'path': 'apache/opensans/DESCRIPTION.en_us.html'}, {'path': 'apache/opensanscondensed/DESCRIPTION.en_us.html'}, {'path': 'apache/roboto/DESCRIPTION.en_us.html'}, {'path': 'apache/robotoslab/DESCRIPTION.en_us.html'}, {'path': 'ofl/amarante/DESCRIPTION.en_us.html'}, {'path': 'ofl/amstelvaralpha/DESCRIPTION.en_us.html'}, {'path': 'ofl/antonio/DESCRIPTION.en_us.html'}, {'path': 'ofl/arefruqaa/DESCRIPTION.en_us.html'}, {'path': 'ofl/arizonia/DESCRIPTION.en_us.html'}, {'path': 'ofl/armata/DESCRIPTION.en_us.html'}]}, 'url': 'https://github.com/google/fonts/pull/2987', 'labels': {'nodes': [{'name': '- Ready for Review'}, {'name': 'I Description/Metadata/OFL'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMZ5g', 'status': {'name': 'PR GF'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc4_LqCS', 'files': {'nodes': [{'path': 'ofl/notosanslydian/METADATA.pb'}, {'path': 'ofl/notosanslydian/NotoSansLydian-Regular.ttf'}, {'path': 'ofl/notosanslydian/OFL.txt'}, {'path': 'ofl/notosanslydian/upstream.yaml'}]}, 'url': 'https://github.com/google/fonts/pull/5264', 'labels': {'nodes': [{'name': '- Ready for Review'}, {'name': 'I Font Upgrade'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMZ5k', 'status': {'name': 'PR GF'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc4_LrP1', 'files': {'nodes': [{'path': 'ofl/notosansmanichaean/METADATA.pb'}, {'path': 'ofl/notosansmanichaean/NotoSansManichaean-Regular.ttf'}, {'path': 'ofl/notosansmanichaean/OFL.txt'}, {'path': 'ofl/notosansmanichaean/upstream.yaml'}]}, 'url': 'https://github.com/google/fonts/pull/5266', 'labels': {'nodes': [{'name': '- Ready for Review'}, {'name': 'I Font Upgrade'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMZ50', 'status': {'name': 'PR GF'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc4_LtMl', 'files': {'nodes': [{'path': 'ofl/notosansogham/METADATA.pb'}, {'path': 'ofl/notosansogham/NotoSansOgham-Regular.ttf'}, {'path': 'ofl/notosansogham/OFL.txt'}, {'path': 'ofl/notosansogham/upstream.yaml'}]}, 'url': 'https://github.com/google/fonts/pull/5268', 'labels': {'nodes': [{'name': '- Ready for Review'}, {'name': 'I Font Upgrade'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMZ54', 'status': {'name': 'PR GF'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc4_SfAy', 'files': {'nodes': [{'path': 'ofl/notosanscarian/METADATA.pb'}, {'path': 'ofl/notosanscarian/NotoSansCarian-Regular.ttf'}, {'path': 'ofl/notosanscarian/OFL.txt'}, {'path': 'ofl/notosanscarian/upstream.yaml'}]}, 'url': 'https://github.com/google/fonts/pull/5277', 'labels': {'nodes': [{'name': '- Ready for Review'}, {'name': 'I Font Upgrade'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMZ58', 'status': {'name': 'PR GF'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc4_iubH', 'files': {'nodes': [{'path': 'ofl/notosansoldpersian/METADATA.pb'}, {'path': 'ofl/notosansoldpersian/NotoSansOldPersian-Regular.ttf'}, {'path': 'ofl/notosansoldpersian/OFL.txt'}, {'path': 'ofl/notosansoldpersian/upstream.yaml'}]}, 'url': 'https://github.com/google/fonts/pull/5313', 'labels': {'nodes': [{'name': '- Ready for Review'}, {'name': 'I Font Upgrade'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMZ6E', 'status': {'name': 'PR GF'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc4_iu2R', 'files': {'nodes': [{'path': 'ofl/notosansmeroitic/METADATA.pb'}, {'path': 'ofl/notosansmeroitic/NotoSansMeroitic-Regular.ttf'}, {'path': 'ofl/notosansmeroitic/OFL.txt'}, {'path': 'ofl/notosansmeroitic/upstream.yaml'}]}, 'url': 'https://github.com/google/fonts/pull/5316', 'labels': {'nodes': [{'name': '- Ready for Review'}, {'name': 'I Font Upgrade'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMZ6Q', 'status': {'name': 'PR GF'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc4_oZKO', 'files': {'nodes': [{'path': '.github/workflows/ci.yaml'}, {'path': '.github/workflows/report.yaml'}, {'path': '.github/workflows/test.yaml'}]}, 'url': 'https://github.com/google/fonts/pull/5326', 'labels': {'nodes': [{'name': 'I Tools / workflow / repo'}, {'name': "-- Needs manager's opinion"}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMZ6U', 'status': {'name': 'PR GF'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc5At5Sm', 'files': {'nodes': [{'path': 'ofl/jainipurva/DESCRIPTION.en_us.html'}, {'path': 'ofl/jainipurva/JainiPurva-Regular.ttf'}, {'path': 'ofl/jainipurva/METADATA.pb'}, {'path': 'ofl/jainipurva/OFL.txt'}, {'path': 'ofl/jainipurva/upstream.yaml'}]}, 'url': 'https://github.com/google/fonts/pull/5403', 'labels': {'nodes': [{'name': "-- Needs manager's opinion"}, {'name': 'I New Font'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMZ6g', 'status': {'name': 'PR GF'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc5MopPo', 'files': {'nodes': [{'path': 'apache/roboto/Roboto-Italic[wdth,wght].ttf'}, {'path': 'apache/roboto/Roboto[wdth,wght].ttf'}]}, 'url': 'https://github.com/google/fonts/pull/6060', 'labels': {'nodes': []}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMZ6k', 'status': {'name': 'In Dev / PR Merged'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc5SUiqY', 'files': {'nodes': [{'path': 'ofl/aleo/Aleo-Bold.ttf'}, {'path': 'ofl/aleo/Aleo-BoldItalic.ttf'}, {'path': 'ofl/aleo/Aleo-Italic.ttf'}, {'path': 'ofl/aleo/Aleo-Italic[wght].ttf'}, {'path': 'ofl/aleo/Aleo-Light.ttf'}, {'path': 'ofl/aleo/Aleo-LightItalic.ttf'}, {'path': 'ofl/aleo/Aleo-Regular.ttf'}, {'path': 'ofl/aleo/Aleo[wght].ttf'}, {'path': 'ofl/aleo/DESCRIPTION.en_us.html'}, {'path': 'ofl/aleo/METADATA.pb'}]}, 'url': 'https://github.com/google/fonts/pull/6345', 'labels': {'nodes': [{'name': 'III Expand glyphset'}, {'name': 'III Expand styles'}, {'name': 'III VF Replacement'}, {'name': '--- to sandbox'}, {'name': 'I Font Upgrade'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMgJY', 'status': {'name': 'PR GF'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc5SZxv_', 'files': {'nodes': [{'path': 'ofl/rubik/METADATA.pb'}, {'path': 'ofl/rubik/Rubik-Italic[wght].ttf'}, {'path': 'ofl/rubik/Rubik[wght].ttf'}]}, 'url': 'https://github.com/google/fonts/pull/6346', 'labels': {'nodes': [{'name': "-- Needs manager's opinion"}, {'name': 'I Font Upgrade'}, {'name': 'II Arabic / Hebrew / Semitic / RTL'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMh5E', 'status': {'name': 'PR GF'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc5SZ5WS', 'files': {'nodes': [{'path': 'catalog/designers/danielgrumer/bio.html'}, {'path': 'catalog/designers/danielgrumer/danielgrumer.png'}, {'path': 'catalog/designers/danielgrumer/info.pb'}]}, 'url': 'https://github.com/google/fonts/pull/6347', 'labels': {'nodes': [{'name': '- Ready for Review'}, {'name': 'I Designer profile'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHMi_s', 'status': {'name': 'Live'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc5BOCPJ', 'files': {'nodes': [{'path': 'ofl/acme/DESCRIPTION.en_us.html'}, {'path': 'ofl/alegreya/DESCRIPTION.en_us.html'}, {'path': 'ofl/alegreyasans/DESCRIPTION.en_us.html'}, {'path': 'ofl/alegreyasanssc/DESCRIPTION.en_us.html'}, {'path': 'ofl/alegreyasc/DESCRIPTION.en_us.html'}, {'path': 'ofl/andadapro/DESCRIPTION.en_us.html'}, {'path': 'ofl/bitter/DESCRIPTION.en_us.html'}, {'path': 'ofl/cambo/DESCRIPTION.en_us.html'}, {'path': 'ofl/gochihand/DESCRIPTION.en_us.html'}, {'path': 'ofl/piazzolla/DESCRIPTION.en_us.html'}]}, 'url': 'https://github.com/google/fonts/pull/5450', 'labels': {'nodes': [{'name': '--- Live'}, {'name': 'I Description/Metadata/OFL'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHOIMM', 'status': {'name': 'In Dev / PR Merged'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc5SgrVa', 'files': {'nodes': [{'path': 'lang/CHANGELOG.md'}, {'path': 'lang/Lib/gflanguages/data/languages/sa_Gong.textproto'}, {'path': 'lang/Lib/gflanguages/data/languages/wsg_Gong.textproto'}]}, 'url': 'https://github.com/google/fonts/pull/6352', 'labels': {'nodes': [{'name': '--- to sandbox'}, {'name': 'I Lang'}]}}}, {'id': 'PVTI_lADOABR6NM4ARPDnzgHOQLo', 'status': {'name': 'In Dev / PR Merged'}, 'type': 'PULL_REQUEST', 'content': {'id': 'PR_kwDOAdQSTc5ShOLA', 'files': {'nodes': [{'path': 'ofl/narnoor/METADATA.pb'}]}, 'url': 'https://github.com/google/fonts/pull/6353', 'labels': {'nodes': [{'name': '--- to sandbox'}, {'name': 'I Description/Metadata/OFL'}]}}}]}}}}}


def pr_directories(fps):
    results = set()
    files = [Path(fp) for fp in fps]
    for f in files:
        path = f
        if path.suffix == ".textproto" and any(d in path.parts for d in ("lang", "axisregistry")):
            results.add(repo_path_to_google_path(path))
        else:
            path = path.parent
            # If a noto article has been updated, just return the family dir
            # ofl/notosans/article --> ofl/notosans
            if "article" in path.parts:
                path = path.parent
            results.add(str(path))
    return results


def write_server_file(data):
    doc = []
    categories_to_write = []
    for cat in (
        "New",
        "Upgrade",
        "Other",
        "Designer profile",
        "Axis Registry",
        "Knowledge",
        "Metadata / Description / License",
        "Sample texts"
    ):
        if cat in data:
            categories_to_write.append(cat)

    for cat in data:
        if cat not in categories_to_write:
            print(f"{cat} isn't sorted appending to end of doc")
            categories_to_write.append(cat)

    seen = set()
    for cat in categories_to_write:
        doc.append(f"# {cat}")
        directories = sorted(data[cat], key=lambda f: len(f))
        filtered_directories = []
        for directory in directories:
            # Skip subdirectories when parent is already seen
            plain_path = re.sub(r" # .*", "", directory)
            path = Path(plain_path)
            if str(path.parent) in seen:
                continue
            # for the axis registry and lang subtrees, we list the file,
            # not the dir
            if any(d in path.parts for d in ("lang", "axisregistry")) \
                and path.suffix != ".textproto":
                print(f"filtering {path}")
                continue
            seen.add(plain_path)
            filtered_directories.append(directory)
        doc.append("\n".join(sorted(filtered_directories)))
        doc.append("")
    return "\n".join(doc)


def main(args=None):
    if len(sys.argv) != 3:
        print("Usage: gftools gen-push-lists /path/to/google/fonts")
        sys.exit()

    to_sandbox = defaultdict(set)
    to_production = defaultdict(set)


    
    board_items = data["data"]["organization"]["projectV2"]["items"]["nodes"]
    for item in board_items:
        status = item.get("status", {}).get("name", None)
        if status in ["PR GF", "Live"]:
            continue

        if "labels" not in item["content"]:
            print("PR missing labels. Skipping")
            continue
        labels = [i["name"] for i in item["content"]["labels"]["nodes"]]
        # Skip blocked prs
        if "-- blocked" in labels:
            print("PR is blocked. Skipping")
            continue
        
        files = [i["path"] for i in item["content"]["files"]["nodes"]] 
        url = item["content"]["url"]
        directories = set(f"{fp} # {url}" for fp in pr_directories(files))

        # get pr state
        if "I Font Upgrade" in labels or "I Small Fix" in labels:
            cat = "Upgrade"
        elif "I New Font" in labels:
            cat = "New"
        elif "I Description/Metadata/OFL" in labels:
            cat = "Metadata / Description / License"
        elif "I Designer profile" in labels:
            cat = "Designer profile"
        elif "I Knowledge" in labels:
            cat = "Knowledge"
        elif "I Axis Registry" in labels:
            cat = "Axis Registry"
        elif "I Lang" in labels:
            cat = "Sample texts"
        else:
            cat = "Other"

        # assign bin
        if status == 'In Dev / PR Merged':
            to_sandbox[cat] |= directories
        elif status == "In Sandbox":
            to_production[cat] |= directories

    
    import pdb
    pdb.set_trace()






    seen_directories = set()
    print("Analysing pull requests in traffic jam. This may take a while!")
    for col in columns:
        if col.name not in set(
            ["Just merged / In transit", "In Sandbox list", "In Production list"]
        ):
            continue
        cards = col.get_cards()
        for card in cards:
            content = card.get_content()
            if not hasattr(content, "labels"):
                print(f"skipping {card}. No labels!")
                continue

            labels = set(l.name for l in content.labels)
            pr = content.as_pull_request()
            directories = set(f"{directory} # {pr.html_url}" for directory in pr_directories(pr))

            if "-- blocked" in labels or "--- Live" in labels:
                continue
            seen_directories |= set(d.replace(" ", "").lower() for d in directories)
            if "I Font Upgrade" in labels or "I Small Fix" in labels:
                cat = "Upgrade"
            elif "I New Font" in labels:
                cat = "New"
            elif "I Description/Metadata/OFL" in labels:
                cat = "Metadata / Description / License"
            elif "I Designer profile" in labels:
                cat = "Designer profile"
            elif "I Knowledge" in labels:
                cat = "Knowledge"
            elif "I Axis Registry" in labels:
                cat = "Axis Registry"
            elif "I Lang" in labels:
                cat = "Sample texts"
            else:
                cat = "Other"
            if "--- to sandbox" in labels:
                to_sandbox[cat] |= directories
            if "--- to production" in labels:
                to_production[cat] |= directories

    gf_repo_path = sys.argv[2]
    sb_path = os.path.join(gf_repo_path, "to_sandbox.txt")
    prod_path = os.path.join(gf_repo_path, "to_production.txt")

    # Keep paths which have been entered manually which do not belong to
    # a label. These need to be manually deleted as well.
    existing_sandbox = parse_server_file(sb_path)
    for i in existing_sandbox:
        if str(i.raw.replace(" ", "").lower()) not in seen_directories:
            to_sandbox[i.type].add(str(i.raw))

    existing_production = parse_server_file(prod_path)
    for i in existing_production:
        if str(i.raw.replace(" ", "").lower()) not in seen_directories:
            to_production[i.type].add(str(i.raw))

    with open(sb_path, "w") as sb_doc:
        sb_doc.write(write_server_file(to_sandbox))

    with open(prod_path, "w") as prod_doc:
        prod_doc.write(write_server_file(to_production))

    print("Done!")


if __name__ == "__main__":
    main()
