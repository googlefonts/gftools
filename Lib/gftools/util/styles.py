
STYLE_NAMES = ["Thin",
               "ExtraLight",
               "Light",
               "Regular",
               "Medium",
               "SemiBold",
               "Bold",
               "ExtraBold",
               "Black",
               "Thin Italic",
               "ExtraLight Italic",
               "Light Italic",
               "Italic",
               "Medium Italic",
               "SemiBold Italic",
               "Bold Italic",
               "ExtraBold Italic",
               "Black Italic"]

RIBBI_STYLE_NAMES = ["Regular",
                     "Italic",
                     "Bold",
                     "BoldItalic"]


def get_stylename(filename):
  filename_base = filename.split('.')[0]
  return filename_base.split('-')[-1]

def _familyname(filename):
  filename_base = filename.split('.')[0]
  names = filename_base.split('-')
  names.pop()
  return '-'.join(names)

def is_italic(stylename):
  return 'Italic' in stylename


def is_regular(stylename):
  return ("Regular" in stylename or
          (stylename in STYLE_NAMES and
           stylename not in RIBBI_STYLE_NAMES and
           "Italic" not in stylename))


def is_bold(stylename):
  return stylename in ["Bold", "BoldItalic"]


def is_filename_canonical(filename):
  if '-' not in filename:
    return False
  else:
    style = get_stylename(filename)
    for valid in STYLE_NAMES:
      valid = ''.join(valid.split(' '))
      if style == valid:
        return True
    # otherwise:
    return False
