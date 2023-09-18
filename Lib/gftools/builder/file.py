from dataclasses import dataclass
from functools import cached_property
import os
from fontTools.designspaceLib import InstanceDescriptor
from glyphsLib.builder import UFOBuilder


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
        return self.extension == "glyphs" or self.extension == "glyphspackage"

    @property
    def is_ufo(self):
        return self.extension == "ufo"

    @property
    def is_designspace(self):
        return self.extension == "designspace"
    
    @cached_property
    def gsfont(self):
        if self.is_glyphs:
            import glyphsLib
            return glyphsLib.GSFont(self.path)
        return None

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
