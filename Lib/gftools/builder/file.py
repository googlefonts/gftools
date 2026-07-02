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

    @cached_property
    def is_variable(self) -> bool:
        if self.is_designspace:
            return len(self.designspace.sources) > 1
        if self.is_ufo:
            return False
        if self.is_glyphspackage:
            # Optimisation opportunity: avoid loading the full GSFont by
            # accessing self.gsfont, instead just reach into the fontinfo.plist
            # directly.
            # Conditions match the ordinary Glyphs ones below.
            return len(self.glyphspackage_fontinfo["fontMaster"]) > 1 or any(
                custom_parameter["name"] == "Virtual Master"
                for custom_parameter in self.glyphspackage_fontinfo["customParameters"]
            )
        # Glyphs may have a "virtual master"
        masters = len(self.gsfont.masters)
        if any("Virtual Master" == c.name for c in self.gsfont.customParameters):
            masters += 1
        return masters > 1

    @cached_property
    def gsfont(self):
        if self.is_glyphs:
            import glyphsLib

            return glyphsLib.load(self.path)
        return None

    @cached_property
    def glyphspackage_fontinfo(self) -> dict[str, Any]:
        """Grants raw dictly-typed access to a Glyphspackage's fontinfo.plist to
        avoid loading the full font through glyphsLib"""

        assert self.is_glyphspackage, (
            "File.glyphspackage_fontinfo should not be accessed on non-glyphspackage sources"
        )
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
            name = self.gsfont.familyName
        elif self.is_glyphspackage:
            # Optimisation: pull this directly from the fontinfo.plist instead
            # of potentially loading the whole font with glyphsLib
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
