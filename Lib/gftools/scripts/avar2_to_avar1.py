#!/usr/bin/env python3
"""
Flatten a variable font with an avar2 table into a plain avar1 variable font.

avar2 (https://github.com/harfbuzz/boring-expansion-spec/blob/main/avar2.md)
remaps each axis's normalized coordinate as a function of *several* axes at
once, which avar1 cannot express. To flatten it we resample the designspace:
static instances ("masters") are cut from the avar2 font and a new variable
font is built from them with varLib. All fvar axes are kept.

Master locations are read off the font instead of guessed: a master is
cut at the peak vector of every avar2 VarStore region and of every
gvar/cvar tuple (plus the default and each axis's reachable extremes).
These sparse locations are the implied masters the font itself was built
from — for Crispy that is the opsz x wdth x wght grid of avar2 knots (the
named-instance positions) plus the font's per-glyph parametric
intermediates. Using peak vectors rather than a tensor product of all
knots keeps the master count proportional to the font's own complexity
instead of 2**n_axes, and every master is a true sample of the original,
so the two fonts match exactly at all of those locations.

Between and around those locations the rebuilt variation model is an
approximation: axis combinations that have no region of their own (e.g.
wght moved together with XOPQ) interpolate additively, and cross-axis
tuples evaluated through the avar2 mapping make the true composite
piecewise-polynomial, which a piecewise-linear model can only approach.

To quantify this, the new font is compared against the original at the
midpoint of every knot cell (where interpolation error peaks) plus a few
random cross-group locations, and the worst outline error is reported in
font units. With --tolerance, extra masters are inserted at the worst
midpoints and the font rebuilt until the in-group error is below the
threshold (or --max-rounds is hit).

A yaml based mapping file can be provided to add avar1 mappings to the
output font. It has the following format:

`
wght:
  400: 380
  500: 520
  700: 700
wdth:
  ...
`

Between knots there is one more source of error that --grid-cuts cannot
target: the mapping is additive, so an *output* axis can cross its own
default (or one of its intermediate masters) part-way between two input
knots. gvar switches to a different master there, so the outline's slope
changes at a point no input knot marks. Adding such a point as a regular
master does not help: varLib has to invent a tent for it, and for an
off-grid location the tent reaches to the axis defaults, so the correction
leaks into neighbouring cells.

Refinement escapes the grid instead. After the font is built, each
refinement location is instanced in both fonts, and the per-glyph residual
is appended to gvar as a tuple with an explicit tent: on every axis where
the location is off its default the tent runs from the previous knot
through the location to the next knot, so it touches only the cells
around it. HVAR is rebuilt from the final gvar. The result is exact at
the refinement locations and unchanged outside their cells. Locations
come from --refine-at (user coordinates of the output font, repeatable)
and from --refine-crossings, which checks every grid edge for crossings
(cheap: the mapping is linear along an edge) and refines at each one
where the output axis travels at least --crossing-min (normalized) on
both sides; --max-refine keeps only the strongest N. A tent cannot be
localized around an axis default, so for every axis a location sits at
the default of, a "guard" master at the neighbouring knots cancels the
leak along that axis (--no-refine-guards to skip them).

Usage:
# default
gftools avar2-to-avar1 path/to/variable-font.ttf

# refine until the worst in-group error is below 2 font units
gftools avar2-to-avar1 path/to/variable-font.ttf --tolerance 2

# also sample the opsz x wdth x wght interior with 3 x 5 x 9 grid masters
gftools avar2-to-avar1 path/to/variable-font.ttf --grid opsz:3,wdth:5,wght:9
# masters at exactly the positions the product uses (default and extremes
# are always added); unchanged by later edits to the font's mappings
gftools avar2-to-avar1 path/to/variable-font.ttf --grid wght:300/400/700,opsz:14/21

# refine at the kinks the grid cannot express, plus a chosen location
gftools avar2-to-avar1 font.ttf --grid wght:300/400/700,wdth:75/100/124,opsz:9/14/21 \\
    --refine-crossings --refine-at wght=352,wdth=25,opsz=9

# with custom avar1 mapping and outpath
gftools avar2-to-avar1 font.ttf --mapping mapping.yaml -o avar1-font.ttf
"""

import argparse
import itertools
import logging
import os
import random
import tempfile

import yaml
from fontTools.designspaceLib import (
    AxisDescriptor,
    DesignSpaceDocument,
    InstanceDescriptor,
    RuleDescriptor,
    SourceDescriptor,
)
from fontTools.misc.cliTools import makeOutputFileName
from fontTools.otlLib.builder import buildStatTable
from fontTools.ttLib import TTFont
from fontTools.varLib import build as varlib_build
from fontTools.varLib import instancer
from fontTools.misc.roundTools import otRound
from fontTools.ttLib import newTable
from fontTools.ttLib.tables import otTables as ot
from fontTools.ttLib.tables.TupleVariation import TupleVariation
from fontTools.varLib.iup import iup_delta_optimize
from fontTools.varLib.models import piecewiseLinearMap, normalizeValue
from fontTools.varLib.varStore import OnlineVarStoreBuilder

log = logging.getLogger("gftools.avar2_to_avar1")


def _denormalize(value, triple):
    minimum, default, maximum = triple
    if value < 0:
        return default + value * (default - minimum)
    return default + value * (maximum - default)


def _avar2_knots_and_edges(avar, axis_tags):
    """Per-axis normalized knots and axis co-occurrence sets from the avar2
    VarStore regions."""
    knots, edges = {}, []
    varstore = avar.table.VarStore
    if varstore is None:
        return knots, edges
    for region in varstore.VarRegionList.Region:
        active = {}
        for tag, axis in zip(axis_tags, region.VarRegionAxis):
            if axis.PeakCoord != 0:
                active[tag] = (axis.StartCoord, axis.PeakCoord, axis.EndCoord)
        for tag, tent in active.items():
            knots.setdefault(tag, set()).update(tent)
        if active:
            edges.append(set(active))
    return knots, edges


def _tuplevar_knots_and_edges(list_of_variations):
    """Same as above, from gvar/cvar TupleVariations."""
    knots, edges = {}, []
    for variations in list_of_variations:
        for tv in variations:
            active = {t: tent for t, tent in tv.axes.items() if tent[1] != 0}
            for tag, tent in active.items():
                knots.setdefault(tag, set()).update(tent)
            if active:
                edges.append(set(active))
    return knots, edges


def _interaction_groups(varying_tags, edges):
    """Union-find axes into groups of axes that co-occur in some region."""
    parent = {t: t for t in varying_tags}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for edge in edges:
        tags = [t for t in edge if t in parent]
        for other in tags[1:]:
            parent[find(other)] = find(tags[0])

    groups = {}
    for t in varying_tags:
        groups.setdefault(find(t), []).append(t)
    return sorted(groups.values(), key=lambda g: varying_tags.index(g[0]))


def _clean_knots(raw_knots, fvar_axes):
    """Clamp knots to what the fvar range can reach, always include the
    default and the reachable extremes, and sort."""
    knots = {}
    for axis in fvar_axes:
        tag = axis.axisTag
        if tag not in raw_knots:
            continue
        lo = -1.0 if axis.minValue < axis.defaultValue else 0.0
        hi = 1.0 if axis.maxValue > axis.defaultValue else 0.0
        vals = {0.0, lo, hi}
        vals.update(v for v in raw_knots[tag] if lo < v < hi)
        knots[tag] = sorted(vals)
    return knots


def _peak_vectors(avar, axis_tags, tuple_vars):
    """Distinct peak vectors of every avar2 region and every gvar/cvar
    tuple: the sparse master locations the font itself is built from."""
    index = {t: i for i, t in enumerate(axis_tags)}
    vectors = set()
    varstore = avar.table.VarStore
    if varstore is not None:
        for region in varstore.VarRegionList.Region:
            vec = tuple(axis.PeakCoord for axis in region.VarRegionAxis)
            if any(vec):
                vectors.add(vec)
    for variations in tuple_vars:
        for tv in variations:
            vec = [0.0] * len(axis_tags)
            for tag, (_, peak, _) in tv.axes.items():
                vec[index[tag]] = peak
            if any(vec):
                vectors.add(tuple(vec))
    return vectors


def _parse_grid_spec(spec):
    """Parse ``opsz:3,wdth:5,wght`` into ``{"opsz": 3, "wdth": 5, "wght": None}``.
    A bare tag means: use every knot the font has on that axis. A slash
    list, ``wght:300/400/700``, means: masters at exactly those user
    positions (``{"wght": [300.0, 400.0, 700.0]}``)."""
    counts = {}
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        tag, sep, count = token.partition(":")
        tag = tag.strip()
        if not sep:
            counts[tag] = None
            continue
        if "/" in count:
            try:
                counts[tag] = [float(v) for v in count.split("/") if v.strip()]
            except ValueError:
                raise ValueError(f"--grid: bad position list in {token!r}")
            continue
        try:
            counts[tag] = int(count)
        except ValueError:
            raise ValueError(f"--grid: bad master count in {token!r}")
    return counts


def _grid_knots(knots, count, cuts=0):
    """Choose the knots an axis contributes to the --grid tensor product.

    knots is the axis's sorted normalized knot list (always containing
    the default and the reachable extremes). With count None, every
    knot is used and each interval is subdivided ``cuts`` times. With a
    count, exactly that many knots are returned: the default and the
    extremes always, then

    - fewer than the font's knots: a subset of the font's own knots,
      spread as evenly as possible (farthest-point selection), because
      the font is exact at its knots;
    - more than the font's knots: all of them, bisecting the largest
      interval until the count is reached.
    """
    if count is None:
        values = set(knots)
        for lo, hi in zip(knots[:-1], knots[1:]):
            for i in range(1, cuts + 1):
                values.add(lo + (hi - lo) * i / (cuts + 1))
        return sorted(values)

    required = sorted({knots[0], 0.0, knots[-1]})
    if count < len(required):
        raise ValueError(
            f"--grid: count {count} is below the {len(required)} knots "
            f"(default and extremes) the axis needs"
        )
    if count <= len(knots):
        chosen = list(required)
        candidates = [k for k in knots if k not in chosen]
        while len(chosen) < count:
            best = max(candidates, key=lambda c: min(abs(c - s) for s in chosen))
            chosen.append(best)
            candidates.remove(best)
        return sorted(chosen)

    chosen = list(knots)
    while len(chosen) < count:
        gaps = [(hi - lo, lo, hi) for lo, hi in zip(chosen[:-1], chosen[1:])]
        _, lo, hi = max(gaps)
        chosen.append((lo + hi) / 2)
        chosen.sort()
    return chosen


def _crossings(v0, v1, breakpoints):
    """Parameters t in (0, 1) at which the straight path from v0 to v1
    passes a breakpoint strictly between them."""
    if v0 == v1:
        return []
    lo, hi = min(v0, v1), max(v0, v1)
    return [(b - v0) / (v1 - v0) for b in breakpoints if lo < b < hi]


def _outline_diff(font_a, font_b):
    """Worst per-point coordinate difference between two static fonts."""
    glyf_a, glyf_b = font_a["glyf"], font_b["glyf"]
    worst, worst_glyph = 0.0, None
    for gname in font_a.getGlyphOrder():
        coords_a = glyf_a[gname].getCoordinates(glyf_a)[0]
        coords_b = glyf_b[gname].getCoordinates(glyf_b)[0]
        if len(coords_a) != len(coords_b):
            return float("inf"), gname
        for (xa, ya), (xb, yb) in zip(coords_a, coords_b):
            d = max(abs(xa - xb), abs(ya - yb))
            if d > worst:
                worst, worst_glyph = d, gname
    return worst, worst_glyph


# ---------------------------------------------------------------- refinement
#
# Local masters appended to the built font's gvar with explicit tents, so a
# correction at an off-grid location stays inside the cells around it.
# Locations here are normalized coordinates of the *output* font, keyed by
# its fvar axes; axes at 0 are at their default.


def _parse_location(text):
    """'wght=352,opsz=9' -> {'wght': 352.0, 'opsz': 9.0}"""
    loc = {}
    for token in text.split(","):
        token = token.strip()
        if not token:
            continue
        tag, sep, value = token.partition("=")
        if not sep:
            raise ValueError(f"bad location {text!r}: expected tag=value")
        try:
            loc[tag.strip()] = float(value)
        except ValueError:
            raise ValueError(f"bad location {text!r}: {value!r} is not a number")
    return loc


def _axis_knots(font):
    """Per axis of `font`, the sorted normalized positions it has masters
    at: gvar tuple peaks plus the default and the reachable extremes."""
    knots = {}
    for axis in font["fvar"].axes:
        lo = -1.0 if axis.minValue < axis.defaultValue else 0.0
        hi = 1.0 if axis.maxValue > axis.defaultValue else 0.0
        knots[axis.axisTag] = {lo, 0.0, hi}
    for variations in font["gvar"].variations.values():
        for tv in variations:
            for tag, (_, peak, _) in tv.axes.items():
                knots[tag].add(peak)
    return {tag: sorted(vals) for tag, vals in knots.items()}


def _tent(knots, v):
    """Support (start, peak, end) that keeps a master at `v` inside its
    cells: from the previous knot to the next, never crossing the default."""
    below = [k for k in knots if k < v]
    above = [k for k in knots if k > v]
    start = max(below) if below else v
    end = min(above) if above else v
    if v > 0:
        start = max(start, 0.0)
    else:
        end = min(end, 0.0)
    return (start, v, end)


def _region_for(knots, norm_loc, placed=()):
    """gvar axes dict for a master at norm_loc; axes at default are absent.
    `placed` are the locations of masters already appended: one that
    differs from norm_loc on a single axis is a knot on that axis for this
    master, so the two tents do not overlap."""
    local = {tag: set(ks) for tag, ks in knots.items()}
    for other in placed:
        diff = [t for t in norm_loc if other.get(t, 0.0) != norm_loc[t]]
        if len(diff) == 1:
            local[diff[0]].add(other[diff[0]])
    return {tag: _tent(sorted(local[tag]), v) for tag, v in norm_loc.items() if v != 0}


def _guard_locations(knots, norm_loc, tags):
    """Locations at the neighbouring knots of every axis in `tags` where
    norm_loc sits at the default, so the leak along that axis can be
    cancelled: each such axis moved alone, then every combination.
    Closest first: one axis moved before two, and so on."""
    choices, moved = [], []
    for tag in tags:
        if norm_loc.get(tag, 0.0) != 0:
            continue
        ks = knots[tag]
        neighbours = [
            k
            for k in (
                max([k for k in ks if k < 0], default=None),
                min([k for k in ks if k > 0], default=None),
            )
            if k is not None
        ]
        if neighbours:
            moved.append(tag)
            choices.append([0.0] + neighbours)
    guards = []
    for combo in itertools.product(*choices):
        if not any(combo):
            continue
        loc = dict(norm_loc)
        loc.update(zip(moved, combo))
        guards.append(loc)
    guards.sort(key=lambda loc: sum(1 for t in moved if loc[t] != 0))
    return guards


def _glyph_coords(font):
    """Per-glyph (coordinates incl. phantom points, controls) of a static
    font, or of a variable font's default outlines."""
    glyf, hmtx = font["glyf"], font["hmtx"].metrics
    return {
        name: glyf._getCoordinatesAndControls(name, hmtx)
        for name in font.getGlyphOrder()
    }


def _append_local_master(font, target, current, region, defaults, iup_tolerance=0.5):
    """Append to `font`'s gvar, per glyph, a tuple with support `region`
    whose deltas take `current` to `target` (both from _glyph_coords).
    Returns the number of glyphs given a tuple and the largest residual."""
    gvar = font["gvar"].variations
    added, worst = 0, 0.0
    for name, (c2, controls) in target.items():
        c1 = current[name][0]
        if len(c1) != len(c2):
            log.warning(
                "%s: point count differs (%d vs %d); not refined",
                name,
                len(c1),
                len(c2),
            )
            continue
        residual = c2 - c1
        deltas = [(otRound(x), otRound(y)) for x, y in residual]
        if not any(x or y for x, y in deltas):
            continue
        worst = max(worst, max(max(abs(x), abs(y)) for x, y in residual))
        if controls.numberOfContours > 0 and iup_tolerance > 0:
            # drop deltas IUP can infer from their contour neighbours; the
            # renderer infers them against the default outline
            deltas = iup_delta_optimize(
                deltas, defaults[name][0], controls.endPts, tolerance=iup_tolerance
            )
        gvar.setdefault(name, []).append(TupleVariation(dict(region), deltas))
        added += 1
    return added, worst


def _rebuild_hvar(font):
    """HVAR advance variations recomputed from the gvar phantom points, so
    they agree with the outlines after tuples were appended."""
    axis_tags = [a.axisTag for a in font["fvar"].axes]
    glyf = font["glyf"]
    builder = OnlineVarStoreBuilder(axis_tags)
    mapping = {}
    for name in font.getGlyphOrder():
        glyph = glyf[name]
        if glyph.isComposite():
            n = len(glyph.components)
        else:
            n = len(glyph.coordinates) if hasattr(glyph, "coordinates") else 0
        supports, deltas = [], []
        for tv in font["gvar"].variations.get(name, []):
            left = tv.coordinates[n] if n < len(tv.coordinates) else None
            right = tv.coordinates[n + 1] if n + 1 < len(tv.coordinates) else None
            adv = (right[0] if right else 0) - (left[0] if left else 0)
            if adv:
                supports.append(tv.axes)
                deltas.append(adv)
        builder.setSupports(supports)
        mapping[name] = builder.storeDeltas(deltas)
    store = builder.finish()
    optimized = store.optimize()
    hvar = ot.HVAR()
    hvar.Version = 0x00010000
    hvar.VarStore = store
    hvar.AdvWidthMap = ot.VarIdxMap()
    hvar.AdvWidthMap.mapping = {name: optimized[idx] for name, idx in mapping.items()}
    hvar.LsbMap = hvar.RsbMap = None
    table = newTable("HVAR")
    table.table = hvar
    font["HVAR"] = table


class Avar2Flattener:
    def __init__(self, ttfont, avar_mapping, out, options):
        if "fvar" not in ttfont:
            raise ValueError("Not a variable font")
        if "avar" not in ttfont or getattr(ttfont["avar"], "majorVersion", 1) < 2:
            raise ValueError("Font has no avar2 table; nothing to flatten")
        self.font = ttfont
        self.out = out
        self.options = options
        self.fvar = ttfont["fvar"]
        self.axis_tags = [a.axisTag for a in self.fvar.axes]
        self.fvar_triples = {
            a.axisTag: (a.minValue, a.defaultValue, a.maxValue) for a in self.fvar.axes
        }
        # Inverse of the avar1 segment maps embedded in the avar2 table, so
        # we can turn a post-avar1 normalized knot back into a user coord.
        self.inv_segments = {
            tag: {v: k for k, v in seg.items()}
            for tag, seg in ttfont["avar"].segments.items()
            if seg
        }
        self.maps = self._axis_maps(avar_mapping)
        self.rules = self._extract_feature_variation_rules()

        avar_knots, avar_edges = _avar2_knots_and_edges(ttfont["avar"], self.axis_tags)
        tuple_vars = [v for v in ttfont["gvar"].variations.values()]
        if "cvar" in ttfont:
            tuple_vars.append(ttfont["cvar"].variations)
        gvar_knots, gvar_edges = _tuplevar_knots_and_edges(tuple_vars)

        raw_knots = avar_knots
        for tag, vals in gvar_knots.items():
            raw_knots.setdefault(tag, set()).update(vals)
        self.knots = _clean_knots(raw_knots, self.fvar.axes)
        # Knots of every axis, output (parametric) ones included: where a
        # mapped coordinate crosses one of these, gvar changes master.
        self.all_knots = dict(self.knots)
        # --axes: restrict the output font to a subset of the fvar axes.
        # Masters are cut with the dropped axes pinned at their defaults,
        # and knots (hence sampling, groups, and the output designspace)
        # only cover the kept axes.
        if getattr(options, "axes", None):
            self.keep_tags = [t.strip() for t in options.axes.split(",")]
            unknown = [t for t in self.keep_tags if t not in self.axis_tags]
            if unknown:
                raise ValueError(f"--axes not in fvar: {unknown}")
            self.knots = {t: v for t, v in self.knots.items() if t in self.keep_tags}
            log.info("Restricting output to axes %s", " ".join(self.keep_tags))
        else:
            self.keep_tags = list(self.axis_tags)
        varying = [t for t in self.axis_tags if t in self.knots]
        self.groups = _interaction_groups(varying, avar_edges + gvar_edges)

        for group in self.groups:
            counts = " x ".join(f"{t}:{len(self.knots[t])}" for t in group)
            log.info("Interaction group [%s] knots %s", " ".join(group), counts)

        default = tuple(0.0 for _ in self.axis_tags)
        self.base_locations = {default}
        # Reachable per-axis extremes anchor the variation model so it never
        # extrapolates past the outermost master.
        index = {t: i for i, t in enumerate(self.axis_tags)}
        for tag in varying:
            for extreme in (self.knots[tag][0], self.knots[tag][-1]):
                if extreme != 0:
                    loc = list(default)
                    loc[index[tag]] = extreme
                    self.base_locations.add(tuple(loc))
        for vec in _peak_vectors(ttfont["avar"], self.axis_tags, tuple_vars):
            self.base_locations.add(self.clamp_vector(vec))
        # Locations added by --tolerance refinement rounds.
        self.extra_locations = set()
        log.info(
            "%d sparse master locations from avar2 regions and gvar/cvar tuples",
            len(self.base_locations),
        )
        # --grid: masters at the full tensor product of the given axes' knots
        # (other axes at default), so interpolation between knots of the
        # primary design axes is sampled instead of approximated additively.
        # Each entry is ``tag`` (all of the font's knots on that axis) or
        # ``tag:N`` (exactly N knots, see _grid_knots), so the product size
        # can be traded per axis: --grid opsz:3,wdth:5,wght:9.
        self.grid_tags, self.grid_knots = None, None
        if getattr(options, "grid", None):
            grid_counts = _parse_grid_spec(options.grid)
            grid_tags = list(grid_counts)
            unknown = [t for t in grid_tags if t not in self.knots]
            if unknown:
                raise ValueError(f"--grid axes not varying in font: {unknown}")
            # --grid-cuts: subdivide each knot interval of the axes given
            # without a count, so the grid also samples cell interiors; the
            # composite avar2 mapping is not multilinear within cells, so
            # corner masters alone leave a quadratic cross-axis residual.
            cuts = getattr(options, "grid_cuts", 0) or 0
            grid_knots = {}
            for tag, count in grid_counts.items():
                if isinstance(count, list):
                    grid_knots[tag] = self.position_knots(tag, count)
                else:
                    grid_knots[tag] = _grid_knots(self.knots[tag], count, cuts)
            self.grid_tags, self.grid_knots = grid_tags, grid_knots
            before = len(self.base_locations)
            grid = list(itertools.product(*(grid_knots[t] for t in grid_tags)))
            for combo in grid:
                loc = list(default)
                for tag, value in zip(grid_tags, combo):
                    loc[index[tag]] = value
                self.base_locations.add(tuple(loc))
            log.info(
                "--grid %s = %d grid masters (%d new)",
                " x ".join(f"{t}:{len(grid_knots[t])}" for t in grid_tags),
                len(grid),
                len(self.base_locations) - before,
            )
        # Refinement: local masters appended to the built font (_refine),
        # as sparse post-avar1 normalized locations with a reason each.
        self.refine_locations = []
        for text in getattr(options, "refine_at", None) or []:
            user = _parse_location(text)
            unknown = [t for t in user if t not in self.knots]
            if unknown:
                raise ValueError(
                    f"--refine-at axes not varying in the output font: {unknown}"
                )
            loc = {}
            for tag, value in user.items():
                lo, hi = self.knots[tag][0], self.knots[tag][-1]
                loc[tag] = min(max(self.output_user_to_knot(tag, value), lo), hi)
            self.refine_locations.append((loc, "--refine-at"))
        if getattr(options, "refine_crossings", False):
            if self.grid_tags is None:
                raise ValueError("--refine-crossings needs --grid")
            found = self.crossing_masters(
                self.grid_knots, self.grid_tags, getattr(options, "crossing_min", 0.1)
            )
            for loc, strength, why in found:
                self.refine_locations.append((loc, why))
            if found:
                log.info(
                    "%d crossings to refine; strongest: %s, where %s",
                    len(found),
                    self.describe(found[0][0]),
                    found[0][2],
                )
            else:
                log.info("No crossings to refine")
        limit = getattr(options, "max_refine", 0) or 0
        if limit and len(self.refine_locations) > limit:
            log.info(
                "--max-refine %d: refining at the %d strongest of %d locations",
                limit,
                limit,
                len(self.refine_locations),
            )
            self.refine_locations = self.refine_locations[:limit]

    def clamp_vector(self, vec):
        """Clamp a normalized location to what the fvar ranges can reach."""
        out = []
        for tag, value in zip(self.axis_tags, vec):
            if tag not in self.knots:
                out.append(0.0)
            else:
                out.append(min(max(value, self.knots[tag][0]), self.knots[tag][-1]))
        return tuple(out)

    def _axis_maps(self, avar_mapping):
        """user->design mapping pairs for the output font: the yaml file if
        given, otherwise any non-identity avar1 segment maps of the input."""
        maps = {}
        if avar_mapping:
            for tag, mapping in avar_mapping.items():
                maps[tag] = sorted((float(k), float(v)) for k, v in mapping.items())
        else:
            for tag, seg in self.font["avar"].segments.items():
                if any(a != b for a, b in seg.items()):
                    triple = self.fvar_triples[tag]
                    maps[tag] = [
                        (_denormalize(a, triple), _denormalize(b, triple))
                        for a, b in sorted(seg.items())
                    ]
        return maps

    def _extract_feature_variation_rules(self):
        """Substitution rules recovered from the GSUB FeatureVariations, which
        is then stripped from the input so every cut master gets an identical
        feature list (varLib refuses to merge masters where a rule left an
        extra rvrn feature behind). The rules are re-added to the designspace
        so varLib rebuilds an equivalent rvrn feature with valid lookup
        indices. Returns [(condition_sets, {from_glyph: to_glyph})] with
        conditions as (tag, min, max) in normalized coordinates."""
        rules = []
        if "GSUB" not in self.font:
            return rules
        gsub = self.font["GSUB"].table
        if not hasattr(gsub, "FeatureVariations") or gsub.FeatureVariations is None:
            return rules
        for record in gsub.FeatureVariations.FeatureVariationRecord:
            conditions = [
                (
                    self.axis_tags[cond.AxisIndex],
                    cond.FilterRangeMinValue,
                    cond.FilterRangeMaxValue,
                )
                for cond in record.ConditionSet.ConditionTable
            ]
            subs = {}
            for sub_record in record.FeatureTableSubstitution.SubstitutionRecord:
                for index in sub_record.Feature.LookupListIndex:
                    for subtable in gsub.LookupList.Lookup[index].SubTable:
                        if hasattr(subtable, "mapping"):
                            subs.update(subtable.mapping)
                        else:
                            log.warning(
                                "Dropping non-single-substitution FeatureVariations "
                                "lookup %d (%s)",
                                index,
                                type(subtable).__name__,
                            )
            if subs:
                rules.append((conditions, subs))
        gsub.FeatureVariations = None
        log.info("Recovered %d substitution rules from FeatureVariations", len(rules))
        return rules

    def user_to_knot(self, tag, value):
        """Post-avar1 normalized coordinate of a user value on an axis."""
        n = normalizeValue(value, self.fvar_triples[tag])
        segments = self.font["avar"].segments.get(tag)
        if segments:
            n = piecewiseLinearMap(n, segments)
        return n

    def output_user_to_knot(self, tag, value):
        """Post-avar1 normalized coordinate of a user value on an axis of
        the *output* font, i.e. through its avar1 mapping if it has one."""
        if tag in self.maps:
            mapping = dict(self.maps[tag])
            design = piecewiseLinearMap(value, mapping)
            triple = tuple(
                piecewiseLinearMap(v, mapping) for v in self.fvar_triples[tag]
            )
            return normalizeValue(design, triple)
        return normalizeValue(value, self.fvar_triples[tag])

    def position_knots(self, tag, positions):
        """Knots for ``tag:a/b/c``: masters at exactly those user positions.
        The default and the reachable extremes are always included, since
        the variation model needs them; anything out of range is clamped."""
        knots = self.knots[tag]
        lo, hi = knots[0], knots[-1]
        wanted = {min(max(self.user_to_knot(tag, v), lo), hi) for v in positions}
        required = {lo, 0.0, hi}
        missing = required - wanted
        if missing:
            log.info(
                "--grid %s: adding %s (default and extremes are always masters)",
                tag,
                ", ".join(
                    f"{self.source_user_location({tag: k})[tag]:g}"
                    for k in sorted(missing)
                ),
            )
        return sorted(wanted | required)

    def mapped_location(self, norm_loc):
        """Post-avar2 normalized coordinates of every axis for a post-avar1
        normalized input location (sparse: missing axes are at default)."""
        pre = {}
        for tag in self.axis_tags:
            n = norm_loc.get(tag, 0.0)
            if tag in self.inv_segments:
                n = piecewiseLinearMap(n, self.inv_segments[tag])
            pre[tag] = n
        out = self.font["avar"].renormalizeLocation(pre, self.font, dropZeroes=False)
        return {t: out.get(t, 0.0) for t in self.axis_tags}

    def crossing_masters(self, axis_knots, grid_tags, min_excursion=0.1, merge=0.02):
        """Locations on grid edges where an output axis crosses one of
        its own knots (its default or an intermediate master) part-way
        between two input knots. gvar changes master there, so the outline
        has a kink that the edge's end masters cannot express; these are
        the places --refine-crossings refines at.

        The mapping is linear along an edge, so each crossing is found
        exactly from the two endpoints. A crossing counts only if the
        output axis travels at least ``min_excursion`` (normalized) on both
        sides of it; tiny wobbles across a default are not worth a master.
        Crossings within ``merge`` of each other on the same edge are
        merged. Returns [(sparse location, strength, description), ...]
        strongest first."""
        found = []
        for tag in grid_tags:
            knots = axis_knots[tag]
            others = [t for t in grid_tags if t != tag]
            for ctx in itertools.product(*(axis_knots[t] for t in others)):
                base = dict(zip(others, ctx))
                for k0, k1 in zip(knots[:-1], knots[1:]):
                    m0 = self.mapped_location({**base, tag: k0})
                    m1 = self.mapped_location({**base, tag: k1})
                    edge = []
                    for out_tag in self.axis_tags:
                        if out_tag == tag:
                            continue
                        for bp in self.all_knots.get(out_tag, [0.0]):
                            for t in _crossings(m0[out_tag], m1[out_tag], [bp]):
                                strength = min(
                                    abs(m0[out_tag] - bp), abs(m1[out_tag] - bp)
                                )
                                if strength < min_excursion:
                                    continue
                                v = k0 + t * (k1 - k0)
                                if any(abs(v - k) <= merge for k in knots):
                                    continue
                                edge.append((strength, v, out_tag, bp))
                    edge.sort(reverse=True)
                    kept = []
                    for strength, v, out_tag, bp in edge:
                        if any(abs(v - w) <= merge for _, w, _, _ in kept):
                            continue
                        kept.append((strength, v, out_tag, bp))
                        loc = {**base, tag: v}
                        why = f"{out_tag} crosses {bp:g} moving {tag} between {self.describe({tag: k0})} and {self.describe({tag: k1})}"
                        found.append((loc, strength, why))
        found.sort(key=lambda x: -x[1])
        return found

    def source_user_location(self, norm_loc):
        """User coords in the *input* font whose post-avar1 normalized
        position equals norm_loc. instancer applies avar2 on top for us."""
        coords = {}
        for tag, n in norm_loc.items():
            if tag in self.inv_segments:
                n = piecewiseLinearMap(n, self.inv_segments[tag])
            minimum, _, maximum = self.fvar_triples[tag]
            u = _denormalize(n, self.fvar_triples[tag])
            coords[tag] = min(max(u, minimum), maximum)
        return coords

    def full_norm_location(self, sparse):
        loc = {tag: 0.0 for tag in self.axis_tags}
        loc.update(sparse)
        return loc

    def build_designspace(self, locations, tmpdir, master_files):
        ds = DesignSpaceDocument()
        name_table = self.font["name"]
        axis_names, design_triples, ds_axes = {}, {}, {}
        for fvar_axis in self.fvar.axes:
            tag = fvar_axis.axisTag
            if tag not in self.keep_tags:
                continue
            ax = AxisDescriptor()
            human = name_table.getDebugName(fvar_axis.axisNameID) or tag
            if human in axis_names.values():
                human = f"{human} ({tag})"
            ax.name = human
            ax.tag = tag
            ax.minimum, ax.default, ax.maximum = self.fvar_triples[tag]
            ax.hidden = bool(fvar_axis.flags & 0x1)
            if tag in self.maps:
                ax.map = self.maps[tag]
            ds.addAxis(ax)
            axis_names[tag] = human
            design_triples[tag] = (
                ax.map_forward(ax.minimum),
                ax.map_forward(ax.default),
                ax.map_forward(ax.maximum),
            )
            ds_axes[tag] = ax
        self.axis_names, self.design_triples, self.ds_axes = (
            axis_names,
            design_triples,
            ds_axes,
        )

        # varLib normalizes rule conditions against the mapped (design) axis
        # triples, so denormalizing with design_triples round-trips the
        # original normalized condition values exactly.
        for i, (conditions, subs) in enumerate(self.rules):
            # A condition on a dropped axis is evaluated at that axis's
            # default: always true (omit it) or never true (skip the rule).
            condition_set, always_false = [], False
            for tag, minimum, maximum in conditions:
                if tag not in axis_names:
                    if not minimum <= 0 <= maximum:
                        always_false = True
                    continue
                condition_set.append(
                    {
                        "name": axis_names[tag],
                        "minimum": _denormalize(minimum, design_triples[tag]),
                        "maximum": _denormalize(maximum, design_triples[tag]),
                    }
                )
            if always_false or not condition_set:
                if always_false:
                    log.warning("Dropping rule %d: condition on dropped axis", i)
                continue
            rule = RuleDescriptor()
            rule.name = f"rule_{i}"
            rule.conditionSets.append(condition_set)
            rule.subs = sorted(subs.items())
            ds.rules.append(rule)

        for loc in locations:
            if loc not in master_files:
                coords = self.source_user_location(dict(zip(self.axis_tags, loc)))
                log.debug("Cutting master at %s", coords)
                master = instancer.instantiateVariableFont(self.font, coords)
                path = os.path.join(tmpdir, f"master_{len(master_files):04d}.ttf")
                master.save(path)
                master_files[loc] = path
            source = SourceDescriptor()
            source.path = master_files[loc]
            source.filename = os.path.basename(master_files[loc])
            source.familyName = self.font["name"].getBestFamilyName()
            source.name = "_".join(
                f"{tag}-{v:g}"
                for tag, v in zip(self.axis_tags, loc)
                if tag in axis_names
            )
            source.location = {
                axis_names[tag]: _denormalize(n, design_triples[tag])
                for tag, n in zip(self.axis_tags, loc)
                if tag in axis_names
            }
            ds.sources.append(source)

        for fvar_inst in self.fvar.instances:
            new_inst = InstanceDescriptor()
            new_inst.name = (
                name_table.getDebugName(fvar_inst.subfamilyNameID) or "Instance"
            )
            new_inst.familyName = self.font["name"].getBestFamilyName()
            new_inst.styleName = new_inst.name
            new_inst.location = {
                axis_names[tag]: ds_axes[tag].map_forward(fvar_inst.coordinates[tag])
                for tag in self.keep_tags
            }
            ds.instances.append(new_inst)
        return ds

    def verification_samples(self, rng):
        """Cell midpoints per group (worst spots for interpolation error)
        plus random cross-group locations."""
        per_group = []
        for gi, group in enumerate(self.groups):
            per_axis = [list(zip(self.knots[t][:-1], self.knots[t][1:])) for t in group]
            group_cells = [
                (gi, dict(zip(group, combo))) for combo in itertools.product(*per_axis)
            ]
            rng.shuffle(group_cells)
            per_group.append(group_cells)
        # Draw round-robin across groups so a group with few cells (e.g. the
        # avar2 input axes) isn't drowned out by one with thousands.
        cells = []
        while len(cells) < self.options.samples and any(per_group):
            for group_cells in per_group:
                if group_cells and len(cells) < self.options.samples:
                    cells.append(group_cells.pop())

        cross = []
        if len(self.groups) > 1:
            varying = [t for g in self.groups for t in g]
            for _ in range(self.options.cross_samples):
                cross.append(
                    {
                        t: rng.uniform(self.knots[t][0], self.knots[t][-1])
                        for t in varying
                    }
                )
        return cells, cross

    def output_user_location(self, norm_loc):
        """User coords in the *output* font of a normalized (post-avar1)
        location: every kept axis, through the output avar1 mapping."""
        full = self.full_norm_location(norm_loc)
        coords = {}
        for tag, n in full.items():
            if tag not in self.ds_axes:  # dropped by --axes
                continue
            design = _denormalize(n, self.design_triples[tag])
            u = self.ds_axes[tag].map_backward(design)
            minimum, _, maximum = self.fvar_triples[tag]
            coords[tag] = min(max(u, minimum), maximum)
        return coords

    def compare_at(self, new_font, norm_loc):
        """Worst outline diff between input and output font at a normalized
        (post-avar1) location."""
        orig_coords = self.source_user_location(self.full_norm_location(norm_loc))
        orig = instancer.instantiateVariableFont(self.font, orig_coords)
        new = instancer.instantiateVariableFont(
            new_font, self.output_user_location(norm_loc)
        )
        return _outline_diff(orig, new)

    def _refine(self, font):
        """Append a local master at every refinement location: the residual
        between the original and `font` there, as gvar tuples whose tents
        span only the neighbouring knots. Guards (see module docstring)
        follow each location. Returns [(norm loc, kind, residual)]."""
        out_tags = [a.axisTag for a in font["fvar"].axes]
        knots = _axis_knots(font)
        guards = getattr(self.options, "refine_guards", True)
        guard_tags = self.grid_tags or [t for t in out_tags if t in self.knots]
        plan = []
        for sparse, why in self.refine_locations:
            full = {t: sparse.get(t, 0.0) for t in out_tags}
            plan.append((full, "master"))
            if not guards:
                continue
            found = _guard_locations(knots, full, guard_tags)
            if len(found) > 64:
                log.warning(
                    "%s: %d guard masters would be needed; skipping guards "
                    "there (the correction leaks along %s)",
                    self.describe(sparse),
                    len(found),
                    " ".join(t for t in guard_tags if full[t] == 0),
                )
                continue
            plan.extend((g, "guard") for g in found)
        log.info(
            "Refining at %d locations (%d guards)",
            len(self.refine_locations),
            sum(1 for _, kind in plan if kind == "guard"),
        )
        defaults = _glyph_coords(font)
        placed, report = [], []
        for full, kind in plan:
            region = _region_for(knots, full, placed)
            placed.append(full)
            if not region:
                log.warning("%s is the default location; nothing to refine", kind)
                continue
            # every input axis pinned, or instancer keeps the avar2 mapping
            # and leaves the parametric axes at their raw defaults
            target = _glyph_coords(
                instancer.instantiateVariableFont(
                    self.font,
                    self.source_user_location(self.full_norm_location(full)),
                    inplace=False,
                )
            )
            current = _glyph_coords(
                instancer.instantiateVariableFont(
                    font, self.output_user_location(full), inplace=False
                )
            )
            added, worst = _append_local_master(font, target, current, region, defaults)
            log.info(
                "  %s at %s: residual %.1f units, %d glyphs given a tuple; tent %s",
                kind,
                self.describe({t: v for t, v in full.items() if v != 0}),
                worst,
                added,
                " ".join(
                    f"{t}:{s:.2f}/{p:.2f}/{e:.2f}" for t, (s, p, e) in region.items()
                ),
            )
            report.append((full, kind, worst))
        if "HVAR" in font:
            _rebuild_hvar(font)
        return report

    def describe(self, norm_loc):
        coords = self.source_user_location(self.full_norm_location(norm_loc))
        return ", ".join(f"{tag}={coords[tag]:g}" for tag in norm_loc)

    def _build_stat(self, vf):
        """Rebuild STAT for the kept axes, carrying over the original
        table's AxisValues (names resolved to strings, axis indices
        remapped). AxisValues that reference a dropped axis are dropped.

        This is done even when every axis is kept: instancer prunes the
        masters' name tables, so the varLib-built font is missing most of
        the name records the original STAT points at. Rebuilding with
        buildStatTable re-adds the records from the resolved strings."""
        orig = self.font["STAT"].table if "STAT" in self.font else None
        names = self.font["name"]
        kept = [a for a in self.fvar.axes if a.axisTag in self.keep_tags]
        elided_fallback = "Regular"
        values_by_tag, locations, stat_axis_names = {}, [], {}
        stat_only_tags, value_tags = [], set(self.keep_tags)
        if orig:
            orig_axes = orig.DesignAxisRecord.Axis
            ordering = {a.AxisTag: a.AxisOrdering for a in orig_axes}
            kept.sort(key=lambda a: ordering.get(a.axisTag, 0))
            # STAT-only axes (e.g. ital on a roman font) have no fvar axis
            # to be dropped with, so they and their AxisValues are always
            # carried over.
            fvar_tags = set(self.axis_tags)
            stat_only_tags = [
                a.AxisTag
                for a in sorted(orig_axes, key=lambda a: a.AxisOrdering)
                if a.AxisTag not in fvar_tags
            ]
            value_tags.update(stat_only_tags)
            # The STAT DesignAxisRecord often carries better display names
            # than the fvar axis records (e.g. Crispy: 'Counter Width' vs
            # 'X-Transparency'), so prefer them.
            stat_axis_names = {
                a.AxisTag: names.getDebugName(a.AxisNameID) for a in orig_axes
            }
            elided_fallback = names.getDebugName(orig.ElidedFallbackNameID) or "Regular"
            for av in orig.AxisValueArray.AxisValue if orig.AxisValueArray else []:
                name = names.getDebugName(av.ValueNameID)
                if name is None:
                    log.warning(
                        "Dropping STAT AxisValue with unresolvable nameID %d",
                        av.ValueNameID,
                    )
                    continue
                if av.Format == 4:
                    refs = [
                        (orig_axes[r.AxisIndex].AxisTag, r.Value)
                        for r in av.AxisValueRecord
                    ]
                    if all(tag in value_tags for tag, _ in refs):
                        locations.append(
                            {
                                "name": name,
                                "flags": av.Flags,
                                "location": dict(refs),
                            }
                        )
                    continue
                tag = orig_axes[av.AxisIndex].AxisTag
                if tag not in value_tags:
                    continue
                value = {
                    "name": name,
                    "flags": av.Flags,
                }
                if av.Format == 1:
                    value["value"] = av.Value
                elif av.Format == 2:
                    value["nominalValue"] = av.NominalValue
                    value["rangeMinValue"] = av.RangeMinValue
                    value["rangeMaxValue"] = av.RangeMaxValue
                elif av.Format == 3:
                    value["value"] = av.Value
                    value["linkedValue"] = av.LinkedValue
                values_by_tag.setdefault(tag, []).append(value)
        stat_axes = []
        for i, axis in enumerate(kept):
            entry = {
                "tag": axis.axisTag,
                "name": stat_axis_names.get(axis.axisTag)
                or self.axis_names[axis.axisTag],
                "ordering": i,
            }
            if axis.axisTag in values_by_tag:
                entry["values"] = values_by_tag[axis.axisTag]
            stat_axes.append(entry)
        for tag in stat_only_tags:
            entry = {
                "tag": tag,
                "name": stat_axis_names.get(tag) or tag,
                "ordering": len(stat_axes),
            }
            if tag in values_by_tag:
                entry["values"] = values_by_tag[tag]
            stat_axes.append(entry)
        buildStatTable(
            vf,
            stat_axes,
            locations=locations or None,
            elidedFallbackName=elided_fallback,
        )

    def run(self):
        rng = random.Random(0)
        with tempfile.TemporaryDirectory() as tmpdir:
            master_files = {}
            rounds = 0
            while True:
                locations = sorted(self.base_locations | self.extra_locations)
                if len(locations) > self.options.max_masters:
                    raise ValueError(
                        f"Would need {len(locations)} masters "
                        f"(max {self.options.max_masters}); pass --max-masters "
                        f"to raise the limit"
                    )
                log.info("Building variable font from %d masters", len(locations))
                ds = self.build_designspace(locations, tmpdir, master_files)
                ds_path = os.path.join(tmpdir, "avar1.designspace")
                ds.write(ds_path)
                vf, _, _ = varlib_build(ds_path)
                # Always rebuild STAT, even when no axes were dropped:
                # copying the original table verbatim leaves its AxisValues
                # pointing at name records that instancer pruned from the
                # masters, so they would resolve to nothing.
                self._build_stat(vf)
                vf.save(self.out)
                new_font = TTFont(self.out)

                worst_cell, worst_err = None, 0.0
                if self.options.verify:
                    worst_cell, worst_err = self._verify(new_font, rng)
                done = (
                    not self.options.verify
                    or self.options.tolerance is None
                    or worst_cell is None
                    or worst_err <= self.options.tolerance
                    or rounds >= self.options.max_rounds
                )
                if done:
                    if self.options.tolerance is not None and worst_err > (
                        self.options.tolerance or 0
                    ):
                        log.warning(
                            "Stopped refining after %d rounds with %.1f units error",
                            rounds,
                            worst_err,
                        )
                    if self.refine_locations:
                        report = self._refine(new_font)
                        new_font.save(self.out)
                        if self.options.verify:
                            final = TTFont(self.out)
                            for full, kind, before in report:
                                after, glyph = self.compare_at(final, full)
                                log.info(
                                    "  %s at %s: worst error %.1f -> %.1f units (%s)",
                                    kind,
                                    self.describe(
                                        {t: v for t, v in full.items() if v != 0}
                                    ),
                                    before,
                                    after,
                                    glyph,
                                )
                    log.info("Saved %s", self.out)
                    return
                # Add a master at the worst midpoint and split the cell so the
                # next verification round samples either side of it.
                _, intervals = worst_cell
                midpoint = {t: (lo + hi) / 2 for t, (lo, hi) in intervals.items()}
                loc = self.clamp_vector(
                    tuple(midpoint.get(tag, 0.0) for tag in self.axis_tags)
                )
                self.extra_locations.add(loc)
                for tag, value in midpoint.items():
                    self.knots[tag] = sorted(set(self.knots[tag]) | {value})
                rounds += 1
                log.info(
                    "Refinement round %d: adding master at %s",
                    rounds,
                    self.describe(midpoint),
                )

    def _verify(self, new_font, rng):
        """Compare the built font against the original at cell midpoints and
        random cross-group locations. Returns the worst cell and its error."""
        cells, cross = self.verification_samples(rng)
        log.info(
            "Verifying against original: %d cell midpoints, %d cross-group samples",
            len(cells),
            len(cross),
        )
        worst_cell, worst_err = None, 0.0
        worst_per_group = {}
        for gi, intervals in cells:
            midpoint = {t: (lo + hi) / 2 for t, (lo, hi) in intervals.items()}
            err, glyph = self.compare_at(new_font, midpoint)
            log.debug("  %s: %.1f (%s)", self.describe(midpoint), err, glyph)
            if gi not in worst_per_group or err > worst_per_group[gi][0]:
                worst_per_group[gi] = (err, glyph, midpoint)
            if err > worst_err:
                worst_cell, worst_err = (gi, intervals), err
        for gi, (err, glyph, midpoint) in sorted(worst_per_group.items()):
            log.info(
                "Worst error in group [%s]: %.1f font units " "(glyph '%s' at %s)",
                " ".join(self.groups[gi]),
                err,
                glyph,
                self.describe(midpoint),
            )
        cross_errs = []
        for norm_loc in cross:
            err, glyph = self.compare_at(new_font, norm_loc)
            cross_errs.append((err, glyph, norm_loc))
            log.debug("  cross %s: %.1f (%s)", self.describe(norm_loc), err, glyph)
        if cross_errs:
            cross_errs.sort(reverse=True, key=lambda rec: rec[0])
            err, glyph, norm_loc = cross_errs[0]
            median = cross_errs[len(cross_errs) // 2][0]
            log.info(
                "Cross-group residual over %d random locations: "
                "median %.1f, worst %.1f font units (glyph '%s' at %s) "
                "-- additive approximation, not reduced by --tolerance",
                len(cross_errs),
                median,
                err,
                glyph,
                self.describe(norm_loc),
            )
        return worst_cell, worst_err


def avar2_to_avar1(ttfont, avar_mapping, out, options):
    Avar2Flattener(ttfont, avar_mapping, out, options).run()


def main(args=None):
    parser = argparse.ArgumentParser(
        description="Flatten an avar2 variable font into an avar1 variable font."
    )
    parser.add_argument("font_path", help="Path to the variable font file")
    parser.add_argument("-m", "--mapping", help="Path to avar1 yaml mapping")
    parser.add_argument("-o", "--out")
    parser.add_argument(
        "--tolerance",
        type=float,
        default=None,
        help="Max acceptable outline error in font units; refine by inserting "
        "knots and rebuilding until met (default: report only, no refinement)",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=5,
        help="Max refinement rounds when --tolerance is given (default: 5)",
    )
    parser.add_argument(
        "--max-masters",
        type=int,
        default=300,
        help="Abort if more than this many masters would be needed (default: 300)",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=64,
        help="Max cell midpoints to verify per round (default: 64)",
    )
    parser.add_argument(
        "--cross-samples",
        type=int,
        default=8,
        help="Random cross-group locations to verify (default: 8)",
    )
    parser.add_argument(
        "--axes",
        help="Comma-separated axis tags to keep in the output font; the "
        "rest are pinned at their defaults (default: keep all axes)",
    )
    parser.add_argument(
        "--grid",
        help="Comma-separated axis tags; add masters at the full tensor "
        "product of these axes' knots for better accuracy between them. "
        "A tag may carry a master count, tag:N, to use exactly N knots on "
        "that axis (always the default and extremes; fewer than the font "
        "has picks evenly from its knots, more bisects the largest gaps), "
        "or a slash list of user positions, tag:300/400/700, to put masters "
        "exactly there (default and extremes are added if missing). "
        "E.g. --grid opsz:3,wdth:5,wght:9 gives 135 grid masters",
    )
    parser.add_argument(
        "--grid-cuts",
        type=int,
        default=0,
        help="With --grid: also insert this many evenly spaced masters "
        "between adjacent knots on each grid axis given without a count "
        "(default: 0)",
    )
    parser.add_argument(
        "--refine-at",
        action="append",
        default=[],
        metavar="LOC",
        help="Refine the built font at this location, given in user "
        "coordinates of the output font, e.g. wght=352,wdth=25,opsz=9 "
        "(repeatable). A local master with an explicit tent is appended, "
        "exact there and unchanged outside the surrounding cells",
    )
    parser.add_argument(
        "--refine-crossings",
        action="store_true",
        help="With --grid: refine wherever an output axis crosses its "
        "default or an intermediate master between two grid knots, since "
        "gvar changes slope there. A parametric font can have hundreds; "
        "see --max-refine",
    )
    parser.add_argument(
        "--crossing-min",
        type=float,
        default=0.1,
        help="Minimum normalized travel of the output axis on both sides of "
        "a crossing for it to be refined (default: 0.1)",
    )
    parser.add_argument(
        "--max-refine",
        type=int,
        default=0,
        help="Refine at most this many locations, strongest crossings first "
        "(default: no limit)",
    )
    parser.add_argument(
        "--no-refine-guards",
        dest="refine_guards",
        action="store_false",
        help="Do not add guard masters at the neighbouring knots of axes a "
        "refinement location sits at the default of; the correction then "
        "applies along the whole of those axes",
    )
    parser.add_argument(
        "--no-verify",
        dest="verify",
        action="store_false",
        help="Skip comparing the output against the original",
    )
    options = parser.parse_args(args)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("fontTools").setLevel(logging.WARNING)

    ttfont = TTFont(options.font_path)

    if options.mapping:
        with open(options.mapping, "r", encoding="utf-8") as f:
            avar_mapping = yaml.safe_load(f)
    else:
        avar_mapping = None

    if options.out:
        out = options.out
    else:
        fp = makeOutputFileName(
            options.font_path, outputDir=None, extension=None, overWrite=False
        )
        out = fp.replace(".ttf", "_avar1.ttf")
    avar2_to_avar1(ttfont, avar_mapping, out, options)


if __name__ == "__main__":
    main()
