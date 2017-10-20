

import os
import sys
import unicodedata

from google.apputils import app
import gflags as flags
from util import google_fonts as fonts


FLAGS = flags.FLAGS
flags.DEFINE_bool('show_char', False, 'Print the actual character')


def main(argv):
  if len(argv) != 2 or not os.path.isfile(argv[1]):
    sys.exit('Must have one argument, a font file.')

  for cp in sorted(fonts.CodepointsInFont(argv[1])):
    show_char = ''
    if FLAGS.show_char:
      show_char = ' ' + unichr(cp) + ' ' + unicodedata.name(unichr(cp), '')
    print '0x%04X%s' % (cp, show_char)

if __name__ == '__main__':
  app.run()
