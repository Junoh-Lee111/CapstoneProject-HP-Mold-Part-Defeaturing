"""Reference rules: holes / fillets / repeated protrusions, registered in the CleanCAD pipeline.

Port of the HP mentor's example (occt_remove_holes_fillets_and_protrusions.py, OCCT/OCP) to
FreeCAD. Registers three SET rules in cleancad_core (ref_holes, ref_fillets, ref_protrusions);
they plug into select()/groups()/process() like any other rule. The thresholds come from the
active profile (cleancad_core.PROFILES) - they are configuration, not fixed criteria.
"""
import math
import os
import sys
from collections import Counter

import Part

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cleancad_core as core  # noqa: E402

GEOM_TOL = 1e-6
SIZE_TOL = 1e-7
MIN_SUPPORT_AREA = 500.0
MAX_WALL = 5.0
MAX_PATCH_FACES = 60
MIN_ELONG = 1.5
MATCH_REL, MATCH_ABS = 0.02, 0.05
TWO_PI = 2 * math.pi


def stype(f):
    return type(f.Surface).__name__


class Topo:
    """Face list + adjacency (shared edges) with identity-based indices."""

    def __init__(self, shape):
        self.shape = shape
        self.faces = list(shape.Faces)
        buckets = {}
        for i, f in enumerate(self.faces):
            buckets.setdefault(f.hashCode(), []).append(i)
        self.edges = []  # (edge, set(face idx))
        seen = []
        for e in shape.Edges:
            owners = set()
            for f in shape.ancestorsOfType(e, Part.Face):
                for i in buckets.get(f.hashCode(), []):
                    if self.faces[i].isSame(f):
                        owners.add(i)
            self.edges.append((e, owners))
        self.nb = {i: set() for i in range(len(self.faces))}
        for _, owners in self.edges:
            for i in owners:
                self.nb[i].update(owners - {i})
        self.area = [f.Area for f in self.faces]


def urange(f):
    return f.ParameterRange  # (u0, u1, v0, v1)


def sweep(f):
    u0, u1, _, _ = urange(f)
    return u1 - u0


def outward_normal(f, p):
    u, v = f.Surface.parameter(p)
    return f.normalAt(u, v)


def inward_cylinder(f):
    """True for a hole wall (material outside the bore): normal points to the axis."""
    s = f.Surface
    u0, u1, v0, v1 = urange(f)
    p = f.valueAt((u0 + u1) / 2, (v0 + v1) / 2)
    n = f.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
    axis = s.Axis
    d = p - s.Center
    radial = d - axis * d.dot(axis)
    return n.dot(radial) < 0


def same_cyl(a, b):
    sa, sb = a.Surface, b.Surface
    if abs(sa.Radius - sb.Radius) > GEOM_TOL:
        return False
    if sa.Axis.cross(sb.Axis).Length > 1e-7:
        return False
    return (sb.Center - sa.Center).cross(sa.Axis).Length <= GEOM_TOL


def connected(indices, nb):
    rem = set(indices)
    while rem:
        seed = rem.pop()
        grp, stack = {seed}, [seed]
        while stack:
            for o in nb[stack.pop()] & rem:
                rem.remove(o)
                grp.add(o)
                stack.append(o)
        yield grp


# ----------------------------------------------------------------------------- holes
def hole_groups(shape, diameter):
    t = Topo(shape)
    cand = {i for i, f in enumerate(t.faces)
            if stype(f) == "Cylinder" and 2 * f.Surface.Radius < diameter - SIZE_TOL and inward_cylinder(f)}
    groups = []
    while cand:
        seed = cand.pop()
        walls, stack = {seed}, [seed]
        while stack:
            for o in t.nb[stack.pop()] & cand:
                if same_cyl(t.faces[seed], t.faces[o]):
                    cand.remove(o)
                    walls.add(o)
                    stack.append(o)
        if abs(sum(sweep(t.faces[i]) for i in walls) - TWO_PI) > 1e-5:
            continue  # partial groove / stacked segment
        sel = set(walls)
        axis = t.faces[seed].Surface.Axis
        adjacent = set().union(*(t.nb[i] for i in walls)) - walls
        for o in adjacent:
            f = t.faces[o]
            if (stype(f) == "Plane" and t.nb[o] and t.nb[o] <= walls
                    and abs(f.Surface.Axis.dot(axis)) > 1 - 1e-7):
                sel.add(o)  # blind-hole floor
        groups.append([t.faces[i] for i in sorted(sel)])
    return groups


# --------------------------------------------------------------------------- fillets
def blend_radius(f):
    k = stype(f)
    if k == "Cylinder":
        return None if sweep(f) >= TWO_PI - 1e-5 else f.Surface.Radius
    if k == "Toroid":
        return f.Surface.MinorRadius
    if k == "Sphere":
        return f.Surface.Radius
    return None


def tangent_at_edge(fa, fb, edge):
    try:
        for frac in (0.2, 0.5, 0.8):
            p = edge.valueAt(edge.FirstParameter + frac * (edge.LastParameter - edge.FirstParameter))
            na, nb = outward_normal(fa, p), outward_normal(fb, p)
            if na.dot(nb) < math.cos(math.radians(0.5)):
                return False
        return True
    except Exception:
        return False


def fillet_groups(shape, radius_limit):
    t = Topo(shape)
    radii = [blend_radius(f) for f in t.faces]
    cand = {i for i, r in enumerate(radii) if r is not None and r < radius_limit - SIZE_TOL}
    tang = {i: set() for i in range(len(t.faces))}
    for e, owners in t.edges:
        if len(owners) != 2:
            continue
        i, j = sorted(owners)
        if (i in cand or j in cand) and tangent_at_edge(t.faces[i], t.faces[j], e):
            tang[i].add(j)
            tang[j].add(i)
    accepted = set()
    for i in cand:
        if stype(t.faces[i]) == "Sphere":
            continue  # corner patches join only through a neighbour
        supports = [j for j in tang[i] - cand
                    if not (stype(t.faces[i]) == "Cylinder" and stype(t.faces[j]) == "Cylinder"
                            and same_cyl(t.faces[i], t.faces[j]))]
        if len(supports) >= 2:
            accepted.add(i)
    stack = list(accepted)
    while stack:
        i = stack.pop()
        for j in (tang[i] & cand) - accepted:
            if abs(radii[i] - radii[j]) <= GEOM_TOL:
                accepted.add(j)
                stack.append(j)
    return [[t.faces[i] for i in sorted(g)] for g in connected(accepted, t.nb)]


# ------------------------------------------------------------------------ protrusions
def face_points(f):
    pts = [v.Point for v in f.Vertexes]
    u0, u1, v0, v1 = urange(f)
    if all(math.isfinite(x) and abs(x) < 1e10 for x in (u0, u1, v0, v1)):
        for fu in (0.05, 0.25, 0.5, 0.75, 0.95):
            for fv in (0.05, 0.25, 0.5, 0.75, 0.95):
                try:
                    p = f.valueAt(u0 + fu * (u1 - u0), v0 + fv * (v1 - v0))
                    if f.isInside(p, GEOM_TOL, True):
                        pts.append(p)
                except Exception:
                    pass
    return pts


def plane_normal(f):
    n = f.Surface.Axis
    return -n if f.Orientation == "Reversed" else n


def surf_radius(f):
    k = stype(f)
    return (f.Surface.Radius if k in ("Cylinder", "Sphere") else
            f.Surface.MinorRadius if k == "Toroid" else 0.0)


def patch_descriptor(group, support, t):
    kinds = Counter(stype(t.faces[i]) for i in group)
    if kinds["Cylinder"] == 0 or (kinds["Sphere"] < 2 and kinds["Toroid"] < 2):
        return None
    if any(k not in ("Plane", "Cylinder", "Sphere", "Toroid") for k in kinds):
        return None
    normal = plane_normal(t.faces[support])
    cyls = [i for i in group if stype(t.faces[i]) == "Cylinder"
            and abs(normal.dot(t.faces[i].Surface.Axis)) < 1e-6 and sweep(t.faces[i]) < TWO_PI - 1e-5]
    if not cyls:
        return None
    main = max(cyls, key=lambda i: t.area[i])
    along = t.faces[main].Surface.Axis
    across = normal.cross(along)
    across.normalize()
    pts = [p for i in group for p in face_points(t.faces[i])]
    if not pts:
        return None
    origin = t.faces[support].Surface.Position
    proj = [[(p - origin).dot(d) for p in pts] for d in (along, across, normal)]
    ext = [max(v) - min(v) for v in proj]
    length, width = sorted(ext[:2], reverse=True)
    height = max(proj[2])
    if (width <= GEOM_TOL or length / width < MIN_ELONG or height <= MATCH_ABS
            or min(proj[2]) < -MAX_WALL - MATCH_ABS):
        return None
    entries = sorted((stype(t.faces[i]), t.area[i], surf_radius(t.faces[i])) for i in group)
    return {"indices": sorted(group), "support": support, "dims": [length, width, ext[2]],
            "surfaces": entries}


def close(x, y):
    return abs(x - y) <= max(MATCH_ABS, MATCH_REL * max(abs(x), abs(y)))


def descriptors_match(a, b):
    if len(a["surfaces"]) != len(b["surfaces"]):
        return False
    if not all(close(x, y) for x, y in zip(a["dims"], b["dims"])):
        return False
    return all(ka == kb and close(aa, ab) and close(ra, rb)
               for (ka, aa, ra), (kb, ab, rb) in zip(a["surfaces"], b["surfaces"]))


def protrusion_families(shape):
    t = Topo(shape)
    supports = [i for i, f in enumerate(t.faces) if stype(f) == "Plane" and t.area[i] >= MIN_SUPPORT_AREA]
    patches, seen = [], set()
    for s in sorted(supports, key=lambda i: t.area[i], reverse=True):
        sp = t.faces[s].Surface
        d = sp.Axis
        barriers = {i for i in supports
                    if abs(d.dot(t.faces[i].Surface.Axis)) > 1 - 1e-7
                    and abs((t.faces[i].Surface.Position - sp.Position).dot(d)) <= MAX_WALL}
        for grp in connected(set(range(len(t.faces))) - barriers, t.nb):
            ident = frozenset(grp)
            if (ident in seen or len(grp) > MAX_PATCH_FACES
                    or not any(s in t.nb[i] for i in grp)
                    or sum(t.area[i] for i in grp) > t.area[s] / 2):
                continue
            desc = patch_descriptor(grp, s, t)
            if desc is not None:
                seen.add(ident)
                patches.append(desc)
    fams = []
    for p in patches:
        fam = next((f for f in fams if f[0]["support"] == p["support"] and descriptors_match(f[0], p)), None)
        if fam is None:
            fams.append([p])
        else:
            fam.append(p)
    fams = [f for f in fams if len(f) >= 2]
    return t, fams


# ------------------------------------------------------------------------ registration
def _flat(groups):
    return [f for g in groups for f in g]


@core.set_rule("ref_holes")
def _holes(shape):
    return _flat(hole_groups(shape, core.PROFILE["hole_diameter"]))


@core.set_rule("ref_fillets", batch="try")
def _fillets(shape):
    return _flat(fillet_groups(shape, core.PROFILE["fillet_radius"]))


@core.set_rule("ref_protrusions", batch="only")
def _protrusions(shape):
    t, fams = protrusion_families(shape)
    return [t.faces[i] for fam in fams for p in fam for i in p["indices"]]
