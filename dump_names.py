
import contextlib
import os


from fontTools import ttLib

from google.apputils import app


def main(argv):
  for font_file in argv[1:]:
    filename = os.path.basename(font_file)
    try:
      with contextlib.closing(ttLib.TTFont(font_file)) as ttf:
        if 'name' not in ttf:
          continue
        for name in ttf['name'].names:
          print '%s %d %d %d %s %s' % (filename, name.platformID,
                                       name.platEncID, name.langID, name.nameID,
                                       name.toUnicode())
    except ttLib.TTLibError as e:
      print 'BAD_FILE', font_file, e


if __name__ == '__main__':
  app.run()
