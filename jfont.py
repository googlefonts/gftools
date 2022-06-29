from fontTools.ttLib import TTFont


f = TTFont("/Users/marcfoley/Type/fonts/ofl/mavenpro/MavenPro[wght].ttf")


# basic recursion of complex obj
def recurs(obj):
    if isinstance(obj, (float, int, str, bool)):
        return obj
    if isinstance(obj, TTFont):
        return {tbl: recurs(obj[tbl]) for tbl in obj.keys() if tbl not in ["loca", "cmap"]}
    elif isinstance(obj, dict):
        return {k: recurs(v) for k, v in obj.items()}
    elif hasattr(obj, "__dict__"):
        return {k: recurs(getattr(obj, k)) for k in vars(obj)}
    elif isinstance(obj, (list, tuple, set)):
        return [recurs(i) for i in obj]



# diff of complex objs
def diff(obj1, obj2):
    # base case compare leaves
    if isinstance(obj1, (float, int, str, bool)) or isinstance(obj2, (float, int,str, bool)):
        if type(obj1) == type(obj2):
            if obj1 != obj2:
                return (obj1, obj2)
            else:
                return None
        elif not obj1:
            return (None, obj2)
        elif not obj2:
            return (obj1, None)
    
    # compare lists
    res = {}
    if isinstance(obj1, list) or isinstance(obj2, list):
        if type(obj1) == type(obj2):
            m = max(len(obj1), len(obj2))
            for i in range(m):
                if i < len(obj1) and i < len(obj2):
                    if diff(obj1[i], obj2[i]):
                        res[f"[{i}]"] = diff(obj1[i], obj2[i])
                elif i >= len(obj1):
                    if diff(None, obj2[i]):
                        res[f"[{i}]"] = diff(None, obj2[i])
                else:
                    if diff(obj1[i], None):
                        res[f"[{i}]"] = diff(obj1[i], None)
        elif isinstance(obj1, list):
            res = {f"[{i}]": diff(obj1[i], None) for i,_ in enumerate(obj1)}
        else:
            res = {f"[{i}]": diff(None, obj2[i]) for i,_ in enumerate(obj2)}

    # compare dicts
    if isinstance(obj1, dict) or isinstance(obj2, dict):
        if type(obj1) == type(obj2):
            same_keys = set(obj1) & set(obj2)
            same = {k: diff(obj1[k], obj2[k]) for k in same_keys if diff(obj1[k], obj2[k])}
            obj1_missing_keys = set(obj2) - set(obj1)
            obj1_missing = {k: diff(None, obj2[k]) for k in obj1_missing_keys}
            obj2_missing_keys = set(obj1) - set(obj2)
            obj2_missing = {k: diff(obj1[k], None) for k in obj2_missing_keys}
            res = {**same, **obj1_missing, **obj2_missing}
        elif isinstance(obj1, dict):
            res = {k: diff(obj1[k], None) for k in obj1}
        else:
            res = {k: diff(None, obj2[k]) for k in obj2}
    return res


obj1 = {"O": {"A": {"B": {"C": 10}}}}
obj2 = {"O": None}


obj2 = {"O": {"A": {"B": [10,20,{"C": 100}]}}}
obj1 = {"O": {"A": {"B": [10,30]}}}

from pprint import pprint
pprint(diff(obj1, obj2))