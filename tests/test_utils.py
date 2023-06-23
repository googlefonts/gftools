import pytest


@pytest.mark.parametrize(
    "url,want",
    [
        ("https://www.google.com", "google.com"),
        ("https://google.com", "google.com"),
        ("http://www.google.com", "google.com"),
        ("http://google.com", "google.com"),
        ("google.com", "google.com"),
        ("", ""),
    ]
)
def test_remove_url_prefix(url, want):
    from gftools.utils import remove_url_prefix
    got = remove_url_prefix(url)
    assert got == want
