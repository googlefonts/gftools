"""Generate STAT tables for a Variable Font Family

This module exports the functions "gen_stat_tables" and
"gen_stat_tables_from_config" which can be used to
generate a STAT table for each font in a Variable Font Family.

The STAT AxisValues are constructed using the Google Font's Axis Registry,
https://github.com/google/fonts/tree/main/axisregistry

The function should be able to make STAT tables for any family with the
following properties:
- All fonts contain the same amount of fvar axes
- All fvar axes have the same ranges
"""

from axisregistry import AxisRegistry
from fontTools.otlLib.builder import buildStatTable
from gftools.utils import font_is_italic
import os
import logging


__all__ = ["gen_stat_tables", "gen_stat_tables_from_config"]


log = logging.getLogger(__name__)


def gen_stat_tables(ttFonts):
    from axisregistry import build_stat

    for ttFont in ttFonts:
        siblings = [f for f in ttFonts if f != ttFont]
        build_stat(ttFont, siblings)


def gen_stat_tables_from_config(stat, varfonts, has_italic=None, locations=None):
    """
    Generate a stat table for each font in a family from a Python configuration.

    Args:
        stat: either a dictionary or list as described below
        varfonts: a list of variable TTFont instances
        has_italic: a boolean indicating whether the family contains an italic.
            If not provided, the stylename of the font files are inspected to
            determine if any of them contain the word ``Italic``.

    The ``stat`` parameter should normally be a list of axis dictionaries in the
    format used by ``buildStatTable``. This list should *not* contain an entry
    for the ``ital`` axis, as this entry will be generated as appropriate for
    each font if ``has_italic`` is True.

    For example::

        varfonts = [
            "Source-Regular-VF[wdth].ttf",
            "Source-Italic-VF[wdth].ttf"
        ]
        stat = [
                { "tag":"wdth", "name": "Width", "values": [ ... ] }
        ]

    Alternately, to allow different STAT table entries for each font, the ``stat``
    parameter may be a dictionary, whose keys are source IDs (usually source
    filenames) corresponding to the appropriate entry in the ``varfonts``
    dictionary and whose values are the list of axis dictionaries for the font.
    Note that in this case, the axes list is passed to ``buildStatTable`` with
    no further manipulation, meaning that if you want an ``ital`` axis, you
    should specify it manually as part of the dictionary.

    For example::

        stat = {
            "Font[wght].ttf": [
                { "tag":"wdth", "name": "Width", "values": [ ... ] },
                { "tag":"ital", "name": "Italic", "values": [ ... ] }
            ],
            "Font-Italic[wght].ttf": [
                { "tag":"wdth", "name": "Width", "values": [ ... ] },
                { "tag":"ital", "name": "Italic", "values": [ ... ] }
            ]
        }
    """
    assert all("fvar" in f for f in varfonts)
    # Check we have no italic
    if isinstance(stat, list):
        if has_italic is None:
            has_italic = any(font_is_italic(f) for f in varfonts)
        if has_italic:
            for ax in stat:
                if ax["tag"] == "ital":
                    raise ValueError("ital axis should not appear in stat config")
                for av in ax.get("values", []):
                    av_name = av.get("name")
                    if not isinstance(av_name, str):
                        raise ValueError(
                            f"Axis value name must be a string, got {type(av_name)}: {av_name}"
                        )
            ital_stat_for_roman = {
                "name": "Italic",
                "tag": "ital",
                "values": [dict(value=0, name="Roman", flags=0x2, linkedValue=1)],
            }
            ital_stat_for_italic = {
                "name": "Italic",
                "tag": "ital",
                "values": [dict(value=1, name="Italic")],
            }

            stat.append({})  # We will switch this entry between Roman and Italic

    for ttFont in varfonts:
        filename = os.path.basename(ttFont.reader.file.name)
        if isinstance(stat, dict):
            if filename not in stat:
                raise ValueError("Filename %s not found in stat dictionary" % filename)
            this_stat = stat[filename]
        else:
            if has_italic:
                if font_is_italic(ttFont):
                    stat[-1] = ital_stat_for_italic
                else:
                    stat[-1] = ital_stat_for_roman
            this_stat = stat

        if isinstance(locations, dict):
            if filename not in locations:
                raise ValueError("Filename %s not found in locations" % filename)
            locations = locations[filename]
        buildStatTable(ttFont, this_stat, locations=locations)
