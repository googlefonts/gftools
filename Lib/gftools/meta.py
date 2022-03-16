"""Generate meta table for a font

This module exports the function "gen_meta_table" which can be used to
add a meta table designating supported and/or design scripts/languages.
"""
from fontTools.ttLib import TTFont, newTable
import os
import logging
import yaml
import re
from langcodes import Language
from langcodes.tag_parser import LanguageTagError
from langcodes.data_dicts import VALIDITY

__all__ = ["gen_meta_table"]


log = logging.getLogger(__name__)


def gen_meta_table(ttFont, config):
    """Generates a meta table from a configuration dictionary.

    Args:
        ttFont: a TTFont instance
        config: a dictionary containing ``slng``/``dlng`` keys
    """
    assert isinstance(config, dict)
    if "meta" in ttFont:
        meta = ttFont["meta"]
        log.warning("meta table already found; merging configuration values!")
    else:
        ttFont["meta"] = meta = newTable("meta")
    for key in ["slng", "dlng"]:
        if key not in config:
            continue
        values = config[key]
        if isinstance(values, str):
            values = re.split(r",\s*", values)
        if key in meta.data:
            values.extend(re.split(r",\s*", meta.data[key]))
        value = _language_list_to_string(values)
        meta.data[key] = value


def _language_list_to_string(values):
    return ", ".join(
        sorted([value for value in set(values) if _validate_scriptlangtag(value)])
    )


def _validate_scriptlangtag(value):
    try:
        code = Language.get(value, normalize=False)
    except LanguageTagError:
        log.warning(f"Skipping unparsable script/lang tag '{value}'")
        return False
    if code.language and len(code.language) == 4 and code.language.isalpha():
        code.script = code.language.title()
        code.language = None
    if not code.script:
        log.warning(
            f"meta table script/lang tags must have a script component, '{value}' does not"
        )
        return False
    if code.language and not VALIDITY.fullmatch(code.language):
        log.warning(f"Invalid language code '{code.language}' in '{value}'")
    if not VALIDITY.fullmatch(code.script):
        log.warning(f"Invalid script code '{code.script}' in '{value}'")
    if code.territory and not VALIDITY.fullmatch(code.territory):
        log.warning(f"Invalid territory code '{code.territory}' in '{value}'")
    if code.extlangs:
        for extlang in code.extlangs:
            if not VALIDITY.fullmatch(extlang):
                log.warning(f"Invalid extended language code '{extlang}' in '{value}'")
                return False
    if code.variants:
        for variant in code.variants:
            if not VALIDITY.fullmatch(variant):
                log.warning(f"Invalid variant code '{variant}' in '{value}'")
                return False
    return code.is_valid()
