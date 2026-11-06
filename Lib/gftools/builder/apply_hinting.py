"""A font's own TrueType hinting, kept as a text file beside its sources.

A source format cannot carry a compiled font's TrueType hinting: its programs
address the glyphs' points by index, and the device metrics tables (hdmx, LTSH,
VDMX) have no source form. A hinting file holds them, and is applied to the
compiled font, which must have the same points:

- ``fpgm``, ``prep``: programs in fontTools assembly
- ``cvt``: control values
- ``gasp``: ``{ppem: behavior}``
- ``maxp``: the TrueType limits (maxZones ... maxSizeOfInstructions)
- ``head_flag_3``: whether ppem is rounded to an integer
- ``head_flags_2_4``: head flags bits 2 (instructions may depend on point size)
  and 4 (instructions may alter advance width), as the release sets them
- ``hdmx``, ``LTSH``, ``VDMX``: device metrics, when the font has them
- ``glyphs``: ``{glyph: {"assembly": program, "id": digest}}``; the id is
  the SHA-256 of the glyph's point text (see ``point_text``)
- ``components``: each composite's component flags that affect hinting
- ``contour_starts``: ``{glyph: [[x, y, on], ...]}``, each contour's first
  point, which a source does not fix (a closed path cannot start off-curve, and
  converters and compilers choose their own start)
- ``transforms``: component matrices whose F2Dot14 values a source does not
  keep at four decimals
- ``lsb_shifts``: ``{glyph: {"xmin": x, "lsb": lsb, "bbox": [xMin, yMin,
  xMax, yMax]}}``, a simple glyph whose left side bearing differs from its
  recorded xMin (a converter may draw it shifted by the difference), or whose
  recorded box differs from its points' (a stale box): its
  points are moved so that the leftmost is at ``x`` again, and its recorded box
  and side bearing restored, which a TrueType rasterizer places it by
- ``boxes``: ``{composite: {"bbox": [xMin, yMin, xMax, yMax], "lsb": lsb}}``,
  a composite whose recorded box differs from the one its components give (a
  stale box, which a TrueType rasterizer places the glyph by): restored
- ``offsets``: ``{composite: [[x, y], ...]}``, the component offsets of a
  composite that places a shifted glyph, or is shifted itself
- ``glyph_order``: the font's glyph names in order; a name the compiled font
  does not have (a release with duplicate or no glyph names) is matched by its
  index, when both fonts have as many glyphs
- ``midpoints``: ``{glyph: {"points": [index, ...], "ends": [...]}}``, on-curve
  points exactly halfway between two off-curves, which a compiler may drop as
  implied, with the glyph's contour ends

Applying refuses every glyph whose points do not match the file (a program
would address other points), and saves nothing in that case.
"""

import argparse
import array
import copy
import hashlib
import json
import sys

from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import ttProgram

FORMAT_VERSION = "1"
MAXP = (
    "maxZones",
    "maxTwilightPoints",
    "maxStorage",
    "maxFunctionDefs",
    "maxInstructionDefs",
    "maxStackElements",
    "maxSizeOfInstructions",
)
# ROUND_XY_TO_GRID, USE_MY_METRICS, OVERLAP_COMPOUND, SCALED_COMPONENT_OFFSET,
# UNSCALED_COMPONENT_OFFSET
COMPONENT_FLAGS = 0x0004 | 0x0200 | 0x0400 | 0x0800 | 0x1000
F2DOT14_UNIT = 1 / 16384


class HintingMismatch(Exception):
    pass


def _assembly(program):
    return "\n".join(program.getAssembly())


def _program(text):
    program = ttProgram.Program()
    program.fromAssembly(text.splitlines())
    return program


def _f2dot14(value):
    return round(value * 16384)


def point_text(font, name, depth=0):
    """A glyph's points as text: its advance, then each contour's points as
    ``x,y,on;`` closed by ``|``, or each component as ``[`` its own text,
    its F2Dot14 matrix and its offset ``]``. Two glyphs with the same text
    give a TrueType program the same points."""
    if depth > 64:
        raise HintingMismatch("%s: components nest too deeply" % name)
    glyph = font["glyf"][name]
    parts = ["w%d" % font["hmtx"][name][0]]
    if glyph.isComposite():
        for c in glyph.components:
            matrix = ",".join(str(_f2dot14(v)) for v in _matrix(c))
            if hasattr(c, "firstPt"):
                offset = "p%d,%d" % (c.firstPt, c.secondPt)
            else:
                offset = "%d,%d" % (c.x, c.y)
            parts.append(
                "[%s(%s;%s)]"
                % (point_text(font, c.glyphName, depth + 1), matrix, offset)
            )
    elif glyph.numberOfContours > 0:
        first = 0
        for end in glyph.endPtsOfContours:
            for i in range(first, end + 1):
                x, y = glyph.coordinates[i]
                parts.append("%d,%d,%d;" % (x, y, glyph.flags[i] & 1))
            parts.append("|")
            first = end + 1
    return "".join(parts)


def glyph_id(font, name):
    """The digest a glyph's program is checked against."""
    return hashlib.sha256(point_text(font, name).encode("ascii")).hexdigest()


def _matrix(component):
    if hasattr(component, "transform"):
        return list(component.transform[0]) + list(component.transform[1])
    return [1, 0, 0, 1]


def extract(font):
    """The hinting of a TrueType font, as a hinting file's data."""
    glyf = font["glyf"]
    data = {"formatVersion": FORMAT_VERSION, "glyph_order": font.getGlyphOrder()}
    for tag in ("fpgm", "prep"):
        if tag in font:
            data[tag] = _assembly(font[tag].program)
    if "cvt " in font:
        data["cvt"] = list(font["cvt "].values)
    if "gasp" in font:
        data["gasp"] = {str(k): v for k, v in sorted(font["gasp"].gaspRange.items())}
    data["maxp"] = {k: getattr(font["maxp"], k) for k in MAXP}
    data["head_flag_3"] = bool(font["head"].flags & 8)
    data["head_flags_2_4"] = font["head"].flags & 0x14
    if "hdmx" in font:
        data["hdmx"] = {str(p): dict(w) for p, w in sorted(font["hdmx"].hdmx.items())}
    if "LTSH" in font:
        data["LTSH"] = dict(font["LTSH"].yPels)
    if "VDMX" in font:
        vdmx = font["VDMX"]
        data["VDMX"] = {
            "version": vdmx.version,
            "ratRanges": [dict(r) for r in vdmx.ratRanges],
            "groups": [{str(k): list(v) for k, v in g.items()} for g in vdmx.groups],
        }
    glyphs, components, starts, transforms, midpoints = {}, {}, {}, {}, {}
    shifts, offsets = {}, {}
    for name in font.getGlyphOrder():
        glyph = glyf[name]
        if not glyph.isComposite() and glyph.numberOfContours > 0:
            shift = font["hmtx"][name][1] - glyph.xMin
            xs = [x for x, _ in glyph.coordinates]
            ys = [y for _, y in glyph.coordinates]
            actual = [min(xs), min(ys), max(xs), max(ys)]
            if shift or actual != [glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax]:
                shifts[name] = {
                    "xmin": min(x for x, _ in glyph.coordinates),
                    "lsb": font["hmtx"][name][1],
                    "bbox": [glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax],
                }
    boxes = {}
    for name in font.getGlyphOrder():
        glyph = glyf[name]
        if glyph.isComposite():
            recorded = [glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax]
            fresh = copy.deepcopy(glyph)
            fresh.recalcBounds(glyf)
            if recorded != [fresh.xMin, fresh.yMin, fresh.xMax, fresh.yMax]:
                boxes[name] = {"bbox": recorded, "lsb": font["hmtx"][name][1]}
    for name in font.getGlyphOrder():
        glyph = glyf[name]
        if glyph.isComposite() and (
            font["hmtx"][name][1] != glyph.xMin
            or any(c.glyphName in shifts for c in glyph.components)
        ):
            offsets[name] = [
                [c.x, c.y] if not hasattr(c, "firstPt") else None
                for c in glyph.components
            ]
    for name in font.getGlyphOrder():
        glyph = glyf[name]
        if hasattr(glyph, "program") and glyph.program.getBytecode():
            glyphs[name] = {
                "assembly": _assembly(glyph.program),
                "id": glyph_id(font, name),
            }
        if glyph.isComposite():
            components[name] = [c.flags & COMPONENT_FLAGS for c in glyph.components]
            matrices = [_matrix(c) for c in glyph.components]
            if any(
                round(round(v, 4) * 16384) != round(v * 16384)
                for m in matrices
                for v in m
            ):
                transforms[name] = matrices
        elif glyph.numberOfContours > 0:
            found = _midpoints(glyph)
            if found:
                midpoints[name] = {
                    "points": found,
                    "ends": list(glyph.endPtsOfContours),
                }
            first = 0
            for end in glyph.endPtsOfContours:
                x, y = glyph.coordinates[first]
                starts.setdefault(name, []).append([x, y, glyph.flags[first] & 1])
                first = end + 1
    data.update(
        glyphs=glyphs,
        components=components,
        contour_starts=starts,
        transforms=transforms,
        midpoints=midpoints,
        lsb_shifts=shifts,
        offsets=offsets,
        boxes=boxes,
    )
    return data


def _restore_starts(glyph, starts, midpoints=None):
    """Rotate each contour to start where the release's does. A start the
    compiler dropped as an implied on-curve (see ``midpoints``, which also gives
    the release's contour ends) is put back later, at the contour's start."""
    coords, flags = list(glyph.coordinates), list(glyph.flags)
    ends = list(glyph.endPtsOfContours)
    if len(ends) != len(starts):
        return False
    dropped = set()
    if midpoints:
        release_starts = [0] + [e + 1 for e in midpoints["ends"][:-1]]
        dropped = {c for c, s in enumerate(release_starts) if s in midpoints["points"]}
    first = 0
    for c, (end, (x, y, on)) in enumerate(zip(ends, starts)):
        indices = list(range(first, end + 1))
        at = [
            k
            for k, j in enumerate(indices)
            if tuple(coords[j]) == (x, y) and bool(flags[j] & 1) == bool(on)
        ]
        if not at and c in dropped:
            # the start was dropped: begin after the two off-curves it lay between
            n = len(indices)
            at = [
                k
                for k in range(n)
                if not flags[indices[k - 1]] & 1
                and not flags[indices[k]] & 1
                and coords[indices[k - 1]][0] + coords[indices[k]][0] == 2 * x
                and coords[indices[k - 1]][1] + coords[indices[k]][1] == 2 * y
            ]
            if len(at) != 1:
                return False
        if len(at) == 1:
            order = indices[at[0] :] + indices[: at[0]]
            coords[first : end + 1] = [coords[j] for j in order]
            flags[first : end + 1] = [flags[j] for j in order]
        elif not (at and at[0] == 0):
            return False
        first = end + 1
    glyph.coordinates = type(glyph.coordinates)(coords)
    glyph.flags = array.array("B", flags)
    return True


def _restore_transforms(glyph, matrices):
    if len(glyph.components) != len(matrices):
        return False
    for component, matrix in zip(glyph.components, matrices):
        if any(
            abs(a - b) > 1.5 * F2DOT14_UNIT for a, b in zip(_matrix(component), matrix)
        ):
            return False
    for component, matrix in zip(glyph.components, matrices):
        if matrix != [1, 0, 0, 1]:
            component.transform = [[matrix[0], matrix[1]], [matrix[2], matrix[3]]]
    return True


def _midpoints(glyph):
    coords, flags, first, found = list(glyph.coordinates), list(glyph.flags), 0, []
    for end in glyph.endPtsOfContours:
        indices = list(range(first, end + 1))
        for k, i in enumerate(indices):
            p, q = indices[k - 1], indices[(k + 1) % len(indices)]
            if (
                flags[i] & 1
                and not flags[p] & 1
                and not flags[q] & 1
                and coords[p][0] + coords[q][0] == 2 * coords[i][0]
                and coords[p][1] + coords[q][1] == 2 * coords[i][1]
            ):
                found.append(i)
        first = end + 1
    return found


def _restore_midpoints(glyph, points, release_ends):
    coords, flags = list(glyph.coordinates), list(glyph.flags)
    ends = list(glyph.endPtsOfContours)
    if len(ends) != len(release_ends):
        return False
    for i in sorted(points):
        c = next((k for k, e in enumerate(release_ends) if i <= e), None)
        if c is None:
            return False
        start, end = (ends[c - 1] + 1 if c else 0), ends[c]
        n = end - start + 1
        if i <= end and flags[i] & 1:
            p, q = start + (i - start - 1) % n, start + (i - start + 1) % n
            if (
                not flags[p] & 1
                and not flags[q] & 1
                and coords[p][0] + coords[q][0] == 2 * coords[i][0]
                and coords[p][1] + coords[q][1] == 2 * coords[i][1]
            ):
                continue  # kept by the compiler
        prev, nxt = start + (i - start - 1) % n, (i if i <= end else start)
        if flags[prev] & 1 or flags[nxt] & 1:
            return False
        sx, sy = coords[prev][0] + coords[nxt][0], coords[prev][1] + coords[nxt][1]
        if sx % 2 or sy % 2:
            return False
        coords.insert(i, (sx // 2, sy // 2))
        flags.insert(i, 1)
        ends = ends[:c] + [e + 1 for e in ends[c:]]
    glyph.coordinates = type(glyph.coordinates)(coords)
    glyph.flags = array.array("B", flags)
    glyph.endPtsOfContours = ends
    return True


GLYPH_KEYED = (
    "glyphs",
    "components",
    "contour_starts",
    "transforms",
    "midpoints",
    "lsb_shifts",
    "offsets",
    "boxes",
    "LTSH",
)


def _rekey(font, data):
    """The data with the file's glyph names replaced by the compiled font's."""
    ours = font.getGlyphOrder()
    have = set(ours)
    theirs = data.get("glyph_order") or []
    by_index = (
        {n: ours[i] for i, n in enumerate(theirs)} if len(theirs) == len(ours) else {}
    )

    def name(n):
        return n if n in have else by_index.get(n, n)

    out = dict(data)
    for key in GLYPH_KEYED:
        if key in data:
            out[key] = {name(n): v for n, v in data[key].items()}
    if "hdmx" in data:
        out["hdmx"] = {
            p: {name(n): w for n, w in row.items()} for p, row in data["hdmx"].items()
        }
    return out


def apply(font, data):
    """Give a compiled TrueType font the hinting of a hinting file's data."""
    if data.get("formatVersion") != FORMAT_VERSION:
        raise HintingMismatch(
            "unknown hinting file formatVersion %r" % data.get("formatVersion")
        )
    data = _rekey(font, data)
    glyf = font["glyf"]
    bad = []
    for name, entry in data.get("lsb_shifts", {}).items():
        glyph = glyf[name] if name in glyf else None
        if glyph is None or glyph.isComposite() or glyph.numberOfContours <= 0:
            bad.append(name)
            continue
        move = entry["xmin"] - min(x for x, _ in glyph.coordinates)
        glyph.coordinates = type(glyph.coordinates)(
            [(x + move, y) for x, y in glyph.coordinates]
        )
        glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax = entry["bbox"]
        font["hmtx"][name] = (font["hmtx"][name][0], entry["lsb"])
    for name, offs in data.get("offsets", {}).items():
        glyph = glyf[name] if name in glyf else None
        if (
            glyph is None
            or not glyph.isComposite()
            or len(glyph.components) != len(offs)
        ):
            bad.append(name)
            continue
        for component, off in zip(glyph.components, offs):
            if off is not None and not hasattr(component, "firstPt"):
                component.x, component.y = off
    for name, entry in data.get("boxes", {}).items():
        glyph = glyf[name] if name in glyf else None
        if glyph is None or not glyph.isComposite():
            bad.append(name)
            continue
        glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax = entry["bbox"]
        font["hmtx"][name] = (font["hmtx"][name][0], entry["lsb"])
    for name, starts in data.get("contour_starts", {}).items():
        if (
            name not in glyf
            or glyf[name].isComposite()
            or not _restore_starts(
                glyf[name], starts, data.get("midpoints", {}).get(name)
            )
        ):
            bad.append(name)
    for name, entry in data.get("midpoints", {}).items():
        glyph = glyf[name] if name in glyf else None
        if (
            glyph is None
            or glyph.isComposite()
            or not _restore_midpoints(glyph, entry["points"], entry["ends"])
        ):
            bad.append(name)
    for name, matrices in data.get("transforms", {}).items():
        if (
            name not in glyf
            or not glyf[name].isComposite()
            or not _restore_transforms(glyf[name], matrices)
        ):
            bad.append(name)
    for name, flags in data.get("components", {}).items():
        glyph = glyf[name] if name in glyf else None
        if (
            glyph is None
            or not glyph.isComposite()
            or len(glyph.components) != len(flags)
        ):
            bad.append(name)
            continue
        for component, f in zip(glyph.components, flags):
            component.flags = (component.flags & ~COMPONENT_FLAGS) | f
    for name, entry in data["glyphs"].items():
        if name not in glyf or glyph_id(font, name) != entry["id"]:
            bad.append(name)
    if bad:
        raise HintingMismatch(
            "%d glyph(s) do not have the points or components the hinting file was "
            "written for: %s" % (len(bad), " ".join(sorted(set(bad))[:20]))
        )
    # every other glyph's box is its points', composites' from their components'
    # points, as a compiler computes it; recorded (stale) boxes stay
    kept = set(data.get("lsb_shifts", {})) | set(data.get("boxes", {}))
    order = font.getGlyphOrder()
    for name in order:
        if name not in kept and not glyf[name].isComposite():
            glyf[name].recalcBounds(glyf)
    for name in order:
        if name not in kept and glyf[name].isComposite():
            glyf[name].recalcBounds(glyf)
    # a composite's recalculation recalculates its components too: put back the
    # recorded boxes
    for key in ("lsb_shifts", "boxes"):
        for name, entry in data.get(key, {}).items():
            if name in glyf:
                g = glyf[name]
                g.xMin, g.yMin, g.xMax, g.yMax = entry["bbox"]
    for name in font.getGlyphOrder():
        glyph = glyf[name]
        if name in data["glyphs"]:
            glyph.program = _program(data["glyphs"][name]["assembly"])
        elif hasattr(glyph, "program"):
            glyph.program = ttProgram.Program()
            glyph.program.fromBytecode(b"")
    for tag in ("fpgm", "prep"):
        if tag in data:
            font[tag] = newTable(tag)
            font[tag].program = _program(data[tag])
        elif tag in font:
            del font[tag]
    if "cvt" in data:
        font["cvt "] = newTable("cvt ")
        font["cvt "].values = array.array("h", data["cvt"])
    elif "cvt " in font:
        del font["cvt "]
    if "gasp" in data:
        font["gasp"] = newTable("gasp")
        font["gasp"].version = 1
        font["gasp"].gaspRange = {int(k): v for k, v in data["gasp"].items()}
    for key, value in data["maxp"].items():
        setattr(font["maxp"], key, value)
    font["head"].flags = (font["head"].flags & ~8) | (8 if data["head_flag_3"] else 0)
    if "head_flags_2_4" in data:
        font["head"].flags = (font["head"].flags & ~0x14) | data["head_flags_2_4"]
    for tag in ("hdmx", "LTSH", "VDMX"):
        if tag in font and tag not in data:
            del font[tag]
    if "hdmx" in data:
        font["hdmx"] = newTable("hdmx")
        font["hdmx"].hdmx = {int(p): w for p, w in data["hdmx"].items()}
    if "LTSH" in data:
        font["LTSH"] = newTable("LTSH")
        font["LTSH"].version, font["LTSH"].yPels = 0, data["LTSH"]
    if "VDMX" in data:
        vdmx = font["VDMX"] = newTable("VDMX")
        vdmx.version = data["VDMX"]["version"]
        vdmx.ratRanges = data["VDMX"]["ratRanges"]
        vdmx.groups = [
            {int(k): tuple(v) for k, v in g.items()} for g in data["VDMX"]["groups"]
        ]
        vdmx.numRecs, vdmx.numRatios = len(vdmx.groups), len(vdmx.ratRanges)


def main(args=None):
    parser = argparse.ArgumentParser(
        description="Apply a hinting file to a compiled TrueType font"
    )
    parser.add_argument("-o", "--output", metavar="TTF", help="file to save on")
    parser.add_argument("font", metavar="TTF", help="font file")
    parser.add_argument("hinting", metavar="JSON", help="hinting file")
    args = parser.parse_args(args)
    # the glyphs' recorded boxes are kept: a release's can differ from its points
    font = TTFont(args.font, recalcBBoxes=False)
    with open(args.hinting) as fh:
        data = json.load(fh)
    try:
        apply(font, data)
    except HintingMismatch as e:
        sys.exit("%s: %s" % (args.hinting, e))
    # maxp's TrueType limits are stated by the file, not recalculated
    font.save(args.output or args.font)


def extract_main(args=None):
    parser = argparse.ArgumentParser(
        description="Write a TrueType font's hinting as a hinting file"
    )
    parser.add_argument(
        "-o", "--output", metavar="JSON", help="file to write (default: stdout)"
    )
    parser.add_argument("font", metavar="TTF", help="font file")
    args = parser.parse_args(args)
    text = json.dumps(extract(TTFont(args.font)), indent=1, sort_keys=True) + "\n"
    if args.output:
        with open(args.output, "w") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
