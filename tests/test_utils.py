import pytest
from fontTools.ttLib import TTFont


@pytest.mark.parametrize(
    "url,want",
    [
        ("https://www.google.com", "google.com"),
        ("https://google.com", "google.com"),
        ("http://www.google.com", "google.com"),
        ("http://google.com", "google.com"),
        ("google.com", "google.com"),
        ("", ""),
    ],
)
def test_remove_url_prefix(url, want):
    from gftools.utils import remove_url_prefix

    got = remove_url_prefix(url)
    assert got == want


def test_format_html():
    from gftools.utils import format_html

    input = """<p>
First sentence. Second sentence.
Sentence that uses an abbreviation, e.g. "for example".    Sentence that uses an abbreviation, eg. "for example".
Sentence that uses another abbreviation, i.e. "for example".    Sentence that uses another abbreviation, ie. "for example".
Sentence that ends in etc. Another sentence after it.
Sentence that uses etc. but then doesn't end.
The characters of the film were designed by H.R. Giger. His alien characters became iconic throughout pop culture.
The characters of the film were designed by H.R. Giger, a Swiss sculptural artist. His alien characters became iconic throughout pop culture.
He was referred to H.R. Giger, who headed the H.R. department at the time, then told them they're fired. <-- Can't have it both ways. Legitimate abbreviations at the end of sentences can only be caught if they are known in advance, e.g. etc.
</p>
"""

    output = """<p>
 First sentence.
 Second sentence.
 Sentence that uses an abbreviation, e.g. "for example".
 Sentence that uses an abbreviation, eg. "for example".
 Sentence that uses another abbreviation, i.e. "for example".
 Sentence that uses another abbreviation, ie. "for example".
 Sentence that ends in etc.
 Another sentence after it.
 Sentence that uses etc. but then doesn't end.
 The characters of the film were designed by H.R.
 Giger.
 His alien characters became iconic throughout pop culture.
 The characters of the film were designed by H.R.
 Giger, a Swiss sculptural artist.
 His alien characters became iconic throughout pop culture.
 He was referred to H.R.
 Giger, who headed the H.R. department at the time, then told them they're fired.
 <-- Can't have it both ways.
 Legitimate abbreviations at the end of sentences can only be caught if they are known in advance, e.g. etc.
</p>
"""
    assert format_html(input) == output


@pytest.mark.parametrize(
    """url,want""",
    [
        (
            "https://github.com/SorkinType/SASchoolHandAustralia",
            ("SorkinType", "SASchoolHandAustralia"),
        ),
        (
            "https://github.com/SorkinType/SASchoolHandAustralia/",
            ("SorkinType", "SASchoolHandAustralia"),
        ),
        ("https://github.com/googlefonts/MavenPro//", ("googlefonts", "MavenPro")),
        ("https://github.com/googlefonts/MavenPro.git", ("googlefonts", "MavenPro")),
        (
            "https://www.github.com/googlefonts/MavenPro.git",
            ("googlefonts", "MavenPro"),
        ),
        ("http://www.github.com/googlefonts/MavenPro.git", ("googlefonts", "MavenPro")),
        ("http://www.github.com/NDISCOVER/Exo-2.0.git", ("NDISCOVER", "Exo-2.0")),
    ],
)
def test_github_user_repo(url, want):
    from gftools.utils import github_user_repo

    assert github_user_repo(url) == want


def test_supported_languages():
    from gftools.util.google_fonts import SupportedLanguages

    ttfont = TTFont("data/test/Nabla[EDPT,EHLT].subset.ttf")
    langs = [l.id for l in SupportedLanguages(ttfont)]
    assert langs == []

    ttfont = TTFont("data/test/Lora-Regular.ttf")
    langs = [l.id for l in SupportedLanguages(ttfont)]
    assert len(langs) >= 350
    assert "en_Latn" in langs
