"""EDGE TREATMENTS: rounded edges (fillets) and bevelled edges (chamfers, countersinks).

Rules: ref_fillets (port of the HP mentor's example; blends below profile "fillet_radius" that run tangent
into two supporting faces, removed together) and chamfer_edge (our own: a narrow face that meets two faces,
about a right angle apart, at 25-65 degrees; width <= profile "chamfer_size")."""
import math
import os
import sys

import Part

_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # .../src
for _p in (_SRC, os.path.join(_SRC, "engine")):                       # layers: engine/, rules/, ...
    if _p not in sys.path:
        sys.path.insert(0, _p)
import cleancad_core as core  # noqa: E402
from geom_utils import Topo, stype, flatten, sweep, outward_normal, same_cyl, connected, angle_deg, SIZE_TOL, TWO_PI, GEOM_TOL  # noqa: E402,F401

CHAMFER_ANGLE = (25.0, 65.0)
CHAMFER_RIGHT_ANGLE = (65.0, 115.0)
MIN_CHAMFER_WIDTH = 0.1


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


def _edge_normals(face_a, face_b, edge):
    try:
        p = edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2)
        na = face_a.normalAt(*face_a.Surface.parameter(p))
        nb = face_b.normalAt(*face_b.Surface.parameter(p))
        return na, nb
    except Exception:                       # noqa: BLE001
        return None


def chamfer_faces(shape):
    t = Topo(shape)
    limit = core.PROFILE.get("chamfer_size", 5.0)
    picked = []
    for i, f in enumerate(t.faces):
        shared = {}                         # neighbour -> (total shared edge length, one edge)
        for e, owners in t.edges:
            if i in owners and len(owners) == 2:
                j = next(iter(owners - {i}))
                total, _ = shared.get(j, (0.0, None))
                shared[j] = (total + e.Length, e)
        if len(shared) < 2:
            continue
        (j1, (l1, e1)), (j2, (l2, e2)) = sorted(shared.items(), key=lambda kv: -kv[1][0])[:2]
        width = t.area[i] / max((l1 + l2) / 2, 1e-9)
        if not (MIN_CHAMFER_WIDTH <= width <= limit):
            continue
        n1 = _edge_normals(f, t.faces[j1], e1)
        n2 = _edge_normals(f, t.faces[j2], e2)
        if not n1 or not n2:
            continue
        a1, a2 = angle_deg(*n1), angle_deg(*n2)
        # the two faces on either side, compared where they meet the chamfer
        between = angle_deg(n1[1], n2[1])
        if (CHAMFER_ANGLE[0] <= a1 <= CHAMFER_ANGLE[1] and CHAMFER_ANGLE[0] <= a2 <= CHAMFER_ANGLE[1]
                and CHAMFER_RIGHT_ANGLE[0] <= between <= CHAMFER_RIGHT_ANGLE[1]
                and abs(a1 + a2 - between) <= 15.0):
            picked.append(i)
    return t, picked


@core.set_rule("ref_fillets", batch="try", category="edges")
def _fillets(shape):
    return flatten(fillet_groups(shape, core.PROFILE["fillet_radius"]))


@core.set_rule("chamfer_edge", category="edges")
def _chamfer_edge(shape):
    t, picked = chamfer_faces(shape)
    return [t.faces[i] for i in picked]
