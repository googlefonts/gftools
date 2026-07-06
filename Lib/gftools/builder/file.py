import os
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

import openstep_plist
from fontTools.designspaceLib import InstanceDescriptor
from glyphsLib.builder import UFOBuilder

from gftools.utils import open_ufo


@dataclass
class File:
    path: str
    type: str = None

    @property
    def extension(self):
        return self.path.split(".")[-1]

    @property
    def basename(self):
        return os.path.basename(self.path)

    def __hash__(self):
        return hash(id(self))

    def __str__(self):
        return self.path

    def exists(self):
        return os.path.exists(self.path)

    @property
    def is_glyphs(self):
        return self.is_glyphs_file or self.is_glyphspackage

    @property
    def is_ufo(self):
        # ".ufoz" is a zipped UFO; ufoLib2 (via open_ufo) reads it like a UFO.
        return self.extension in ("ufo", "ufoz") or ".ufo.json" in self.path

    @property
    def is_designspace(self):
        return self.extension == "designspace"

    @property
    def is_font_source(self):
        return self.is_glyphs or self.is_ufo or self.is_designspace

    @property
    def is_glyphs_file(self):
        return self.extension == "glyphs"

    @property
    def is_glyphspackage(self):
        return self.extension == "glyphspackage"

    @property
    def glyphs_format(self) -> int:
        if self.is_glyphs_file:
            return int(self.glyphs_plist.get(".formatVersion", 2))
        elif self.is_glyphspackage:
            return int(self.glyphspackage_fontinfo.get(".formatVersion", 2))
        else:
            raise ValueError(
                "File.glyphs_format should not be accessed on non-Glyphs sources"
            )

    @cached_property
    def is_variable(self) -> bool:
        if self.is_designspace:
            return len(self.designspace.sources) > 1
        if self.is_ufo:
            return False
        # Deal with Glyphs sources in their raw plist form to save parsing with
        # glyphsLib, which is far slower
        if self.is_glyphs_file:
            glyphs_fontinfo = self.glyphs_plist
        elif self.is_glyphspackage:
            glyphs_fontinfo = self.glyphspackage_fontinfo
        else:
            raise ValueError(f"unsure how to determine if {self.path} is variable")
        # Fine for Glyphs v2 & v3
        return len(glyphs_fontinfo["fontMaster"]) > 1 or any(
            custom_parameter["name"] == "Virtual Master"
            for custom_parameter in glyphs_fontinfo["customParameters"]
        )

    @cached_property
    def gsfont(self):
        if self.is_glyphs:
            import glyphsLib

            return glyphsLib.load(self.path)
        return None

    @cached_property
    def glyphs_plist(self) -> dict[str, Any]:
        """Grants raw dictly-typed access to a Glyphs to avoid parsing the full
        font with glyphsLib.

        Note that this could be either Glyphs format v2 or v3."""

        assert (
            self.is_glyphs_file
        ), "File.glyphs_plist should not be accessed on non-glyphs single file sources"
        return openstep_plist.load(open(self.path, encoding="utf-8"))

    @cached_property
    def glyphspackage_fontinfo(self) -> dict[str, Any]:
        """Grants raw dictly-typed access to a Glyphspackage's fontinfo.plist to
        avoid parsing the full font with glyphsLib"""

        assert (
            self.is_glyphspackage
        ), "File.glyphspackage_fontinfo should not be accessed on non-glyphspackage sources"
        fontinfo_path = Path(self.path) / "fontinfo.plist"
        return openstep_plist.load(fontinfo_path.open(encoding="utf-8"))

    @cached_property
    def designspace(self):
        if self.is_designspace:
            from fontTools.designspaceLib import DesignSpaceDocument

            return DesignSpaceDocument.fromfile(self.path)
        return None

    @cached_property
    def instances(self):
        if self.is_glyphs:
            gsfont = self.gsfont
            builder = UFOBuilder(gsfont, minimal=True)
            builder.to_designspace_instances()
            return builder._designspace.instances
        elif self.is_designspace:
            return self.designspace.instances
        else:  # UFO
            return [InstanceDescriptor(filename=self.basename)]

    @cached_property
    def family_name(self):
        # Figure out target name
        if self.is_glyphs_file:
            # Optimisation: pull directly from source instead of parsing with
            # glyphsLib
            # Fine for Glyphs v2 & v3
            name = self.glyphs_plist["familyName"]
        elif self.is_glyphspackage:
            # Optimisation: pull this directly from the fontinfo.plist instead
            # of parsing with glyphsLib
            name = self.glyphspackage_fontinfo["familyName"]
        elif self.is_ufo:
            ufo = open_ufo(self.path)
            name = ufo.info.familyName
        elif self.designspace.sources[0].familyName:
            return self.designspace.sources[0].familyName
        else:
            self.designspace.loadSourceFonts(open_ufo)
            return self.designspace.sources[0].font.info.familyName
        return name
