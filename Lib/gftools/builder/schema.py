"""
This schema represents all known key/value pairs for the builder config file.
"""
from strictyaml import (
                        load,
                        Map,
                        MapPattern,
                        Str,
                        Int,
                        Seq,
                        YAMLError,
                        Optional,
                        Bool
                        )


stat_schema = Seq(
    Map({
        "name": Str(),
        "tag": Str(),
        "values": Seq(
            Map({
                "name": Str(),
                "value": Int(),
                Optional("nominalValue"): Int(),
                Optional("linkedValue"): Int(),
                Optional("rangeMinValue"): Int(),
                Optional("rangeMaxValue"): Int(),
                Optional("flags"): Int()
            })
        )
    }),
)

instance_schema = MapPattern(Str(), Seq(
    Map({
        Optional("familyName"): Str(),
        Optional("styleName"): Str(),
        "coordinates": MapPattern(Str(), Int()),
    })
))

schema = Map(
    {
        "sources": Seq(Str()),
        Optional("logLevel"): Str(),
        Optional("stylespaceFile"): Str(),
        Optional("stat"): stat_schema | MapPattern(Str(), stat_schema),
        Optional("familyName"): Str(),
        Optional("includeSourceFixes"): Bool(),
        Optional("stylespaceFile"): Str(),
        Optional("instances"): instance_schema,
        Optional("buildVariable"): Bool(),
        Optional("buildStatic"): Bool(),
        Optional("buildOTF"): Bool(),
        Optional("buildTTF"): Bool(),
        Optional("buildWebfont"): Bool(),
        Optional("outputDir"): Str(),
        Optional("vfDir"): Str(),
        Optional("ttDir"): Str(),
        Optional("otDir"): Str(),
        Optional("woffDir"): Str(),
        Optional("cleanUp"): Bool(),
        Optional("autohintTTF"): Bool(),
        Optional("axisOrder"): Seq(Str()),
        Optional("flattenComponents"): Bool(),
    }
)
