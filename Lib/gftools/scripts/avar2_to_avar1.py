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

Usage:
# default
gftools avar2-to-avar1 path/to/variable-font.ttf

# refine until the worst in-group error is below 2 font units
gftools avar2-to-avar1 path/to/variable-font.ttf --tolerance 2

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
from fontTools.varLib.models import piecewiseLinearMap

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
        if getattr(options, "grid", None):
            grid_tags = [t.strip() for t in options.grid.split(",")]
            unknown = [t for t in grid_tags if t not in self.knots]
            if unknown:
                raise ValueError(f"--grid axes not varying in font: {unknown}")
            # --grid-cuts: subdivide each knot interval so the grid also
            # samples cell interiors; the composite avar2 mapping is not
            # multilinear within cells, so corner masters alone leave a
            # quadratic cross-axis residual.
            cuts = getattr(options, "grid_cuts", 0) or 0
            grid_knots = {}
            for tag in grid_tags:
                knots = self.knots[tag]
                values = set(knots)
                for lo, hi in zip(knots[:-1], knots[1:]):
                    for i in range(1, cuts + 1):
                        values.add(lo + (hi - lo) * i / (cuts + 1))
                grid_knots[tag] = sorted(values)
            before = len(self.base_locations)
            for combo in itertools.product(*(grid_knots[t] for t in grid_tags)):
                loc = list(default)
                for tag, value in zip(grid_tags, combo):
                    loc[index[tag]] = value
                self.base_locations.add(tuple(loc))
            log.info(
                "--grid %s (cuts %d): %d extra grid masters",
                options.grid,
                cuts,
                len(self.base_locations) - before,
            )

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
        if gsub.FeatureVariations is None:
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

    def compare_at(self, new_font, norm_loc):
        """Worst outline diff between input and output font at a normalized
        (post-avar1) location."""
        full = self.full_norm_location(norm_loc)
        orig_coords = self.source_user_location(full)
        new_coords = {}
        for tag, n in full.items():
            if tag not in self.ds_axes:  # dropped by --axes
                continue
            design = _denormalize(n, self.design_triples[tag])
            u = self.ds_axes[tag].map_backward(design)
            minimum, _, maximum = self.fvar_triples[tag]
            new_coords[tag] = min(max(u, minimum), maximum)
        orig = instancer.instantiateVariableFont(self.font, orig_coords)
        new = instancer.instantiateVariableFont(new_font, new_coords)
        return _outline_diff(orig, new)

    def describe(self, norm_loc):
        coords = self.source_user_location(self.full_norm_location(norm_loc))
        return ", ".join(f"{tag}={coords[tag]:g}" for tag in norm_loc)

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
                # The original STAT covers every fvar axis, so it is only
                # valid when no axes were dropped; otherwise replace the
                # (equally invalid) copy inherited from the default master
                # with a minimal axis-records-only STAT for the kept axes.
                if len(self.keep_tags) == len(self.axis_tags):
                    if "STAT" in self.font:
                        vf["STAT"] = self.font["STAT"]
                else:
                    stat_axes = [
                        {
                            "tag": axis.axisTag,
                            "name": self.axis_names[axis.axisTag],
                            "ordering": ordering,
                        }
                        for ordering, axis in enumerate(
                            a for a in self.fvar.axes if a.axisTag in self.keep_tags
                        )
                    ]
                    buildStatTable(vf, stat_axes, elidedFallbackName="Regular")
                vf.save(self.out)
                log.info("Saved %s", self.out)

                if not self.options.verify:
                    return

                new_font = TTFont(self.out)
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
                        "Worst error in group [%s]: %.1f font units "
                        "(glyph '%s' at %s)",
                        " ".join(self.groups[gi]),
                        err,
                        glyph,
                        self.describe(midpoint),
                    )
                cross_errs = []
                for norm_loc in cross:
                    err, glyph = self.compare_at(new_font, norm_loc)
                    cross_errs.append((err, glyph, norm_loc))
                    log.debug(
                        "  cross %s: %.1f (%s)", self.describe(norm_loc), err, glyph
                    )
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

                if (
                    self.options.tolerance is None
                    or worst_cell is None
                    or worst_err <= self.options.tolerance
                    or rounds >= self.options.max_rounds
                ):
                    if self.options.tolerance is not None and worst_err > (
                        self.options.tolerance or 0
                    ):
                        log.warning(
                            "Stopped refining after %d rounds with %.1f units error",
                            rounds,
                            worst_err,
                        )
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
        "product of these axes' knots for better accuracy between them "
        "(e.g. --grid opsz,wdth,wght)",
    )
    parser.add_argument(
        "--grid-cuts",
        type=int,
        default=0,
        help="With --grid: also insert this many evenly spaced masters "
        "between adjacent knots on each grid axis (default: 0)",
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
