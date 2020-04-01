Google Fonts Arabic Character Sets
==================================

Two character sets were developed for Arabic:

1. **Core** Basic character set covering the 3 most widely used languages.
2. **Plus** Covering additional less widely used languages (but not characters needed for historical or specialized texts).

The character sets intentionally omit Arabic Presentation Forms, because:
* They are deprecated characters that should not be used for text input,
* When they appear on the web it is often by mistake, so it might be desirable to make them stand out,
* They cover a subset of the forms of a subset of the Arabic characters encoded in Unicode,
* They increase file size (depends on the font, it might be significant or not) while not providing much value.

Core
----

[GF-arabic-core.nam](https://github.com/googlefonts/gftools/blob/master/Lib/gftools/encodings/GF Glyph Sets/Arabic/GF-arabic-core.nam)

### Language coverage
* Arabic, including characters used in Maghrebi varieties of Arabic.
* Persian
* Urdu

### Additional characters
* Common punctuation symbols shared between Arabic and othes scripts

Plus
----

[GF-arabic-plus.nam](https://github.com/googlefonts/gftools/blob/master/Lib/gftools/encodings/GF Glyph Sets/Arabic/GF-arabic-plus.nam)

### Language coverage
In addition to languages supported by **Core**:

* Kurdish
* Malay (Jawi)
* Pashto
* Sindhi
* Uyghur
