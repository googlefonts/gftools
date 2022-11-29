from gftools.builder import GFBuilder
import tempfile
import pytest
import yaml
import os
from strictyaml import load, YAMLError
from strictyaml.exceptions import YAMLValidationError


def monkey_patch_config_defaults(self):
    """we're not testing this"""
    pass


GFBuilder.fill_config_defaults = monkey_patch_config_defaults

@pytest.fixture
def config_file():
    return {
        "buildStatic": True,
        "includeSourceFixes": False,
        "instances": {
            "MavenPro[wght].ttf": [
                {"coordinates": {"wght": 500}, "familyName": "Dejon"},
                {"coordinates": {"wght": 400}, "familyName": "Dejon Special"},
                {"coordinates": {"wght": 500}, "familyName": "Bogart"},
            ]
        },
        "sources": ["MavenPro.glyphs"],
    }


def test_good_config(config_file):
    # check a good config file
    with tempfile.NamedTemporaryFile("r+", suffix=".yml") as f:
        f.write(yaml.dump(config_file))
        f.seek(0)
        GFBuilder(f.name)


def test_bad_config_structure(config_file):
    # change sources to a string when it should be a list
    config_file["sources"] = "foobar"
    with tempfile.NamedTemporaryFile("r+", suffix=".yml") as f:
        f.write(yaml.dump(config_file))
        f.seek(0)
        with pytest.raises(ValueError, match="The yaml config file isn't structured properly"):
            GFBuilder(f.name)


def test_bad_config_key(config_file):
    # Spell a key incorrectly
    config_file["source"] = config_file["sources"]
    del config_file["sources"]
    with tempfile.NamedTemporaryFile("r+", suffix=".yml") as f:
        f.write(yaml.dump(config_file))
        f.seek(0)
        with pytest.raises(YAMLError, match="A key in the configuration file"):
            GFBuilder(f.name)
