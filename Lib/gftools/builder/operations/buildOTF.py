from gftools.builder.operations import FontmakeOperationBase


class BuildOTF(FontmakeOperationBase):
    description = "Build a OTF from a source file"
    rule = "fontmake --output-path $out -o otf $fontmake_type $in $args"

    def validate(self):
        if not self.first_source.exists():
            # We can't check this file (assume it was generated as part of the
            # build), so user is on their own.
            return
        if self.first_source.is_glyphs and len(self.first_source.gsfont.masters) > 1:
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
