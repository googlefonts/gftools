import argparse
from copy import deepcopy as copy
from enum import Enum
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._n_a_m_e import table__n_a_m_e
from fontTools.ttLib.tables._f_v_a_r import table__f_v_a_r
from fontTools.ttLib.tables.S_T_A_T_ import table_S_T_A_T_
from fontTools.ttLib.tables._c_m_a_p import table__c_m_a_p


class_defs = {
    1: "Base Glyph",
    2: "Ligature Glyph",
    3: "Mark Glyph",
    4: "Component Glyph",
}

def serialise_name_table(obj):
    return {
        (r.nameID, r.platformID, r.platEncID, r.langID): r.toUnicode()
        for r in obj.names
    }


def serialise_fvar_table(obj, root):
    nametbl = root["name"]
    axes = {
        a.axisTag: {
            "minValue": a.minValue,
            "maxValue": a.maxValue,
            "defaultValue": a.defaultValue,
            "axisName": nametbl.getName(a.axisNameID, 3, 1, 0x409).toUnicode()
            # TODO get axis Name Value (will need ttFont obj)
        }
        for a in obj.axes
    }

    instances = {
        nametbl.getName(i.subfamilyNameID, 3, 1, 0x409).toUnicode(): {
            "coordinates": i.coordinates,
            # todo get ps name
#            "postscriptName": None if i.postscriptNameID == None else nametbl.getName(
#                i.postscriptNameID, 3, 1, 0x409
#            ).toUnicode(),
            "flags": i.flags,
        }
        for i in obj.instances
    }
    return {"axes": axes, "instances": instances}


def serialise_stat_table(obj, root):
    nametbl = root["name"]
    design_records = {
        d.AxisTag: {
            "order": d.AxisOrdering,
            "AxisName": nametbl.getName(d.AxisNameID, 3, 1, 0x409).toUnicode(),
        }
        for d in obj.table.DesignAxisRecord.Axis
    }
    if not obj.table.AxisValueArray:
        return {"design axis records": design_records}
    try:
        axis_values = {
            nametbl.getName(a.ValueNameID, 3, 1, 0x409).toUnicode(): {
                "format": a.Format,
                "AxisIndex": a.AxisIndex,
                "Flags": a.Flags,
                "Value": a.Value,
            }
            for a in obj.table.AxisValueArray.AxisValue
        }
    except:
        return {}
    return {"axis values": axis_values, "design axis records": design_records}


def serialise_cmap(obj):
    return {f"0x{hex(k)[2:].zfill(4).upper()}": v for k, v in obj.getBestCmap().items()}


def TTJ(ttFont):
    root = ttFont
    return _TTJ(ttFont, root)


def _TTJ(obj, root=None):
    """Convert a TTFont to Basic python types"""
    if isinstance(obj, (float, int, str, bool)):
        return obj

    # custom
    elif isinstance(obj, table__n_a_m_e):
        return serialise_name_table(obj)

    elif isinstance(obj, table__f_v_a_r):
        return serialise_fvar_table(obj, root)

    elif isinstance(obj, table_S_T_A_T_):
        return serialise_stat_table(obj, root)

    elif isinstance(obj, table__c_m_a_p):
        return serialise_cmap(obj)

    elif isinstance(obj, TTFont):
        return {k: _TTJ(obj[k], root) for k in obj.keys() if k not in ["loca"]}
    elif isinstance(obj, dict):
        return {k: _TTJ(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple, set)):
        return [_TTJ(i) for i in obj]
    elif hasattr(obj, "__dict__"):
        return {k: _TTJ(getattr(obj, k)) for k in vars(obj)}
    return obj


class Diff:
    def __init__(self, obj_a, obj_b):
        """A basic general purposes dict differ. Should not be tied to fonts!"""
        self.obj_a = obj_a 
        self.obj_b = obj_b
        self.diff = self.clean(self._diff(self.obj_a, self.obj_b))

    def _diff(self, obj1, obj2, path=[]):
        """Diff to json objects. Output as html"""
        if obj1 is None and obj2 is None:
            return False
        elif isinstance(obj1, (int, float, str)) and isinstance(obj2, (int, float, str)):
            if obj1 == obj2:
                return False
            return obj1, obj2
        elif isinstance(obj1, (int, float, str)) and obj2 is None:
            return obj1, obj2
        elif obj1 is None and isinstance(obj2, (int, float, str)):
            return obj1, obj2

        res = {}
        if isinstance(obj1, dict) and isinstance(obj2, dict):
            for k in set(obj1.keys()) | set(obj2.keys()):
                if k in obj1 and k in obj2:
                    res[k] = self._diff(obj1[k], obj2[k], path + [k])
                elif k in obj1 and k not in obj2:
                    res[k] = self._diff(obj1[k], None, path + [k])
                else:
                    res[k] = self._diff(None, obj2[k], path + [k])
        elif isinstance(obj1, dict) and not isinstance(obj2, dict):
            for k in obj1:
                res[k] = self._diff(obj1[k], obj2, path=path + [k])
        elif not isinstance(obj1, dict) and isinstance(obj2, dict):
            for k in obj2:
                res[k] = self._diff(obj1, obj2[k], path + [k])
        if isinstance(obj1, list) and isinstance(obj2, list):
            for i in range(max(len(obj1), len(obj2))):
                if i < len(obj1) and i < len(obj2):
                    res[i] = self._diff(obj1[i], obj2[i], path + [i])
                elif i < len(obj1) and i >= len(obj2):
                    res[i] = self._diff(obj1[i], None, path + [i])
                else:
                    res[i] = self._diff(None, obj2[i], path + [i])
        elif isinstance(obj1, list) and not isinstance(obj2, list):
            for i in range(len(obj1)):
                res[i] = self._diff(obj1[i], obj2, path + [i])
        elif not isinstance(obj1, list) and isinstance(obj2, list):
            for i in range(len(obj2)):
                res[i] = self._diff(obj1, obj2[i], path + [i])
        return res

    def clean(self, obj):
        """Remove any paths which are False or contain too many changes"""
        if obj is None:
            return None
        if isinstance(obj, tuple):
            return obj
        if obj == False:
            return False
        res = copy(obj)
        for k, v in obj.items():
            res[k] = self.clean(v)
            if res[k] == False or not res[k]:
                res.pop(k)
        if len(res) >= 133:
            return {"error": (f"There are {len(res)} changes, check manually!", "")}
        return res

    def render(self):
        return self._render(self.diff)

    def _render(self, obj, space=""):
        s = ""
        if not obj:
            return ""
        if isinstance(obj, tuple):
            return f'\n{space}<span class="attrib-before">{obj[0]}</span> <span class="attrib-after">{obj[1]}</span>'

        for k, v in obj.items():
            if isinstance(k, int):
                k = f"[{k}]"
            if space:
                hide = 'style="display:none"'
            else:
                hide = ""
            s += (
                f'\n{space}<div class="node" {hide}>\n{space}{k}'
                + self._render(v, space + "  ")
                + f"\n{space}</div>"
            )
        return s
    
    def summary(self):
        raise NotImplementedError()


class TTJDiff(Diff):
    def summary(self):
        doc = []
        obj = self.diff
        try:
            font_revision = obj["head"]["fontRevision"]
            if font_revision[0] == font_revision[1]:
                doc.append(f"<li>head.fontRevision is same {font_revision[0]}</li>")
            elif font_revision[0] > font_revision[1]:
                doc.append(
                    f"<li>head.fontRevision is less than older version {font_revision[0]} {font_revision[1]}</li>"
                )
            else:
                doc.append(
                    f"<li>head.fontRevision has been incremented from {font_revision[0]} to {font_revision[1]}</li>"
                )
        except:
            pass

        try:
            avar = obj["avar"]["segments"]
            if avar:
                doc.append(
                    "<li>Avar table has been modified. Please check all diffs to see if glyph color is lighter/darker.</li>"
                )
        except:
            pass

        try:
            names = obj["name"]
            nameids = set(k[0] for k, v in names.items() if v)
            menu_nameids = set([1, 2, 4, 6, 16, 17, 21, 22])

            changed_menu_nameids = menu_nameids & nameids
            if changed_menu_nameids:
                doc.append(
                    f"<li>NameIDs {changed_menu_nameids} have changed. This may affect application font menus.</li>"
                )

            changed_ps_nameid = set([6]) & nameids
            if changed_ps_nameid:
                doc.append(
                    f"<li>Postscript name has changed. This may cause issues for Adobe users if they update their fonts.</li>"
                )

            changed_vf_ps_name = set([25]) & nameids
            if changed_vf_ps_name:
                doc.append(
                    f"<li>nameID {25} has changed (Variations PostScript Name Prefix)</li>"
                )
        except:
            pass

        # FIX THIS
        try:
            for k, v in obj.items():
                if all(vv[0] == None for kk, vv in v.items()):
                    doc.append(f"<li>{k} table has been added</li>")
                elif all(vv[1] == None for kk, vv in v.items()):
                    doc.append(f"<li>{k} table has been removed</li>")
        except:
            pass
        return "\n".join(doc)
