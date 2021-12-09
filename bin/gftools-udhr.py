#!/usr/bin/env python3
"""Extracts text samples from UDHR translations.

Translations exist for myriad languages at varying levels of support. The tool
focuses on Stage 4+ translations for which the UDHR translation has a reliable
amount of content and structure for scraping text samples.

See more at https://www.unicode.org/udhr.
"""

import enum
import os
import ssl
import tempfile
from urllib import request
from lxml import etree
import zipfile

UHDR_URL_TEMPLATE = 'https://www.un.org/{language_code}/universal-declaration-human-rights/'
UDHR_TRANSLATIONS_ZIP_URL = 'https://www.unicode.org/udhr/assemblies/udhr_xml.zip'
INDEX_XML = 'index.xml'


class UdhrTranslations():

  def __init__(self):
    self._zip_dir = tempfile.TemporaryDirectory()
    self._DownloadUdhrTranslationsZip()
    self._udhrs = self._ParseUdhrs()
    self._udhr_map = {}

    for udhr in self._udhrs:
      udhr.Parse(self._LoadUdhrTranslation(udhr))
      self._udhr_map[udhr.key] = udhr
      self._udhr_map[udhr.iso639_3] = udhr
      self._udhr_map[udhr.iso15924] = udhr
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

  def GetUdhr(self, lang_code, min_stage=0):
    if lang_code not in self._udhr_map or self._udhr_map[lang_code].stage < min_stage:
      return None
    return self._udhr_map[lang_code]

  class Udhr():

    def __init__(self, udhr_data, zip_dir):
      self.key = udhr_data.get('f')
      self.iso639_3 = udhr_data.get('iso639-3')
      self.iso15924 = udhr_data.get('iso15924')
      self.bcp47 = udhr_data.get('bcp47')
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
      extractor = SampleTextExtractor(udhr)
      return extractor.GetSampleTexts()

  class TextType(enum.Enum):
    GLYPHS = 1
    WORD = 2
    PHRASE = 3
    SENTENCE = 4
    PARAGRAPH = 5
    PASSAGE = 6

  class Size(enum.Enum):
    SMALL = 1
    MEDIUM = 2
    LARGE = 3

    def Switch(options, size):
      if size not in options:
        raise Error('Size {size} not in options: {options}'.format(
            options=options, size=size))
      return options[size]

  class SampleTextExtractor():

    def __init__(self, udhr):
      self._udhr = udhr
      self._glyphs = {}
      self._words = {}
      self._phrases = {}
      self._sentences = {}
      self._paragraphs = {}
      self._passages = {}

    def _ExtractGlyphs(self, size):
      if size == Size.SMALL:
        # single glyph
        pass
      elif size == Size.MEDIUM:
        # upper and lower of single glyph
        pass
      elif size == Size.LARGE:
        # upper and lower of two glyphs
        pass
      else:
        self._UnsupportedSize(size)
      pass

    def _ExtractWord(self, size):
      options = {
          Size.SMALL: (3, 5),
          Size.MEDIUM: (6, 8),
          Size.LARGE: (8, 11),
      }
      min_length, max_length = Size.Switch(options, size)
      pass

    def _ExtractPhrase(self, size):
      options = {
          Size.SMALL: (3, 7),
          Size.MEDIUM: (8, 14),
          Size.LARGE: (12, 20),
      }
      min_length, max_length = Size.Switch(options, size)
      pass

    def _ExtractSentence(self, size):
      options = {
          Size.SMALL: (6, 10),
          Size.MEDIUM: (12, 20),
          Size.LARGE: (23, 35),
      }
      min_length, max_length = Size.Switch(options, size)
      pass

    def _ExtractParagraph(self, size):
      options = {
          Size.SMALL: (10, 20),
          Size.MEDIUM: (30, 50),
          Size.LARGE: (70, 100),
      }
      length = Size.Switch(options, size)
      pass

    def _ExtractPassage(self, size):
      options = {
          Size.SMALL: 2,
          Size.MEDIUM: 3,
          Size.LARGE: 5,
      }
      length = Size.Switch(options, size)
      pass

    def _UnsupportedSize(self, size):
      raise Error('Unsupported size: ' + size)

    def _Get(self, text_type, size):
      pass

    def GetSampleTexts(self):
      return {
          'hero': [
              self._Get(TextType.GLYPHS, Size.LARGE),  # Single glyphs (eg AbZx)
          ],
          'type_tester': [
              self._Get(TextType.PHRASE, Size.LARGE),  # 12-20 word phrase
          ],
          'poster': [
              self._Get(TextType.WORD, Size.MEDIUM),  # Single word
              self._Get(TextType.WORD, Size.LARGE),  # Single longer word
              self._Get(TextType.SENTENCE, Size.SMALL),  # 6-10 word sentence
              self._Get(TextType.SENTENCE, Size.MEDIUM),  # 12-20 word sentence
          ],
          'specimen': [
              self._Get(TextType.SENTENCE, Size.SMALL),  # 6-10 word sentence
              self._Get(TextType.PARAGRAPH, Size.SMALL),  # Paragraph
              self._Get(TextType.PARAGRAPH, Size.MEDIUM),  # Medium paragraph
              self._Get(TextType.PARAGRAPH, Size.LARGE),  # Large paragraph
              self._Get(TextType.PASSAGE,
                        Size.SMALL),  # Multiple paragraphs split over 2 columns
              self._Get(TextType.PASSAGE,
                        Size.MEDIUM),  # Multiple paragraphs split over 3 columns
          ],
      }
