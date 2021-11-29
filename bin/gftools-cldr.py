#!/usr/bin/env python3
"""Exposes information of interest buried in the CLDR.

Specifically useful are language and region info.

See more at http://cldr.unicode.org/.
"""

from collections import defaultdict
from collections import deque
import os
import tempfile
from urllib import request
from lxml import etree
import zipfile

CLDR_ZIP_URL = 'http://unicode.org/Public/cldr/latest/core.zip'
SUPPLEMENTAL_DATA_XML_PATH = 'common/supplemental/supplementalData.xml'
SUPPLEMENTAL_METADATA_XML_PATH = 'common/supplemental/supplementalMetadata.xml'
LANG_XML_PATH = 'common/main/{lang_code}.xml'
EN = 'en'
WORLD_REGION = '001'
NO_COMMENTS_XML_PARSER = etree.XMLParser(remove_comments=True)


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

    lang_aliases = self._ParseLanguageAliases()
    lang_names, region_names = self._ParseDisplayNamesFromEnXml()
    lang_names_supplement, region_names_supplement = self._ParseDisplayNamesFromSupplementalData()
    lang_names.update(lang_names_supplement)
    region_names.update(region_names_supplement)
    region_populations, lang_populations, lang_regions = self._ParseLanguageRegionInfo()
    region_groups = self._ParseRegionGroups()

    self.langs = self._CompileLanguages(lang_aliases, lang_names, lang_populations)
    self.regions = self._CompileRegions(region_names, region_populations)
    self.region_groups = self._CompileRegionGroups(region_groups, region_names)
    self.lang_region_map = lang_regions
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
    regions_data = root.find('.//{*}territories')

    lang_names = {lang.get('type'): lang.text for lang in languages_data}
    region_names = {region.get('type'): region.text for region in regions_data}
    return lang_names, region_names

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
      chars = chars[1:len(chars)-1].split(' ')
      exemplar_chars[category] = chars
    return exemplar_chars

  def _CompileLanguages(self, lang_aliases, lang_names, lang_populations):
    langs = {}
    for lang_code in lang_populations:
      population = lang_populations[lang_code]
      display_name = lang_names[lang_code]
      assert display_name is not None, 'Missing display name for language: ' + lang_code
      aliases = [] if lang_code not in lang_aliases else lang_aliases[lang_code]
      langs[lang_code] = self.Language(lang_code, aliases, display_name, population)
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

  def _SetRegionsOnLanguages(self, lang_regions):
    for lang_code in lang_regions:
      assert lang_code in self.langs, 'Missing language: ' + lang_code
      regions = [self.regions[r] for r in lang_regions[lang_code]]
      self.langs[lang_code].SetRegions(regions)

  def _SetExemplarCharsOnLanguages(self):
    for lang_code in self.langs:
      exemplar_chars = self._ParseExemplarCharacters(lang_code)
      self.langs[lang_code].SetExemplarChars(exemplar_chars)

  class Language():

    def __init__(self, lang_code, aliases, display_name, population):
      self.id = lang_code
      self.aliases = aliases
      self.name = display_name
      self.population = int(population)
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
