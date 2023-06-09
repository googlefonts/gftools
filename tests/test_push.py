import pytest
from gftools.push2 import PushItem, PushItems
from pathlib import Path
import os


CWD = os.path.dirname(__file__)
TEST_DIR = os.path.join(CWD, "..", "data", "test", "gf_fonts")
TEST_FAMILY_DIR = Path(os.path.join(TEST_DIR, "ofl", "mavenpro"))



@pytest.mark.parametrize(

    "item1,item2,expected",
    [
        (
            PushItem("ofl/mavenpro", "modified", "dev", "45"),
            PushItem("ofl/mavenpro", "modified", "dev", "45"),
            True
        ),
        (
            PushItem("ofl/mavenpro", "modified", "dev", "45"),
            PushItem("ofl/mavenpro", "modified", "dev", "46"),
            False
        ),
        (
            PushItem("ofl/mavenpro", "modified", "dev", "45"),
            PushItem("ofl/mavenpro2", "modified", "dev", "45"),
            False
        ),
        (
            PushItem("ofl/mavenpro", "modified", "dev", "45"),
            PushItem("ofl/mavenpro", "modified", "sandbox", "45"),
            False
        ),
    ]
)
def test_push_item_eq(item1, item2, expected):
    assert (item1 == item2) == expected


@pytest.mark.parametrize(
    "items, expected_size",
    [
        (
            [
                PushItem("1", "1", "1", "1"),
                PushItem("1", "1", "1", "1"),
                PushItem("1", "1", "1", "1"),
            ],
            1
        ),
        (
            [
                PushItem("1", "1", "1", "1"),
                PushItem("1", "1", "1", "1"),
                PushItem("2", "1", "1", "1"),
            ],
            2
        ),
    ]
)
def test_push_item_set(items, expected_size):
    new_items = PushItems(set(items))
    assert len(new_items) == expected_size


@pytest.mark.parametrize(
    "items, expected",
    [
        # fonts filenames get removed
        (
            [
                PushItem(Path("ofl/mavenpro/MavenPro[wght].ttf"), "update", "dev", "1")
            ],
            PushItems([PushItem(Path("ofl/mavenpro"), "update", "dev", "1")]),
        ),
        # font family
        (
            [
                PushItem(Path("ofl/mavenpro/MavenPro[wght].ttf"), "update", "dev", "1"),
                PushItem(Path("ofl/mavenpro/MavenPro-Italic[wght].ttf"), "update", "dev", "1")
            ],
            PushItems([PushItem(Path("ofl/mavenpro"), "update", "dev", "1")]),
        ),
        # axisregistry
        (
            [
                PushItem(Path("axisregistry/Lib/axisregistry/data/bounce.textproto"), "new", "dev", "1"),
                PushItem(Path("axisregistry/Lib/axisregistry/data/morph.textproto"), "new", "dev", "1")
            ],
            PushItems([
                PushItem(Path("axisregistry/bounce.textproto"), "new", "dev", "1"),
                PushItem(Path("axisregistry/morph.textproto"), "new", "dev", "1"),
            ])
        ),
        # lang
        (
            [
                PushItem(Path("lang/Lib/gflanguages/data/languages/aa_Latn.textproto"), "new", "dev", "1"),
            ],
            PushItems([
                PushItem(Path("lang/languages/aa_Latn.textproto"), "new", "dev", "1"),
            ])
        ),
        # child
        (
            [
                PushItem(Path("ofl/mavenpro"), "new", "dev", "1"),
                PushItem(Path("ofl"), "new", "dev", "1"),
            ],
            PushItems([
                PushItem(Path("ofl/mavenpro"), "new", "dev", "1"),
            ])
        ),
        # parent
        (
            [
                PushItem(Path("ofl"), "new", "dev", "1"),
                PushItem(Path("ofl/mavenpro"), "new", "dev", "1"),
            ],
            PushItems([
                PushItem(Path("ofl/mavenpro"), "new", "dev", "1"),
            ])
        ),
        # parent dir
        (
            [
                PushItem(Path("ofl"), "new", "dev", "1"),
                PushItem(Path("apache"), "new", "dev", "1"),
                PushItem(Path("lang/authors.txt"), "new", "dev", "1"),
            ],
            PushItems()
        ),
        # noto article
        (
            [
                PushItem(Path("ofl/notosans/article"), "new", "dev", "1"),
            ],
            PushItems([
                PushItem(Path("ofl/notosans"), "new", "dev", "1"),
            ])
        ),
        # noto full
        (
            [
                PushItem(Path("ofl/notosans/article"), "new", "dev", "1"),
                PushItem(Path("ofl/notosans/NotoSans[wght].ttf"), "new", "dev", "1"),
                PushItem(Path("ofl/notosans/DESCRIPTION.en_us.html"), "new", "dev", "1"),
                PushItem(Path("ofl/notosans/OFL.txt"), "new", "dev", "1"),
            ],
            PushItems([
                PushItem(Path("ofl/notosans"), "new", "dev", "1"),
            ])
        ),

    ]
)
def test_push_items_add(items, expected):
    res = PushItems()
    for item in items:
        res.add(item)
    assert res == expected
    


def test_push_items_from_traffic_jam():
    items = PushItems.from_traffic_jam()
    # traffic board shouldn't be empty
    assert len(items) != 0, "board is empty! check https://github.com/orgs/google/projects/74"


@pytest.mark.parametrize(
    "string, expected_size",
    [
        (
           "ofl/noto # 2",
           1 
        ),
        (
           "# New\nofl/noto # 2\nofl/foobar # 3\n\n# Upgrade\nofl/mavenPro # 4",
           3 
        ),
    ]
)
def test_push_items_from_server_file(string, expected_size):
    from io import StringIO

    data = StringIO()
    data.write(string)
    data.seek(0)
    items = PushItems.from_server_file(data, "dev")
    assert len(items) == expected_size


@pytest.mark.parametrize(
    "items,expected",
    [
        # standard items
        (
            PushItems([
                PushItem("a/b", "Upgrade", "dev", "45"),
                PushItem("a/c", "New", "dev", "46"),
            ]),
            "# New\na/c # 46\n\n# Upgrade\na/b # 45\n"
        ),
        # duplicate items
        (
            PushItems([
                PushItem("a/b", "Upgrade", "dev", "45"),
                PushItem("a/b", "Upgrade", "dev", "45"),
                PushItem("a/b", "Upgrade", "dev", "45"),
            ]),
            "# Upgrade\na/b # 45\n"
        ),
    ]
)
def test_push_items_to_server_file(items, expected):
    from io import StringIO

    out = StringIO()
    items.to_server_file(out)
    out.seek(0)
    assert out.read() == expected

@pytest.mark.parametrize(
    "path, expected",
    [
        (TEST_FAMILY_DIR, []),
        (Path("/foo/bar"), [Path("/foo/bar")]),
    ]
)
def test_push_items_missing_paths(path, expected):
    items = PushItems([PushItem(path, "a", "a", "a")])
    assert items.missing_paths() == expected