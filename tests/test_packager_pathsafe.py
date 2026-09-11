"""Regression tests for gftools.packager._pathsafe.safe_join.

These verify that a contributor-controlled ``dest_file`` cannot escape the
target family directory (path traversal / arbitrary file write).
"""

import os
import pytest

from gftools.packager._pathsafe import safe_join


def test_normal_dest_file_is_allowed(tmp_path):
    out = safe_join(tmp_path, "MyFont[wght].ttf")
    assert str(out).startswith(str(tmp_path.resolve()))


def test_nested_dest_file_is_allowed(tmp_path):
    out = safe_join(tmp_path, "static/MyFont-Regular.ttf")
    assert str(out).startswith(str(tmp_path.resolve()))


def test_parent_traversal_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        safe_join(tmp_path, "../../../etc/cron.d/pwn")


def test_absolute_dest_file_is_rejected(tmp_path):
    abs_target = os.path.abspath(os.sep + os.path.join("tmp", "pwn"))
    with pytest.raises(ValueError):
        safe_join(tmp_path, abs_target)


def test_sneaky_traversal_after_prefix_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        safe_join(tmp_path, "ok/../../../../../../etc/passwd")
