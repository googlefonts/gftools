import os
from tempfile import TemporaryDirectory

from gftools.builder.operations import OperationBase


class BuildSTAT(OperationBase):
    description = "Build a STAT table from one or more source files"
    operation_rule = (
        "gftools-gen-stat --out $tempdir $args -- $in && mv $finalfile $out"
    )
    postprocess_rule = "gftools-gen-stat --inplace $args -- $in"

    # OK, buildSTAT is a bit of a tricky one because of how gftools-gen-stat
    # works, and because of how we're likely to want to use it.
    # gftools-gen-stat is intrinsically in-place, although it can be used to
    # write files to a separate directory. The issue is that while we normally
    # want to run buildSTAT right at the end of the process, in which case
    # in-place is OK and we have a stamp file as the target, we might also want
    # to add a STAT table before doing other stuff to the font; in that case,
    # having a stamp file as a target causes problems for future steps.
    # To finesse the problem, we allow for only two cases: either this is a
    # postprocess step in which case it can affect multiple inputs, or it's an
    # "operation", in which case it may only have a single input.

    def validate(self):
        if not self.postprocess and len(self.targets) > 1:
            raise ValueError(
                "BuildSTAT can only have one target when used as an operation"
            )

    @classmethod
    def write_rules(cls, writer):
        name = cls.__module__.split(".")[-1]
        writer.comment(name + ": " + cls.description)
        if os.name == "nt":
            writer.rule(
                "buildSTAT-operation", "cmd /c " + cls.operation_rule + " $stamp"
            )
            writer.rule(
                "buildSTAT-postprocess", "cmd /c " + cls.postprocess_rule + " $stamp"
            )
        else:
            writer.rule("buildSTAT-operation", cls.operation_rule + " $stamp")
            writer.rule("buildSTAT-postprocess", cls.postprocess_rule + " $stamp")
        writer.newline()

    def build(self, writer):
        if self.postprocess:
            stamp = " && touch " + self.stamppath
            writer.comment(
                "Postprocessing "
                + ", ".join([t.path for t in self.targets])
                + " with "
                + self.__class__.__name__
            )
            writer.build(
                self.stamppath,
                "buildSTAT-postprocess",
                self.dependencies,
                variables={"stamp": stamp, **self.variables},
                implicit=[
                    t.path for t in self.implicit if t.path not in self.dependencies
                ],
            )
        else:
            tempdir = TemporaryDirectory().name
            finalfile = os.path.join(tempdir, self.first_source.basename)
            writer.comment("Generating " + ", ".join([t.path for t in self.targets]))
            writer.build(
                list(set([t.path for t in self.targets])),
                "buildSTAT-operation",
                self.dependencies,
                variables={
                    **self.variables,
                    "tempdir": tempdir,
                    "finalfile": finalfile,
                },
            )
