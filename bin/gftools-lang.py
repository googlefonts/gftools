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
from google.protobuf import text_format
from hyperglot import languages
from hyperglot import parse
from hyperglot import VALIDITYLEVELS
from lxml import etree
from urllib import request
import csv
import enum
import glob
import os
import pathlib
import re
import ssl
import tempfile
import unicodedata2 as uni
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

        alt_code = lang_code + '_' + script_code

        if alt_code not in lang_populations and not primary_script_found:
          key = lang_code
          primary_script_found = True
        else:
          key = alt_code

        if alt_code in lang_names:
          display_name = lang_names[alt_code]
        elif key in lang_names:
          display_name = lang_names[key]
        elif lang_code in lang_names:
          display_name = '{lang}, {script}'.format(lang=lang_names[lang_code], script=script_names[script_code])
        else:
          warnings.warn('Missing display name for language: ' + lang_code)
          display_name = None

        population = lang_populations[key] or 0
        aliases = lang_aliases[alt_code] or lang_aliases[lang_code] or []
        langs[key] = self.Language(key, lang_code, script_code, aliases, display_name, population, historical)
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
      if lang_code not in self.langs:
        warnings.warn('Unable to find language when setting region info: ' + lang_code)
        continue
      regions = lang_regions[lang_code]
      self.langs[lang_code].SetRegions(regions)

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
      if udhr.bcp47 in self._udhr_map and self._udhr_map[udhr.bcp47].stage > udhr.stage:
        w = 'Skipping UDHR "{other}" in favor of "{this}"'.format(other=self._udhr_map[udhr.bcp47].name, this=udhr.name)
        warnings.warn(w)
        continue
      self._udhr_map[udhr.bcp47] = udhr

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
    return [self.Udhr(udhr_data, self._zip_dir) for udhr_data in root.xpath('*')]

  def _LoadUdhrTranslation(self, udhr):
    filename = 'udhr_{key}.xml'.format(key=udhr.key)
    path = os.path.join(self._zip_dir.name, filename)
    if os.path.exists(path):
      return etree.parse(path)
    return None

  def GetUdhrs(self, min_stage=0):
    return [udhr for udhr in self._udhrs if udhr.stage >= min_stage]

  def GetUdhr(self, lang, min_stage=0):
    lang_code = lang.id
    alt_code = lang_code + '_' + lang.script_code
    if lang_code in SUPPLEMENTAL_ALIASES:
      alias = SUPPLEMENTAL_ALIASES[lang_code]
      if alias in self._udhr_map and self._udhr_map[alias].stage >= min_stage:
        return self._udhr_map[alias]
    if alt_code in self._udhr_map and self._udhr_map[alt_code].stage >= min_stage:
      return self._udhr_map[alt_code]
    if lang_code in self._udhr_map and self._udhr_map[lang_code].stage >= min_stage:
      return self._udhr_map[lang_code]
    return None

  def HasUdhr(self, lang, min_stage=0):
    lang_code = lang.id
    alt_code = lang_code + '_' + lang.script_code
    if lang_code in SUPPLEMENTAL_ALIASES:
      alias = SUPPLEMENTAL_ALIASES[lang_code]
      if alias in self._udhr_map and self._udhr_map[alias].stage >= min_stage:
        return True
    if alt_code in self._udhr_map and self._udhr_map[alt_code].stage >= min_stage:
      return True
    if lang_code in self._udhr_map and self._udhr_map[lang_code].stage >= min_stage:
      return True
    return False

  class Udhr():

    def __init__(self, udhr_data, zip_dir):
      self.key = udhr_data.get('f')
      self.iso639_3 = udhr_data.get('iso639-3')
      self.iso15924 = udhr_data.get('iso15924')
      self.bcp47 = udhr_data.get('bcp47').replace('-', '_')
      self.direction = udhr_data.get('dir')
      self.ohchr = udhr_data.get('ohchr')
      self.stage = int(udhr_data.get('stage'))
      self.loc = udhr_data.get('loc')
      self.name = udhr_data.get('n')

    def Parse(self, translation_data):
      if translation_data is None or self.stage < 2:
        return

      self.title = None
      if translation_data.find('./{*}title') is not None:
        self.title = translation_data.find('./{*}title').text

      preamble_data = translation_data.find('./{*}preamble')
      self.preamble = None
      if preamble_data is not None:
        if preamble_data.find('./{*}title') is not None:
          self.preamble = {
              'title':
                  preamble_data.find('./{*}title').text,
              'content': [
                  para.text for para in preamble_data.findall('./{*}para')
                      ],
          }

      articles_data = translation_data.findall('./{*}article')
      self.articles = []
      for article_data in articles_data:
        article = {
            'id':
                int(article_data.get('number')),
            'title':
                article_data.find('./{*}title').text,
            'content': [
                para.text for para in article_data.findall('./{*}para')
                    ],
        }
        self.articles.append(article)

    def GetSampleTexts(self):
      extractor = UdhrTranslations.SampleTextExtractor(self)
      return extractor.GetSampleTexts()

  class SampleTextExtractor():

    class TextType(enum.Enum):
      GLYPHS = 1
      WORD = 2
      PHRASE = 3
      SENTENCE = 4
      PARAGRAPH = 5
      PASSAGE = 6

    def __init__(self, udhr):
      self._udhr = udhr
      self._glyphs = iter(self._GetGlyphs())
      self._words = iter(self._GetWords())
      self._paragraphs = iter(self._GetParagraphs())
      self._phrase_history = set()

      self._non_word_regex = re.compile(r'[^\w]+')
      self._space_regex = re.compile(r'\s+')
      self._non_word_space_regex = re.compile(r'[^\w\s]+')

    def _DisplayLength(self, s):
      """Returns length of given string. Omits combining characters."""
      return len(self._non_word_space_regex.sub('', s))

    def _GetGlyphs(self):
      seen = set()
      for article in self._udhr.articles:
        for para in article['content']:
          for ch in self._non_word_regex.sub('', para):
            ch = ch.lower()
            if ch not in seen:
              seen.add(ch)
              yield ch

    def _GetWords(self):
      if self._space_regex.search(self._udhr.articles[0]['content'][0]) is not None:
        splitter = self._space_regex
      else:
        splitter = self._non_word_regex

      seen = set()
      for article in self._udhr.articles:
        for para in article['content']:
          for s in splitter.split(para):
            if s not in seen:
              seen.add(s)
              yield s

    def _GetParagraphs(self):
      if self._udhr.preamble is not None:
        for para in self._udhr.preamble['content']:
          yield para
      for article in self._udhr.articles:
        for para in article['content']:
          yield para

    def _ExtractGlyphs(self, min_chars, max_chars):
      s = ''
      for ch in self._glyphs:
        s += ch.upper()
        if len(s) >= min_chars:
          break
        if ch != ch.upper():
          s += ch
          if len(s) >= min_chars:
            break
      return s

    def _ExtractWord(self, min_chars, max_chars):
      for iterator in [self._words, self._GetWords()]:
        for w in iterator:
          if w is None:
            continue
          if min_chars <= self._DisplayLength(w) <= max_chars:
            return w
      raise Exception('Unable to extract word: ' + self._udhr.key)

    def _ExtractPhrase(self, min_chars, max_chars):
      for iterator in [self._paragraphs, self._GetParagraphs()]:
        for para in iterator:
          if para is None:
            continue
          if self._space_regex.search(para) is not None:
            regex = self._space_regex
          else:
            regex = self._non_word_regex
          for match in regex.finditer(para, min_chars):
            phrase = para[:match.start()]
            p_size = self._DisplayLength(phrase)
            if p_size > max_chars:
              break
            if min_chars <= p_size and phrase not in self._phrase_history:
              self._phrase_history.add(phrase)
              return phrase
      raise Exception('Unable to extract phrase: ' + self._udhr.key)

    def _ExtractSentence(self, min_chars, max_chars):
      # Sentence delimination may differ between scripts, so tokenizing on spaces
      # would be unreliable. Prefer to use _ExtractPhrase.
      return self._ExtractPhrase(min_chars, max_chars)

    def _ExtractParagraph(self, min_chars, max_chars):
      for iterator in [self._paragraphs, self._GetParagraphs()]:
        for para in iterator:
          if para is None:
            continue
          if min_chars <= self._DisplayLength(para) <= max_chars:
            return para
      # Paragraphs likely insufficient length; try combining into passages
      return self._ExtractPassage(min_chars, max_chars)

    def _ExtractPassage(self, min_chars, max_chars):
      p = []
      for iterator in [self._paragraphs, self._GetParagraphs()]:
        for para in iterator:
          if para is None:
            continue
          p.append(para)
          p_size = self._DisplayLength(' '.join(p))
          if max_chars < p_size:
            p.pop()
          elif min_chars <= p_size:
            return '\n'.join(p)
      return self._ExtractPhrase(min_chars, max_chars)

    def _Get(self, text_type, **kwargs):
      if 'char_count' in kwargs:
        min_chars = kwargs['char_count']
        max_chars = kwargs['char_count']
      else:
        min_chars = kwargs['min_chars']
        max_chars = kwargs['max_chars']
      if text_type == self.TextType.GLYPHS:
        return self._ExtractGlyphs(min_chars, max_chars)
      if text_type == self.TextType.WORD:
        return self._ExtractWord(min_chars, max_chars)
      if text_type == self.TextType.PHRASE:
        return self._ExtractPhrase(min_chars, max_chars)
      if text_type == self.TextType.SENTENCE:
        return self._ExtractSentence(min_chars, max_chars)
      if text_type == self.TextType.PARAGRAPH:
        return self._ExtractParagraph(min_chars, max_chars)
      if text_type == self.TextType.PASSAGE:
        return self._ExtractPassage(min_chars, max_chars)
      raise Exception('Unsupported text type: ' + text_type)

    def GetSampleTexts(self):
      sample_text = fonts_public_pb2.SampleTextProto()
      sample_text.masthead_full = self._Get(self.TextType.GLYPHS, char_count = 4)
      sample_text.masthead_partial = self._Get(self.TextType.GLYPHS, char_count = 2)
      sample_text.styles = self._Get(self.TextType.PHRASE, min_chars = 40, max_chars = 60)
      sample_text.tester = self._Get(self.TextType.PHRASE, min_chars = 60, max_chars = 90)
      sample_text.poster_sm = self._Get(self.TextType.PHRASE, min_chars = 10, max_chars = 15)
      sample_text.poster_md = self._Get(self.TextType.PHRASE, min_chars = 8, max_chars = 12)
      sample_text.poster_lg = self._Get(self.TextType.WORD, min_chars = 3, max_chars = 8)
      sample_text.specimen_48 = self._Get(self.TextType.SENTENCE, min_chars = 60, max_chars = 70)
      sample_text.specimen_36 = self._Get(self.TextType.PARAGRAPH, min_chars = 100, max_chars = 120)
      sample_text.specimen_32 = self._Get(self.TextType.PARAGRAPH, min_chars = 140, max_chars = 180)
      sample_text.specimen_21 = self._Get(self.TextType.PASSAGE, min_chars = 300, max_chars = 500)
      sample_text.specimen_16 = self._Get(self.TextType.PASSAGE, min_chars = 550, max_chars = 750)
      return sample_text


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
  if udhrs.HasUdhr(lang, min_stage=4):
    return udhrs.GetUdhr(lang, min_stage=4).GetSampleTexts()

  # Find a fallback language – largest population with same script(s)
  fallback = None
  population = -1
  for fallback_lang_code in cldr.langs:
    fallback_lang = cldr.langs[fallback_lang_code]
    p = fallback_lang.population
    if lang.script_code == fallback_lang.script_code and \
        udhrs.HasUdhr(fallback_lang, min_stage=4) and \
        p > population:
      fallback = fallback_lang_code
      population = p

  if fallback is None:
    warnings.warn('Unable to find sample text fallback: ' + lang_code)
    return None

  sample_text = fonts_public_pb2.SampleTextProto()
  sample_text.fallback_language = fallback
  return sample_text


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

  if FLAGS.mark_historical_languages:
    _MarkHistoricalLanguages()

  if FLAGS.report:
    print('Writing insights report...')
    _WriteReport(out_dir)


if __name__ == '__main__':
  app.run(main)
