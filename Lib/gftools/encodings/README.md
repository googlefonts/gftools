# Google Fonts API subsets

The `.nam` files in this directory are provided to explain how the Unicode Range subsets are defined, typically per script (writing system), in the Google Fonts css API.

This information is useful for expert web developers.

If you are a font developer or typeface designer, you probably won't find them too useful.
Instead, see the subdirectory `GF Glyph Sets` which provides glyph set definition "standards" that are typically useful sets to draw.

## The "Namelist" file format

This directory contains "Namelist" files, for developers.
Typeface designers typically want **glyph sets**, and the `GF Glyph Sets` subdirectory here contains a [`README.md`]('GF Glyph Sets/README.md') describing them.

Their purpose is to subset fonts available from the Google Fonts API.
They define the `unicode-range` property values included in the `@font-face` rules returned by the Google Fonts API.
Each file lists Unicode characters, one per line, followed by glyph names or glyph descriptions.
As `unicode-range` values, this data is 'mini-fied', with contiguous ranges expressed as such (start-end hex values).

Typically within a font family, all the Unicode characters in each file are also in every other file that make up the family.
And typically, all the Unicode characters in a font file can be found within the set of Namelist files.
When a font family is onboarded into the `main` branch of http://github.com/google/fonts, a [METADATA](https://github.com/googlefonts/gf-docs/blob/main/METADATA/README.md) file is included that lists at the end the subsets supported;
those refer to these Namelists.

If the font files include characters that are not in any Namelist declared in the family [METADATA](https://github.com/googlefonts/gf-docs/blob/main/METADATA/README.md) file, those characters will not be available to Fonts API end-users, unless the users request the character using the `text=` API option ([learn more](https://developers.google.com/fonts/docs/getting_started#optimizing_your_font_requests)). 

* Developers can use Namefiles with [pyftsubset](https://github.com/behdad/fonttools/blob/main/Lib/fontTools/subset.py) to generate subsets from full `ttf` files.

* The extension of a Namelist file is "`.nam`".

* Namelist files are encoded in UTF-8.

* All encodings with the exception of `khmer` include `latin_unique-glyphs.nam`

* All *extended* encodings with filenames like`{lang}-ext_unique-glyphs.nam` also include `{lang}_unique-glyphs.nam`

* This is implemented in the `CodepointFiles` function of [google_fonts.py](../util/google_fonts.py)

* The [`README.md`]('GF Glyph Sets/README.md') describes mostly how each of the Namelist files depend on each other, to implement this [header includes](#header) were created.

#### Codepoint format

A line that starts with `0x` and then have 4 or 5 **uppercase** hex digits; what follows is an arbitrary description to the end of the line.

Example:

```
0x0061  a LATIN SMALL LETTER A
0x0062  b LATIN SMALL LETTER B
0x0063  c LATIN SMALL LETTER C
0x03E4  Ϥ COPTIC CAPITAL LETTER FEI
0x10142  𐅂 GREEK ACROPHONIC ATTIC ONE DRACHMA
```

#### Comments

Comments are lines starting with `#`.

Example:

```
# Created by Alexei Vanyashin 2016-27-06
#$ include ../GF-latin-plus_unique-glyphs.nam
```

## glyphs without Unicode (since the "novel" encodings)

A line that starts with at least six spaces describes a glyph that has no Unicode and will usually be accessible via OpenType GSUB. These glyphs are used to ensure the fonts contain certain OpenType features.

The description is a human readable glyph name that can be used in the authoring application (targeted at Glyphs) to create and process the glyph properly.

Example:

```
          aacute.sc
          abreve.sc
          abreveacute.sc
          abrevedotbelow.sc
```

For legacy reasons, we also accept lines in the form of:

```
        Д uni0414.loclBGR
        И uni0418.loclBGR
        Й uni0419.loclBGR
```

Using this sample python implementation to obtain the glyph name:

```py
line.strip().rsplit(' ')[-1]
```

#### Header

The header was created to make the Namelist format more self contained.

The Namelist header is made of all consecutive comment lines at the beginning of the file. The first non-comment line ends the header.

Specially crafted comment lines, "header data", define the meta data of the file. Other comments are just that, comments.

A header data line begins with `#$` then is followed by a keyword and then followed by the arguments for the keyword.

The keyword is separated from its arguments by one or more space characters.

The keywords, the semantics of a keyword and the syntax of its arguments should be documented here.

Format for header data:

```
#$ {keyword} {arguments}
```

##### Keyword `#$ include {namfile}`

The `include` keyword can be used zero or more times. Order of appearance should have no effect on the resulting set and thus be not important.

It specifies the namfiles on which the current namfile depends. The file plus all of its includes together define the complete char-set.

Includes are loaded recursively, meaning that the includes of an included files must also be loaded.

E.g. a novel a "pro" encoding would include its "plus" encoding and the latter would include its "base" encoding. The Pro charset then is the union of pro, plus and base.

Loops in the includes are not followed; the final result as a `set` wouldn't have a different value whether the same file is included once or many times.

`{namfile}` is a file path to a namfile relative to the path of the file that contains the include statement.

Example from `GF-latin-expert_unique-glyphs.nam`

```
#$ include GF-latin-pro_unique-glyphs.nam
0x2153  ⅓ onethird
0x2154  ⅔ twothirds
0x215B  ⅛ oneeighth
```


##### Possible Keywords

* `author {name}` (zero or more) since we can already find `# Created by` comments in the novel nam-files we could as well just institutionalize it.

* `label {name}` A human readable name for the file, to be used in user interfaces. Could also have a further `{locale}` argument for internationalization.

## Scripts

A python script, `tools/namelist.py` can generate these files:

    namelist.py Font.ttf > NameList.nam

The `[wgl-latin.enc]` file can be used by [Fontlab Studio 5](http://www.fontlab.com), and represented Microsoft's [Windows Glyph List 4](https://en.wikipedia.org/wiki/Windows_Glyph_List_4) glyph set.

A python script, `tools/unicode_names.py` can reformat these files:

    python unicode_names.py --nam_file=encodings/latin_unique-glyphs.nam;
    0x0020    SPACE
    0x0021  ! EXCLAMATION MARK
    0x0022  " QUOTATION MARK
    0x0023  # NUMBER SIGN
    ...

Namelist parsing is implemented in:

Python: `tools/util/google_fonts.py` use the function `CodepointsInSubset` for legacy Namelist files and `codepointsInNamelist` for novel Namelist files.

JavaScript: [analyzeCharSets.js](https://github.com/graphicore/specimenTools/blob/languages/build/analyzeCharSets.js) implements novel style Namefile parsing.
