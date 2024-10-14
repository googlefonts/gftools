from collections import defaultdict
from dataclasses import dataclass, field
from functools import cached_property
import os
import pkgutil
import importlib
import inspect
import sys
from os.path import dirname
from tempfile import NamedTemporaryFile

from gftools.builder.file import File
from gftools.utils import shell_quote


@dataclass
class OperationBase:
    postprocess: bool = False
    original: dict = field(default_factory=dict)
    _targets: set = field(default_factory=set)  # [File]
    _sources: set = field(default_factory=set)  # [File]
    implicit: set = field(default_factory=set)

    in_place = False
    description = "A badly described rule"
    rule: str = "echo"  # Must be overridden in subclass

    def __eq__(self, other):
        return self.original == other.original

    # Having a convenience function for "looks equal" is nice but
    # sometimes you actually need to know if it's literally the same
    # step
    def object_equals(self, other):
        return id(self) == id(other)

    def convert_dependencies(self, graph):
        if "needs" in self.original:
            if not isinstance(self.original["needs"], list):
                self.original["needs"] = [self.original["needs"]]
            self.original["needs"] = [
                graph._ensure_named_file(dependency)
                for dependency in self.original["needs"]
            ]

    @classmethod
    def write_rules(cls, writer):
        name = cls.__module__.split(".")[-1]
        writer.comment(name + ": " + cls.description)
        if os.name == "nt":
            cmd = "cmd /c " + cls.rule + " $stamp"
        else:
            cmd = cls.rule + " $stamp"
        writer.rule(
            name,
            f"{shell_quote(sys.executable)} -m gftools.builder.jobrunner {cmd}",
            description=name,
        )
        writer.newline()

    @property
    def opname(self):
        return self.__class__.__module__.split(".")[-1]

    def set_target(self, target):
        self._targets.add(target)

    def set_source(self, source):
        self._sources.add(source)

    @cached_property
    def stamppath(self):
        return NamedTemporaryFile().name + f".{self.opname}stamp"

    @property
    def variables(self):
        return {k: v for k, v in self.original.items() if k != "needs"}

    def build(self, writer):
        if self.postprocess:
            # Check this *is* a post-process step
            stamp = " && touch " + self.stamppath
            writer.comment(
                "Postprocessing "
                + ", ".join([t.path for t in self.targets])
                + " with "
                + self.__class__.__name__
            )
            writer.build(
                self.stamppath,
                self.opname,
                self.dependencies,
                variables={"stamp": stamp, **self.variables},
                implicit=[
                    t.path for t in self.implicit if t.path not in self.dependencies
                ],
            )
        else:
            writer.comment("Generating " + ", ".join([t.path for t in self.targets]))
            writer.build(
                list(set([t.path for t in self.targets])),
                self.opname,
                self.dependencies,
                variables=self.variables,
            )

    def __hash__(self):
        return hash(id(self))

    @property
    def dependencies(self):
        sources = [source.path for source in self._sources]
        if "needs" in self.original:
            return sources + [d.path for d in self.original["needs"]]
        return list(set(sources))

    @property
    def targets(self):
        return self._targets

    @property
    def first_target(self):
        return list(self.targets)[0]

    @property
    def first_source(self):
        return list(self._sources)[0]

    def validate(self):
        return True


class FontmakeOperationBase(OperationBase):
    COMPILER_ENV_KEY = "GFTOOLS_COMPILER"
    static = False
    format = "ttf"
    rule = "fontmake --output-path $out -o $format $fontmake_type $in $args"

    @property
    def variables(self):
        vars = defaultdict(str)
        vars["compiler"] = self.compiler
        vars["format"] = self.format  # buildTTF -> ttf, etc.
        for k, v in self.original.items():
            if k != "needs":
                vars[k] = v

        if self.first_source.is_glyphs:
            vars["fontmake_type"] = "-g"
        elif self.first_source.is_designspace:
            vars["fontmake_type"] = "-m"
        elif self.first_source.is_ufo:
            vars["fontmake_type"] = "-u"
        if "--verbose" not in vars["args"]:
            vars["args"] += " --verbose WARNING "

        return vars

    def validate(self):
        if self.static:
            if not self.first_source.exists():
                # We can't check this file (assume it was generated as part of the
                # build), so user is on their own.
                return
            if (
                self.first_source.is_glyphs
                and len(self.first_source.gsfont.masters) > 1
            ):
                raise ValueError(
                    f"Cannot build a static font from {self.first_source.path}"
                )
            if (
                self.first_source.designspace
                and len(self.first_source.designspace.sources) > 1
            ):
                raise ValueError(
                    f"Cannot build a static font from {self.first_source.path}"
                )


known_operations = {}

for mod in pkgutil.iter_modules([dirname(__file__)]):
    imp = importlib.import_module("gftools.builder.operations." + mod.name)
    classes = [
        (name, cls)
        for name, cls in inspect.getmembers(sys.modules[imp.__name__], inspect.isclass)
        if "OperationBase" not in name and issubclass(cls, OperationBase)
    ]
    if len(classes) > 1:
        raise ValueError(
            f"Too many classes in module gftools.builder.operations.{mod.name}"
        )
    known_operations[mod.name] = classes[0][1]
