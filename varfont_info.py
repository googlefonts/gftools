
import contextlib
from fontTools import ttLib
from google.apputils import app


def _ResolveName(ttf, name_id):
  if name_id == 0xFFFF:
    return '[anonymous]'
  names = [n for n in ttf['name'].names if n.nameID == name_id]
  if not names:
    return '[?nameID=%d?]' % name_id
  unicode_names = [n for n in names if n.isUnicode()]
  if unicode_names:
    return unicode_names[0].toUnicode()
  return names[0].toUnicode()


def main(argv):
  for filename in argv[1:]:
    with contextlib.closing(ttLib.TTFont(filename)) as ttf:
      print filename
      if 'fvar' in ttf:
        fvar = ttf['fvar']
        print ' axes'
        axes = [(a.axisTag, a.minValue, a.defaultValue, a.maxValue)
                for a in fvar.axes]
        for tag, minv, defv, maxv in axes:
          print "  '%s' %d-%d, default %d" % (tag, minv, maxv, defv)

        if fvar.instances:
          print ' named-instances'
          for inst in fvar.instances:
            print '   %s %s' % (_ResolveName(ttf, inst.postscriptNameID),
                                inst.coordinates)

if __name__ == '__main__':
  app.run()
