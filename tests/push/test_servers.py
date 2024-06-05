import pytest
from gftools.push.servers import GFServers, GFServer
from gftools.push.items import Family, Designer, FamilyMeta


DATA = {
    "dev": {"families": {"Abel": {"name": "Abel", "version": "1.000"}}},
    "sandbox": {"families": {"Abel": {"name": "Abel", "version": "0.999"}}},
    "production": {"families": {"Abel": {"name": "Abel", "version": "0.999"}}},
    "last_checked": "2023-01-01",
}


@pytest.fixture
def servers():
    return GFServers.from_dict(DATA)


def test_servers_open_and_save(servers):
    assert servers != None
    assert servers.to_json() != None


def test_iter(servers):
    assert ["dev", "sandbox", "production"] == [s.name for s in servers]


@pytest.mark.parametrize(
    "item, res",
    [
        (
            Family("Abel", "1.000"),
            {
                "name": "Abel",
                "version": "1.000",
                "In dev": True,
                "In sandbox": False,
                "In production": False,
            },
        )
    ],
)
def test_compare_items(servers, item, res):
    # TODO may be worth using a dataclass instead of dict
    assert servers.compare_item(item) == res


@pytest.fixture
def server():
    return GFServer(name="Prod")


@pytest.mark.parametrize(
    "method, family_name, res",
    [
        # Test on a family which isn't updated regularly. We should
        # probably use mocks at some point
        ("update_family", "Allan", Family("Allan", "Version 1.002")),
        ("update_family_designers", "Allan", Designer(name="Anton Koovit", bio=None)),
        (
            "update_metadata",
            "Allan",
            FamilyMeta(
                name="Allan",
                designer=["Anton Koovit"],
                license="ofl",
                category="DISPLAY",
                subsets=["latin", "latin-ext"],
                stroke="SERIF",
                classifications=["display"],
                description="Once Allan was a sign painter in Berlin. Grey paneling work in the subway, bad materials, a city split in two. Now things have changed. His (character) palette of activities have expanded tremendously: he happily spends time traveling, experimenting in the gastronomic field, all kinds of festivities are no longer foreign to him. He comes with alternate features, and hints. A typeface suited for bigger sizes and display use. Truly a type that you like to see!",
            ),
        ),
    ],
)
def test_update_server(server, method, family_name, res):
    assert server.find_item(res) == None
    funcc = getattr(server, method)
    funcc(family_name)
    assert server.find_item(res) == res
