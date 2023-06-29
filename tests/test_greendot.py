import pytest
from gftools.greendot import green_dot


@pytest.mark.parametrize(
    "range,expected",
    [
        # Bodoni-Moda
        ((6, 96), [9, 18, 28, 48, 72]),
        # Fraunces
        ((9, 144), [14, 28, 48, 72, 120]),
        # Imbue
        ((10, 100), [14, 24, 36, 48, 72]),
        # Literata
        ((7, 72), [14, 18, 24, 36, 60]),
        # Newsreader
        ((6, 72), [9, 14, 24, 36, 60]),
        # Piazolla
        ((8, 30), [14, 18, 24]),
        # Texturina
        ((12, 72), [14, 18, 28, 48, 60]),
        # NDA
        ((17, 18), [17, 18]),
    ],
)
def test_green_dot(range, expected):
    assert green_dot(*range) == expected
