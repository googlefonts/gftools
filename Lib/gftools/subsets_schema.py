"""
Schema for the subsets accepted by gftools-add-ds-subsets and by the builder's
includeSubsets option.

This lives apart from gftools.subsetmerger so that the builder can validate
its config without importing the subset merger's dependencies.
"""

from strictyaml import HexInt, Int, Map, Optional, Seq, Str

subsets_schema = Seq(
    Map(
        {
            "from": Str() | Map({"repo": Str(), "path": Str()}),
            Optional("name"): Str(),
            Optional("glyphNames"): Seq(Str()),
            Optional("glyphNamesFile"): Str() | Seq(Str()),
            Optional("ranges"): Seq(
                Map({"start": (HexInt() | Int()), "end": (HexInt() | Int())})
            ),
            Optional("layoutHandling"): Str(),
            Optional("kernHandling"): Str(),
            Optional("force"): Str(),
            Optional("exclude_glyphs"): Seq(Str()),
            Optional("exclude_codepoints"): Seq(Str()),
            Optional("exclude_glyphs_file"): Str(),
            Optional("exclude_codepoints_file"): Str(),
        }
    )
)
