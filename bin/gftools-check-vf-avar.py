#!/usr/bin/env python3
"""
Generate a html overlay doc which compares a family of static fonts against
a family of vf font instances.

If the variable font instances do not match the static fonts perfectly,
it usually means the avar table needs adjusting
https://docs.microsoft.com/en-us/typography/opentype/spec/avar

Please note: The generated html doc will only work on browsers which support
variable fonts.

TODO (M Foley) this script is a quickie. The functionality of this script
should be built into GF regression.
"""
from __future__ import print_function
import argparse
import os

WEIGHT_MAP = {
    'Thin': 100,
    'ThinItalic': 100,
    'ExtraLight': 200,
    'ExtraLightItalic': 200,
    'Light': 300,
    'LightItalic': 300,
    'Regular': 400,
    'Italic': 400,
    'Medium': 500,
    'MediumItalic': 500,
    'SemiBold': 600,
    'SemiBoldItalic': 600,
    'Bold': 700,
    'BoldItalic': 700,
    'ExtraBold': 800,
    'ExtraBoldItalic': 800,
    'Black': 900,
    'BlackItalic': 900
}

HTML_TEMPLATE = """
<html>
  <head>
    <style>
      html{
          font-family: sans-serif;
      }
      {{ static_fonts }}
      {{ variable_fonts }}

      {{ static_styles }}
      {{ variable_styles }}
    </style>
  </head>
  <body>
  <h1>Variable Font instances vs Static fonts</h1>
  <h3>Static fonts, <span style="color: cyan">Variable Font Instances</span></h3>
    <div id='container'>
      {{ elements }}
    </div>
  </body>
</html>
"""


def get_vf_font_info(variable_font_paths):

    faces = []
    for path in variable_font_paths:
        filename = os.path.basename(path)[:-4]
        family_name = filename.split('-')[0] + '-VF'
        font_type = filename.split('-')[1]
        if font_type not in ('Roman', 'Italic'):
            raise Exception("Filename must contain either Roman or Italic")
        style = 'normal' if 'Roman' in font_type else 'italic'

        faces.append((family_name, path, style))
    return sorted(faces, key=lambda k: k[2])


def get_static_fonts_info(static_font_paths):
    faces = []
    for path in static_font_paths:
        filename = os.path.basename(path)[:-4]
        family_name, style = filename.split('-')
        weight = WEIGHT_MAP[style]
        ttype = 'normal' if 'Italic' not in style else 'italic'

        faces.append((family_name, path, weight, ttype))
    return sorted(faces, key=lambda k: k[2])


def populate_html_template(html_template, static_fonts, vf_fonts):
    """Note: The vf css styles are populated using the weight
    and style values from the static fonts."""
    static_font_template = """
    @font-face {font-family: '%s';
    src: url('%s') format('truetype');
    font-weight: %s;
    font-style: %s}"""

    vf_font_template = """
    @font-face {font-family: '%s';
    src: url('%s') format('truetype');
    font-weight: 1 999;
    font-style: %s}"""

    style_template = """
    .%s{
        position: absolute;
        font-family: %s;
        font-weight: %s;
        font-style: %s;
        font-size: 48px;
        top: %spx;
    }"""

    vf_style_template = """
    .%s{
        position: absolute;
        font-family: %s;
        font-weight: %s;
        font-style: %s;
        font-size: 48px;
        top: %spx;
        color: cyan;
    }"""
    element_template = """
    <div class="%s">hamburgevons</div>"""

    html = html_template

    # Gen @font-faces for static fonts
    static_font_faces = []
    for family_name, path, weight, ttype in static_fonts:
        static_font_face = static_font_template % (
            family_name, path, weight, ttype
        )
        static_font_faces.append(static_font_face)

    # Gen @font-face for variable fonts
    vf_font_faces = []
    for family_name, path, style in vf_fonts:
        vf_font_face = vf_font_template % (
            family_name, path, style
        )
        vf_font_faces.append(vf_font_face)

    # Gen css classes for both static fonts and variable fonts. Use the
    # static font values to set the vf values so they're matching.
    # Gen div elements for each style as well.
    static_styles = []
    variable_styles = []
    elements = []
    line_gap = 150
    for family_name, path, weight, ttype in static_fonts:
        # Gen static class styles
        static_style = style_template % (
            family_name+str(weight)+ttype,
            family_name,
            weight,
            ttype,
            line_gap
        )
        static_styles.append(static_style)

        # Gen variable class styles
        variable_style = vf_style_template % (
            vf_fonts[0][0]+str(weight)+ttype,
            vf_fonts[0][0],
            weight,
            ttype,
            line_gap
        )
        variable_styles.append(variable_style)

        # Gen Div elements
        static_element = element_template % (
            family_name+str(weight)+ttype
        )
        elements.append(static_element)

        variable_element = element_template % (
            vf_fonts[0][0]+str(weight)+ttype
        )
        elements.append(variable_element)
        line_gap += 72

    html = html.replace('{{ static_fonts }}', '\n'.join(static_font_faces))
    html = html.replace('{{ variable_fonts }}', '\n'.join(vf_font_faces))
    html = html.replace('{{ static_styles }}', '\n'.join(static_styles))
    html = html.replace('{{ variable_styles }}', '\n'.join(variable_styles))
    html = html.replace('{{ elements }}', '\n'.join(elements))
    return html


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variable-fonts', '-vf', nargs='+')
    parser.add_argument('--static-fonts', '-sf', nargs='+')
    parser.add_argument('--out', '-o', help='html output filepath', required=True)
    args = parser.parse_args()

    vf_fonts = get_vf_font_info(args.variable_fonts)
    static_fonts = get_static_fonts_info(args.static_fonts)

    html = populate_html_template(
        HTML_TEMPLATE,
        static_fonts,
        vf_fonts
    )
    with open(args.out, 'w') as html_doc:
        html_doc.write(html)
        print('html written to {}'.format(args.out))


if __name__ == '__main__':
    main()
