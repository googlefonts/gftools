import json
import os
from collections import OrderedDict
from pkg_resources import resource_filename


class LastUpdatedOrderedDict(OrderedDict):
    """Store items in the order the keys were last added."""

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.move_to_end(key)


def _fetch_all_unicode_sections():
    sections = LastUpdatedOrderedDict()
    filename = resource_filename("gftools.util",
                                      os.path.join('UnicodeSections',
                                                    'UnicodeSections.json'))
    with open(filename, 'r') as file:
      data = json.load(file)
      for section_name in data:
        assert section_name not in sections, "multiple entries for " + section_name
        glyphs = data[section_name].split('\u0020')
        if len(glyphs) > 0:
          sections[section_name] = glyphs
    return sections


DATA = _fetch_all_unicode_sections()
