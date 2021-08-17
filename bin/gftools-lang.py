#!/usr/bin/env python3
"""
gftools lang

Generates Language/Region metadata.

CLDR info is supplemented with Hyperglot
(https://github.com/rosettatype/hyperglot), which pulls from other data sources
and consequently has a more complete set of language metadata.

Usage:

# Standard usage. Output lang metadata to a dir. Does not overwrite existing data.
gftools lang --out . -l

# Generate a report with insights about data and potential metadata holes.
gftools lang --out . -r

"""

from absl import app
from absl import flags
from collections import defaultdict
from collections import deque
from fontTools.ttLib import TTFont
from gftools import fonts_public_pb2
from gftools.util.udhr import Udhr
from google.protobuf import text_format
from hyperglot import languages
from hyperglot import parse
from hyperglot import VALIDITYLEVELS
from lxml import etree
from urllib import request
import csv
import glob
import os
import pathlib
import re
import ssl
import tempfile
import warnings
import zipfile


DIR = os.path.dirname(os.path.realpath(__file__))
NOTO_DIR = os.path.join(DIR, 'noto-unhinted')
OUTPUT_DIR = os.path.join(DIR, 'data')
REGIONS_CSV = os.path.join(OUTPUT_DIR, 'regions.csv')
LANGUAGES_CSV = os.path.join(OUTPUT_DIR, 'languages.csv')
NOTO_CSV = os.path.join(OUTPUT_DIR, 'noto.csv')
TEXT_SAMPLES_CSV = os.path.join(OUTPUT_DIR, 'text_samples.csv')

# Hyperglot language support params
SUPPORT = 'base'
VALIDITY = VALIDITYLEVELS[1]  # draft
DECOMPOSED = False
MARKS = False
INCLUDE_ALL_ORTHOGRAPHIES = True
INCLUDE_HISTORICAL = True
INCLUDE_CONSTRUCTED = True

"""Additional aliases mapping from CLDR to Hyperglot/UDHR."""
SUPPLEMENTAL_ALIASES = {
    'ff': 'fuf',  # Fulah to Pular
    'ff_Adlm': 'fuf_Adlm',  # Fulah (Adlam) to Pular (Adlam)
    'fil': 'tgl',  # Filipino to Tagalog (Latin)
    'fil_Tglg': 'tgl_Tglg',  #Filipino to Tagalog (Tagalog)
    'prd': 'pes',  # Parsi-Dari to Iranian Persian
    'uz_Arab': 'uzs',  # Uzbek (Arabic) to Southern Uzbek
}

# CLDR
CLDR_ZIP_URL = 'http://unicode.org/Public/cldr/latest/core.zip'
SUPPLEMENTAL_DATA_XML_PATH = 'common/supplemental/supplementalData.xml'
SUPPLEMENTAL_METADATA_XML_PATH = 'common/supplemental/supplementalMetadata.xml'
LANG_XML_PATH = 'common/main/{lang_code}.xml'
EN = 'en'
WORLD_REGION = '001'
NO_COMMENTS_XML_PARSER = etree.XMLParser(remove_comments=True)
UNDEFINED = 'und'  # undefined lang code

LANGUAGE_OVERRIDES = {
  'abq': {
    'name': 'Abaza',
  },
  'aii': {
    'name': 'Assyrian Neo-Aramaic',
    'preferred_name': 'Assyrian',
  },
  'bn': {
    'name': 'Bengali',
    'autonym': 'বাংলা',
  },
  'eky': {
    'name': 'Eastern Kayah',
  },
  'ett': {
    'name': 'Etruscan',
  },
  'evn': {
    'name': 'Evenki',
  },
  'kyu': {
    'name': 'Western Kayah',
  },
  'myz': {
    'name': 'Mandaic',
  },
  'osc': {
    'name': 'Oscan',
  },
  'otk': {
    'name': 'Old Turkish',
  },
  'smp': {
    'name': 'Samaritan',
  },
  'xcr': {
    'name': 'Carian',
  },
  'xlc': {
    'name': 'Lycian',
  },
  'xld': {
    'name': 'Lydian',
  },
  'xpr': {
    'name': 'Parthian',
  },
  'xsa': {
    'name': 'Sabaean',
  },
  'xum': {
    'name': 'Umbrian',
  },
}

SCRIPT_OVERRIDES = {
  'Cans': {
    'name': 'Unified Canadian Aboriginal Syllabics',
  },
  'Mtei': {
    'name': 'Meetei Mayek',
  },
}

# UDHR
UHDR_URL_TEMPLATE = 'https://www.un.org/{language_code}/universal-declaration-human-rights/'
UDHR_TRANSLATIONS_ZIP_URL = 'https://www.unicode.org/udhr/assemblies/udhr_xml.zip'
INDEX_XML = 'index.xml'

FLAGS = flags.FLAGS
flags.DEFINE_string('out', None, 'Path to lang metadata package', short_name='o')
flags.mark_flag_as_required('out')
flags.DEFINE_boolean('overwrite_sample_text', False, 'Whether to overwrite sample text with any generated from UDHR translations', short_name='w')
flags.DEFINE_bool('gen_lang', False, 'Whether to generate the lang metadata package', short_name='l')
flags.DEFINE_bool('report', False, 'Whether to output a report of lang metadata insights', short_name='r')
flags.DEFINE_string('noto_root', None, 'Path to noto root', short_name='n')
flags.DEFINE_bool('mark_historical_languages', False, 'Whether to update the lang metadata package to specify historical scripts', short_name='h')


class Cldr():
  """Exposes information of interest buried in the CLDR.

  Specifically useful are language and region info.

  See more at http://cldr.unicode.org/.
  """

  def _GetLangXmlPath(lang_code):
    return LANG_XML_PATH.format(lang_code=lang_code)

  def __init__(self):
    self._zip_dir = tempfile.TemporaryDirectory()
    self._DownloadCldrZip()

    lang_index = self._ParseLanguageIndex()
    lang_historical = self._ParseHistoricalLanguages()
    lang_aliases = self._ParseLanguageAliases()
    lang_names, script_names, region_names = self._ParseDisplayNamesFromEnXml()
    lang_names_supplement, region_names_supplement = self._ParseDisplayNamesFromSupplementalData()
    lang_names.update(lang_names_supplement)
    region_names.update(region_names_supplement)
    lang_names.update({o: LANGUAGE_OVERRIDES[o]['name'] for o in LANGUAGE_OVERRIDES if 'name' in LANGUAGE_OVERRIDES[o]})
    script_names.update({s: SCRIPT_OVERRIDES[s]['name'] for s in SCRIPT_OVERRIDES if 'name' in SCRIPT_OVERRIDES[s]})
    region_populations, lang_populations, lang_regions = self._ParseLanguageRegionInfo()
    region_groups = self._ParseRegionGroups()

    self.langs = self._CompileLanguages(lang_index, lang_historical, lang_aliases, lang_names, lang_populations, script_names)
    self.regions = self._CompileRegions(region_names, region_populations)
    self.region_groups = self._CompileRegionGroups(region_groups, region_names)
    self.scripts = self._CompileScripts(lang_index, script_names)
    self.lang_regions = lang_regions
    self._SetRegionsOnLanguages(lang_regions)
    self._SetExemplarCharsOnLanguages()

  def __enter__(self):
    return self

  def __exit__(self, exc_type, exc_value, traceback):
    self._zip_dir.cleanup()

  def _DownloadCldrZip(self):
    with tempfile.NamedTemporaryFile(suffix='.zip') as zip_file:
      request.urlretrieve(CLDR_ZIP_URL, zip_file.name)
      with zipfile.ZipFile(zip_file.name, 'r') as zip_ref:
        zip_ref.extractall(self._zip_dir.name)

  def _ParseLanguageIndex(self):
    root = etree.parse(os.path.join(self._zip_dir.name,
                       SUPPLEMENTAL_DATA_XML_PATH), parser=NO_COMMENTS_XML_PARSER)
    language_data = root.find('.//{*}languageData')

    lang_index = {}
    for l in language_data:
      l_id = l.get('type')
      scripts = [] if l.get('scripts') is None else l.get('scripts').split(' ')
      if l_id in lang_index:
        lang_index[l_id].extend(scripts)
      else:
        lang_index[l_id] = scripts
    return lang_index

  def _ParseHistoricalLanguages(self):
    root = etree.parse(os.path.join(self._zip_dir.name,
                       SUPPLEMENTAL_DATA_XML_PATH), parser=NO_COMMENTS_XML_PARSER)
    language_data = root.find('.//{*}languageData')

    historical = {}
    for l in language_data:
      if l.get('scripts') is None:
        continue
      if l.get('alt') == 'secondary':
        l_id = l.get('type')
        scripts = [] if l.get('scripts') is None else l.get('scripts').split(' ')
        if l_id in historical:
          historical[l_id].extend(scripts)
        else:
          historical[l_id] = scripts
    return historical

  def _ParseLanguageAliases(self):
    root = etree.parse(os.path.join(self._zip_dir.name,
                       SUPPLEMENTAL_METADATA_XML_PATH), parser=NO_COMMENTS_XML_PARSER)
    aliases_data = root.find('.//{*}alias').xpath('languageAlias')
    aliases = defaultdict(lambda: set())
    for alias_data in aliases_data:
      aliases[alias_data.get('replacement')].add(alias_data.get('type'))
    return aliases

  def _ParseDisplayNamesFromEnXml(self):
    root = etree.parse(os.path.join(self._zip_dir.name,
                       Cldr._GetLangXmlPath(EN)), parser=NO_COMMENTS_XML_PARSER)
    languages_data = root.find('.//{*}languages')
    scripts_data = root.find('.//{*}scripts')
    regions_data = root.find('.//{*}territories')

    lang_names = {lang.get('type'): lang.text for lang in languages_data if lang.get('alt') != 'long'}
    script_names = {script.get('type'): script.text for script in scripts_data}
    region_names = {region.get('type'): region.text for region in regions_data}

    return lang_names, script_names, region_names

  def _ParseDisplayNamesFromSupplementalData(self):
    root = etree.parse(os.path.join(
        self._zip_dir.name, SUPPLEMENTAL_DATA_XML_PATH))
    regions_data = root.find('.//{*}territoryInfo')

    lang_names = {}
    region_names = {}
    for region_data in regions_data:
      region_code = region_data.get('type')
      region_names[region_code] = region_data[0].text
      assert len(region_data) % 2 == 1, 'Is there a node without a comment label?'
      for i in range(1, len(region_data), 2):
        lang_code = region_data[i].get('type')
        lang_names[lang_code] = region_data[i+1].text
    return lang_names, region_names

  def _ParseLanguageRegionInfo(self):
    root = etree.parse(os.path.join(self._zip_dir.name,
                       SUPPLEMENTAL_DATA_XML_PATH), parser=NO_COMMENTS_XML_PARSER)
    regions_data = root.find('.//{*}territoryInfo')

    region_populations = defaultdict(lambda: 0)
    lang_populations = defaultdict(lambda: 0)
    lang_regions = defaultdict(lambda: set())

    for region_data in regions_data:
      if not len(region_data):
        # Skip pseudo entries like 'ZZ' (Unknown Region)
        continue
      region_code = region_data.get('type')
      region_population = int(region_data.get('population'))
      region_populations[region_code] = region_population
      for lang_population_data in region_data:
        lang_code = lang_population_data.get('type')
        population_percent = float(
            lang_population_data.get('populationPercent'))
        lang_populations[lang_code] += region_population * \
            population_percent / 100
        lang_regions[lang_code].add(region_code)

    return region_populations, lang_populations, lang_regions

  def _ParseRegionGroups(self):
    root = etree.parse(os.path.join(self._zip_dir.name,
                       SUPPLEMENTAL_DATA_XML_PATH), parser=NO_COMMENTS_XML_PARSER)
    territory_containment_data = root.find('.//{*}territoryContainment')
    groups_data = territory_containment_data.xpath('group[not(@status)]')
    raw_groups = {group_data.get('type'): group_data.get(
        'contains').split(' ') for group_data in groups_data}

    region_groups = {}

    # Expand region groups
    for group in raw_groups[WORLD_REGION]:
      regions = deque([group])
      i = 0
      while i < len(regions):
        if regions[i] in raw_groups:
          regions.extend(raw_groups[regions[i]])
          del regions[i]
        else:
          i += 1
      region_groups[group] = set(regions)

    return region_groups

  def _ParseExemplarCharacters(self, lang_code):
    xml_file = os.path.join(self._zip_dir.name, Cldr._GetLangXmlPath(lang_code))
    if not os.path.isfile(xml_file):
      return {}
    root = etree.parse(xml_file, parser=NO_COMMENTS_XML_PARSER)
    characters_data = root.find('.//{*}characters')
    if characters_data is None:
      return {}

    exemplar_chars = {}
    for exemplar_characters_data in characters_data.xpath('exemplarCharacters'):
      category = exemplar_characters_data.get('type') or 'base'
      chars = exemplar_characters_data.text
      chars = chars[1:len(chars)-1]
      exemplar_chars[category] = chars
    return exemplar_chars

  def _CompileLanguages(self, lang_index, lang_historical, lang_aliases, lang_names, lang_populations, script_names):
    langs = {}
    for lang_code in lang_index:
      primary_script_found = False
      for script_code in lang_index[lang_code]:
        historical = False
        if lang_code in lang_historical:
          if len(lang_historical[lang_code]) == 0:
            # All scripts are historical for language
            historical = True
          else:
            historical = script_code in lang_historical[lang_code]

        key = lang_code + '_' + script_code
        if key not in lang_populations and not primary_script_found:
          alt_code = lang_code
          primary_script_found = True
        else:
          alt_code = key

        if key in lang_names:
          display_name = lang_names[key]
        elif alt_code in lang_names:
          display_name = lang_names[alt_code]
        elif lang_code in lang_names:
          display_name = '{lang}, {script}'.format(lang=lang_names[lang_code], script=script_names[script_code])
        else:
          warnings.warn('Missing display name for language: ' + lang_code)
          display_name = None

        population = lang_populations[key] or 0
        aliases = lang_aliases[key] or lang_aliases[lang_code] or []
        langs[alt_code] = self.Language(key, lang_code, script_code, aliases, display_name, population, historical)
    return langs

  def _CompileRegions(self, region_names, region_populations):
    regions = {}
    for region_code in region_populations:
      population = region_populations[region_code]
      display_name = region_names[region_code]
      assert display_name is not None, 'Missing display name for region: ' + region_code
      regions[region_code] = self.Region(region_code, display_name, population)
    return regions

  def _CompileRegionGroups(self, region_groups, region_names):
    return {region_names[group]: region_groups[group] for group in region_groups}

  def _CompileScripts(self, lang_index, script_names):
    script_codes = {script for lang_code in lang_index for script in lang_index[lang_code]}
    return {script_code: script_names[script_code] for script_code in script_codes if script_code in script_names}

  def _SetRegionsOnLanguages(self, lang_regions):
    for lang_code in lang_regions:
      lang = None
      if lang_code in self.langs:
        lang = self.langs[lang_code]
      if lang is None:
        print ('Looking very hard for language: ' + lang_code)
        for l in self.langs.values():
          if l.lang_code == lang_code:
            print (l)
        warnings.warn('Unable to find language when setting region info: ' + lang_code)
        continue
      lang.SetRegions(lang_regions[lang_code])

  def _SetExemplarCharsOnLanguages(self):
    for lang_code in self.langs:
      exemplar_chars = self._ParseExemplarCharacters(lang_code)
      self.langs[lang_code].SetExemplarChars(exemplar_chars)

  class Language():

    def __init__(self, key, lang_code, script_code, aliases, display_name, population, historical):
      self.id = key
      self.lang_code = lang_code
      self.script_code = script_code
      self.aliases = aliases
      self.name = display_name
      self.population = int(population)
      self.historical = historical
      self.regions = None
      self.exemplar_chars = None

    def SetRegions(self, regions):
      assert self.regions is None, 'Regions already set on language: ' + self.id
      self.regions = regions

    def SetExemplarChars(self, exemplar_chars):
      assert self.exemplar_chars is None, 'Exemplar chars already set on language: ' + self.id
      self.exemplar_chars = exemplar_chars

  class Region():

    def __init__(self, region_code, display_name, population):
      self.id = region_code
      self.name = display_name
      self.population = int(population)


class UdhrTranslations():
  """Extracts text samples from UDHR translations.

  Translations exist for myriad languages at varying levels of support. The tool
  focuses on Stage 4+ translations for which the UDHR translation has a reliable
  amount of content and structure for scraping text samples.

  See more at https://www.unicode.org/udhr.
  """

  def __init__(self):
    self._zip_dir = tempfile.TemporaryDirectory()
    self._DownloadUdhrTranslationsZip()
    self._udhrs = self._ParseUdhrs()
    self._udhr_map = {}

    for udhr in self._udhrs:
      udhr.Parse(self._LoadUdhrTranslation(udhr))
      if udhr.iso639_3 != 'yue': continue
      key = udhr.iso639_3 + '_' + udhr.iso15924
      if key in self._udhr_map and self._udhr_map[key].stage > udhr.stage:
        w = 'Skipping UDHR "{other}" in favor of "{this}"'.format(other=self._udhr_map[udhr.key].name, this=udhr.name)
        warnings.warn(w)
        continue
      self._udhr_map[key] = udhr

  def __enter__(self):
    return self

  def __exit__(self, exc_type, exc_value, traceback):
    self._zip_dir.cleanup()

  def _DownloadUdhrTranslationsZip(self):
    with tempfile.NamedTemporaryFile(suffix='.zip') as zip_file:
      # Disable SSL verification
      ssl._create_default_https_context = ssl._create_unverified_context
      request.urlretrieve(UDHR_TRANSLATIONS_ZIP_URL, zip_file.name)
      with zipfile.ZipFile(zip_file.name, 'r') as zip_ref:
        zip_ref.extractall(self._zip_dir.name)

  def _ParseUdhrs(self):
    root = etree.parse(os.path.join(self._zip_dir.name, INDEX_XML))
    udhrs = []
    for udhr_data in root.xpath('*'):
      udhr = Udhr(
          key=udhr_data.get('f'),
          iso639_3=udhr_data.get('iso639-3'),
          iso15924=udhr_data.get('iso15924'),
          bcp47=udhr_data.get('bcp47').replace('-', '_'),
          direction=udhr_data.get('dir'),
          ohchr=udhr_data.get('ohchr'),
          stage=int(udhr_data.get('stage')),
          loc=udhr_data.get('loc'),
          name=udhr_data.get('n'))
      udhrs.append(udhr)
    return udhrs

  def _LoadUdhrTranslation(self, udhr):
    filename = 'udhr_{key}.xml'.format(key=udhr.key)
    path = os.path.join(self._zip_dir.name, filename)
    if os.path.exists(path):
      return etree.parse(path)
    return None

  def GetUdhrs(self, min_stage=0):
    return [udhr for udhr in self._udhrs if udhr.stage >= min_stage]

  def GetUdhr(self, lang, min_stage=0):
    key = lang.lang_code + '_' + lang.script_code
    if key in SUPPLEMENTAL_ALIASES:
      alias = SUPPLEMENTAL_ALIASES[key]
      if alias in self._udhr_map and self._udhr_map[alias].stage >= min_stage:
        return self._udhr_map[alias]
    if key in self._udhr_map and self._udhr_map[key].stage >= min_stage:
      return self._udhr_map[key]
    return None

  def HasUdhr(self, lang, min_stage=0):
    key = lang.lang_code + '_' + lang.script_code
    print(self._udhr_map.keys())
    if key in SUPPLEMENTAL_ALIASES:
      alias = SUPPLEMENTAL_ALIASES[key]
      if alias in self._udhr_map and self._udhr_map[alias].stage >= min_stage:
        return True
    if key in self._udhr_map and self._udhr_map[key].stage >= min_stage:
      return True
    return False


def _GetHyperglotLanguage(lang, hyperglot_languages):
  lang_code = lang.lang_code
  if lang_code in hyperglot_languages:
    return hyperglot_languages[lang_code]
  for alias in lang.aliases:
    if alias in hyperglot_languages:
      return hyperglot_languages[alias]
  if lang_code in SUPPLEMENTAL_ALIASES and SUPPLEMENTAL_ALIASES[lang_code] in hyperglot_languages:
    return hyperglot_languages[SUPPLEMENTAL_ALIASES[lang_code]]
  for hg_lang in hyperglot_languages.values():
    if 'includes' in hg_lang and lang_code in hg_lang['includes']:
      return hg_lang
  warnings.warn('Unable to find language in hyperglot: ' + lang_code)
  return None


def _GetHyperglotOrtho(cldr, lang, hg_lang):
  if hg_lang is not None and 'orthographies' in hg_lang:
    for ortho in hg_lang['orthographies']:
      if ortho['script'] == cldr.scripts[lang.script_code]:
        return ortho
  warnings.warn('Unable to find orthography in hyperglot: ' + lang.id)
  return None


def _GetPreferredName(lang, hg_lang):
  if lang.id in LANGUAGE_OVERRIDES and 'preferred_name' in LANGUAGE_OVERRIDES[lang.id]:
    return LANGUAGE_OVERRIDES[lang.id]['preferred_name']
  if hg_lang is not None and 'preferred_name' in hg_lang:
    return hg_lang['preferred_name']
  return None


def _GetAutonym(cldr, lang, hg_lang):
  if lang.id in LANGUAGE_OVERRIDES and 'autonym' in LANGUAGE_OVERRIDES[lang.id]:
    return LANGUAGE_OVERRIDES[lang.id]['autonym']
  ortho = _GetHyperglotOrtho(cldr, lang, hg_lang)
  if ortho is not None and 'autonym' in ortho:
    return ortho['autonym']
  if hg_lang is not None and 'autonym' in hg_lang:
    return hg_lang['autonym']
  return None


def _GetExemplarCharacters(cldr, lang, hg_lang):
  exemplar_chars = fonts_public_pb2.ExemplarCharsProto()

  if hg_lang is not None and 'orthographies' in hg_lang:
    ortho = _GetHyperglotOrtho(cldr, lang, hg_lang)
    if ortho is not None:
      if 'base' in ortho:
        exemplar_chars.base = ortho['base']
      if 'auxiliary' in ortho:
        exemplar_chars.auxiliary = ortho['auxiliary']
      if 'marks' in ortho:
        exemplar_chars.marks = ortho['marks']
      if 'numerals' in ortho:
        exemplar_chars.numerals = ortho['numerals']
      if 'punctuation' in ortho:
        exemplar_chars.punctuation = ortho['punctuation']

  if 'base' in lang.exemplar_chars:
    exemplar_chars.base = lang.exemplar_chars['base']
  if 'auxiliary' in lang.exemplar_chars:
    exemplar_chars.auxiliary = lang.exemplar_chars['auxiliary']
  if 'marks' in lang.exemplar_chars:
    exemplar_chars.marks = lang.exemplar_chars['marks']
  if 'numbers' in lang.exemplar_chars:
    exemplar_chars.numerals = lang.exemplar_chars['numbers']
  if 'punctuation' in lang.exemplar_chars:
    exemplar_chars.punctuation = lang.exemplar_chars['punctuation']
  if 'index' in lang.exemplar_chars:
    exemplar_chars.index = lang.exemplar_chars['index']

  if text_format.MessageToString(exemplar_chars) == text_format.MessageToString(fonts_public_pb2.ExemplarCharsProto()):
    return None

  return exemplar_chars


def _GetSampleText(lang_code, cldr, udhrs):
  lang = cldr.langs[lang_code]
  if udhrs.HasUdhr(lang, min_stage=0):
    return udhrs.GetUdhr(lang, min_stage=0).GetSampleTexts()
  return None


def _IsHistorical(cldr_lang, hg_lang):
  if cldr_lang is not None and cldr_lang.historical:
    return True
  if hg_lang is not None and 'status' in hg_lang:
    return hg_lang['status'] == 'historical'
  return False


def _LoadLanguages(languages_dir):
  languages = {}
  for textproto_file in glob.iglob(os.path.join(languages_dir, '*.textproto')):
    with open(textproto_file, 'r', encoding='utf-8') as f:
      language = text_format.Parse(f.read(), fonts_public_pb2.LanguageProto())
      languages[language.id] = language
  return languages


def _LoadScripts(scripts_dir):
  scripts = {}
  for textproto_file in glob.iglob(os.path.join(scripts_dir, '*.textproto')):
    with open(textproto_file, 'r', encoding='utf-8') as f:
      script = text_format.Parse(f.read(), fonts_public_pb2.ScriptProto())
      scripts[script.id] = script
  return scripts


def _SupportedLanguages(font_path, languages):
  chars = _ParseFontChars(font_path)

  supported = []
  for lang in languages.values():
    if not lang.HasField('exemplar_chars') or not lang.exemplar_chars.HasField('base'):
      continue
    base = parse.parse_chars(lang.exemplar_chars.base,
                             decompose=False,
                             retainDecomposed=False)
    if set(base).issubset(chars):
      supported.append(lang)

  return supported


def _ParseFontChars(path):
  """
  Open the provided font path and extract the codepoints encoded in the font
  @return list of characters
  """
  font = TTFont(path, lazy=True)
  cmap = font["cmap"].getBestCmap()
  font.close()

  # The cmap keys are int codepoints
  return [chr(c) for c in cmap.keys()]


def _WriteProto(proto, path):
  with open(path, 'w', newline='') as f:
    textproto = text_format.MessageToString(proto, as_utf8=True)
    f.write(textproto)


def _WriteCsv(path, rows):
  with open(path, 'w', newline='') as csvfile:
    writer = csv.writer(csvfile, delimiter='\t', quotechar='"',
                        quoting=csv.QUOTE_MINIMAL)
    for row in rows:
      writer.writerow(row)


def _WriteRegionMetadata(cldr, out_dir):
  for r in cldr.regions.values():
    path = os.path.join(out_dir, r.id + '.textproto')
    if os.path.exists(path):
      continue

    region = fonts_public_pb2.RegionProto()
    region.id = r.id
    region.name = r.name
    region.population = r.population
    groups = [
        group for group in cldr.region_groups if r.id in cldr.region_groups[group]]
    assert len(groups) > 0, 'Region does not belong to any groups: ' + r.id
    region.region_group.extend(sorted(groups))
    _WriteProto(region, path)


def _WriteScriptMetadata(cldr, out_dir):
  for s in cldr.scripts:
    path = os.path.join(out_dir, s + '.textproto')
    if os.path.exists(path):
      continue
    script = fonts_public_pb2.ScriptProto()
    script.id = s
    script.name = cldr.scripts[s]
    _WriteProto(script, path)


def _WriteLanguageMetadata(cldr, out_dir):
  hyperglot_languages = languages.Languages()
  with UdhrTranslations() as udhrs:
    for lang_code in cldr.langs:
      path = os.path.join(out_dir, lang_code + '.textproto')
      if os.path.exists(path):
        continue

      lang = cldr.langs[lang_code]
      hg_lang = _GetHyperglotLanguage(lang, hyperglot_languages)

      language = fonts_public_pb2.LanguageProto()
      language.id = lang.id
      language.language = lang.lang_code
      language.script = lang.script_code
      language.population = lang.population

      name = lang.name
      if name is not None:
        language.name = name

      preferred_name = _GetPreferredName(lang, hg_lang)
      if preferred_name is not None:
        language.preferred_name = preferred_name

      autonym = _GetAutonym(cldr, lang, hg_lang)
      if autonym is not None:
        language.autonym = autonym

      if lang.regions is not None:
        language.region.extend(sorted(lang.regions))

      exemplar_chars = _GetExemplarCharacters(cldr, lang, hg_lang)
      if exemplar_chars is not None:
        language.exemplar_chars.MergeFrom(exemplar_chars)

      sample_text = _GetSampleText(lang_code, cldr, udhrs)
      if sample_text is not None:
        language.sample_text.MergeFrom(sample_text)

      _WriteProto(language, path)


def _OverwriteSampleText(cldr, out_dir):
  languages = _LoadLanguages(out_dir)
  with UdhrTranslations() as udhrs:
    udhr_map = {u.iso639_3 + '_' + u.iso15924: u for u in udhrs.GetUdhrs()}
    for l in languages.values():
      if not l.id.startswith('yue'): continue
      if l.id in udhr_map:
        udhr = udhr_map[l.id]
        path = os.path.join(out_dir, l.id + '.textproto')
        sample_text = udhr.GetSampleTexts()
        print(sample_text)
        l.sample_text.MergeFrom(sample_text)
        _WriteProto(l, path)


def _WriteReport(out_dir):
  rows = [['Language', '(name)', 'No name', 'No autonym', 'No exemplar chars', 'No sample text', 'Sample text fallback', '(name)']]

  languages = _LoadLanguages(os.path.join(out_dir, 'languages'))
  scripts = _LoadScripts(os.path.join(out_dir, 'scripts'))
  for lang in languages.values():
    row = [
      lang.id,
      '' if not lang.HasField('name') else lang.name,
      '' if lang.HasField('name') else 'X',
      '' if lang.HasField('autonym') else 'X',
      '' if lang.HasField('exemplar_chars') else 'X',
      '' if lang.HasField('sample_text') else 'X',
      '' if not lang.HasField('sample_text') or not lang.sample_text.HasField('fallback_language') else lang.sample_text.fallback_language,
      '' if not lang.HasField('sample_text') or not lang.sample_text.HasField('fallback_language') else languages[lang.sample_text.fallback_language].name or languages[lang.sample_text.fallback_language].id,
    ]
    rows.append(row)

  path = os.path.join(out_dir, 'report.csv')
  _WriteCsv(path, rows)

  if FLAGS.noto_root is not None:
    notos_without_lang = []
    notos_without_sample_text = []
    supported_without_sample_text = []
    for fontfile in glob.iglob(os.path.join(FLAGS.noto_root, '*-Regular.ttf')):
      family = os.path.basename(fontfile).replace('-Regular.ttf', '')
      supported = _SupportedLanguages(fontfile, languages)
      if len(supported) == 0:
        lang_hint = family.replace('Noto', '').replace('Sans', '').replace('Serif', '').replace('UI', '').replace('Unjoined', '').replace('Turkic', 'Turkish').lower()
        supported = []
        for lang in languages.values():
          if lang_hint in re.sub(r'[^\w]+', '', lang.name).lower():
            supported.append(lang)
          elif lang.script in scripts and lang_hint in re.sub(r'[^\w]+', '', scripts[lang.script].name).lower():
            supported.append(lang)
      if len(supported) == 0:
        notos_without_lang.append(family)
      elif all(not l.HasField('sample_text') for l in supported):
        notos_without_sample_text.append(family)
      [supported_without_sample_text.append(l.name or l.id) for l in supported if not l.HasField('sample_text') and l not in supported_without_sample_text]

    rows = [['Notos without lang support', 'Notos without sample text', 'Supported language without sample text']]
    for i in range(max(len(notos_without_lang), len(notos_without_sample_text), len(supported_without_sample_text))):
      row = [
        '' if i >= len(notos_without_lang) else notos_without_lang[i],
        '' if i >= len(notos_without_sample_text) else notos_without_sample_text[i],
        '' if i >= len(supported_without_sample_text) else supported_without_sample_text[i],
      ]
      rows.append(row)

    path = os.path.join(out_dir, 'support.csv')
    _WriteCsv(path, rows)


def _MarkHistoricalLanguages():
  langs = _LoadLanguages(os.path.join(FLAGS.out, 'languages'))
  hyperglot_languages = languages.Languages()
  with Cldr() as cldr:
    for lang in langs.values():
      cldr_lang = None if lang.id not in cldr.langs else cldr.langs[lang.id]
      hg_lang = None
      if cldr_lang is None:
        if lang.id in hyperglot_languages:
          hg_lang = hyperglot_languages[lang.language]
      else:
        hg_lang = _GetHyperglotLanguage(cldr_lang, hyperglot_languages)
      historical = _IsHistorical(cldr_lang, hg_lang)
      if historical:
        lang.historical = True
        _WriteProto(lang, os.path.join(FLAGS.out, 'languages', lang.id + '.textproto'))


def _LoadLanguages(languages_dir):
  langs = {}
  for textproto_file in glob.iglob(os.path.join(languages_dir, '*.textproto')):
    with open(textproto_file, 'r', encoding='utf-8') as f:
      language = text_format.Parse(f.read(), fonts_public_pb2.LanguageProto())
      langs[language.id] = language
  return langs


def main(argv):
  out_dir = FLAGS.out
  pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)

  if FLAGS.gen_lang:
    with Cldr() as cldr:
      print('Writing region metadata...')
      path = os.path.join(out_dir, 'regions')
      pathlib.Path(path).mkdir(parents=True, exist_ok=True)
      _WriteRegionMetadata(cldr, path)

      print('Writing script metadata...')
      path = os.path.join(out_dir, 'scripts')
      pathlib.Path(path).mkdir(parents=True, exist_ok=True)
      _WriteScriptMetadata(cldr, path)

      print('Writing language metadata...')
      path = os.path.join(out_dir, 'languages')
      pathlib.Path(path).mkdir(parents=True, exist_ok=True)
      _WriteLanguageMetadata(cldr, path)

  if FLAGS.overwrite_sample_text:
    with Cldr() as cldr:
      print ('Overwriting sample text...')
      path = os.path.join(out_dir, 'languages')
      pathlib.Path(path).mkdir(parents=True, exist_ok=True)
      _OverwriteSampleText(cldr, path)

  if FLAGS.mark_historical_languages:
    _MarkHistoricalLanguages()

  if FLAGS.report:
    print('Writing insights report...')
    _WriteReport(out_dir)


if __name__ == '__main__':
  app.run(main)
