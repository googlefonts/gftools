import pytest
import tempfile
import subprocess
import os
from fontTools.ttLib import TTFont
from gftools.builder.dependencies import GFTOOLS_DEPENDENCIES_KEY


TEST_FONT = os.path.join("data", "test", "Lora-Regular.ttf")


@pytest.mark.parametrize("fp", [TEST_FONT])
def test_write_and_read_dependencies(fp):
    with tempfile.TemporaryDirectory() as tmp:
        font_out = os.path.join(tmp, "font.ttf")
        requirements_out = os.path.join(tmp, "requirements.txt")
        subprocess.run(
            ["gftools", "font-dependencies", "write", TEST_FONT, "-o", font_out]
        )
        ttfont = TTFont(font_out)
        assert "Debg" in ttfont
        assert GFTOOLS_DEPENDENCIES_KEY in ttfont["Debg"].data

        subprocess.run(
            ["gftools", "font-dependencies", "read", font_out, "-o", requirements_out]
        )
        with open(requirements_out, encoding="utf-8") as doc:
            doc_text = doc.read()
            assert "fonttools" in doc_text
