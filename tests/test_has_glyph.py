import os

import pytest

from gftools.scripts import has_glyph


TEST_DATA = os.path.join("data", "test")


def test_missing_directory_reports_error(tmp_path, capsys):
    missing = os.path.join(str(tmp_path), "does-not-exist")
    with pytest.raises(SystemExit) as exc_info:
        has_glyph.main([missing, "A"])
    assert exc_info.value.code == 2
    _, stderr = capsys.readouterr()
    assert "Directory does not exist" in stderr
    assert missing in stderr


def test_existing_directory_scans_without_error(capsys):
    assert has_glyph.main([TEST_DATA, "A"]) is None
