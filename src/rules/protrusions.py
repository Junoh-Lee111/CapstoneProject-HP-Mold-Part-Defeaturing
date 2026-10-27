"""PROTRUSIONS: things that stand up from a flat face - ribs, bosses and repeated rounded bumps.

Rules: ref_protrusions (port of the HP mentor's example: rounded, elongated patches that occur at least
twice with the same shape), rib (thin and long, also over a gentle bend and at the edge of a part) and boss
(a round column up to profile "boss_max_diameter"). Fallback: when defeaturing() cannot remove one, the
prism standing on its host plane is cut away."""
import math
import os
import sys

import Part

_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # .../src
for _p in (_SRC, os.path.join(_SRC, "engine")):                       # layers: engine/, rules/, ...
    if _p not in sys.path:
        sys.path.insert(0, _p)
import cleancad_core as core  # noqa: E402
from collections import Counter  # noqa: E402

from geom_utils import (Topo, stype, flatten, face_points, plane_frame, box2d, is_circle_wire,  # noqa: E402,F401
                        angle_deg, owners_index, connected, inward_cylinder, sweep, GEOM_TOL, TWO_PI)

# --- HP-example style repeated protrusions
MIN_SUPPORT_AREA = 500.0
MAX_WALL = 5.0
MAX_PATCH_FACES = 60
MIN_ELONG = 1.5
MATCH_REL, MATCH_ABS = 0.02, 0.05

# --- our rib / boss recognition
MIN_HOST_AREA = 50.0
BELOW_TOL = 0.1            # mm: a face may dip this far below the host plane (root blends) and still stand on it
RIB_MIN_LENGTH_FACTOR = 3.0
EDGE_RIB_LENGTH_FACTOR = 2.0
EDGE_RIB_MAX_HEIGHT = 3.0    # mm: a taller group at the edge is structure (a wall, a flange), not a rib
MIN_EDGE_RIB_FACES = 3       # a rib is more than one sliver face
BENT_MAX_HEIGHT = 3.0   # mm: height limit for the part of a rib that lies on a bent-away neighbour host
BEND_ANGLE = 20.0       # degrees: flat faces this close in direction count as one gently bent host


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


def protrusion_bundles(shape):
    """-> (topo, [{"kind": "rib"|"boss", "host": i, "faces": [...], "height": h, "thickness": t}])"""
    t = Topo(shape)
    owners_of = owners_index(t)
    prof = core.PROFILE
    logo_cap = prof.get("logo_max_depth") or 0.0
    boss_max = prof.get("boss_max_diameter", 20.0)
    rib_max = prof.get("rib_max_thickness", 4.0)
    pts_cache = {}

    def points(i):
        if i not in pts_cache:
            pts_cache[i] = face_points(t.faces[i])
        return pts_cache[i]

    bores = {}

    def bore_wall(i):
        """A complete round hole wall. A hole is never part of a boss or a rib: the hole rules decide on it
        (a boss keeps the hole that runs through it)."""
        if i not in bores:
            f = t.faces[i]
            bores[i] = stype(f) == "Cylinder" and sweep(f) >= TWO_PI - 1e-5 and inward_cylinder(f)
        return bores[i]

    out = []
    for h, host in enumerate(t.faces):
        if t.plane(h) is None or t.area[h] < MIN_HOST_AREA:
            continue
        origin, n, u, v = plane_frame(host, t.plane(h))

        def heights(i):
            return [(p - origin).dot(n) for p in points(i)]

        for wire in [w for w in host.Wires if not w.isSame(host.OuterWire)]:
            seeds = set()
            for e in wire.Edges:
                seeds |= owners_of(e)
            seeds.discard(h)
            bundle, frontier = set(), set(seeds)
            while frontier:
                nxt = set()
                for f in frontier:
                    if f in bundle or f == h or bore_wall(f):
                        continue
                    hs = heights(f)
                    if not hs or min(hs) < -BELOW_TOL:
                        continue            # reaches below the host plane: not standing on it
                    if max(hs) < BELOW_TOL:
                        continue            # lies in the host plane
                    bundle.add(f)
                    nxt |= t.nb[f]
                frontier = nxt - bundle
            if not bundle:
                continue
            height = max(max(heights(f)) for f in bundle)
            if height <= logo_cap + 1e-6:
                continue                    # a marking, handled by the logo rule
            # Mean thickness from the TOP faces (parallel to the host, at the top of the bundle): a
            # network of crossing ribs encloses cells, so its outline wire is not a thin strip, but its
            # top face (with the cells as holes) is. thickness = 2 * area / perimeter of those faces.
            tops = [f for f in bundle if t.plane(f) is not None
                    and abs(plane_frame(t.faces[f], t.plane(f))[1].dot(n)) > 1 - 1e-6
                    and max(heights(f)) >= height - BELOW_TOL]
            if tops:
                area = sum(t.area[f] for f in tops)
                perimeter = sum(w.Length for f in tops for w in t.faces[f].Wires)
                tb = [vx.Point for f in tops for vx in t.faces[f].Vertexes]
            else:
                area, perimeter, tb = None, 0.0, [vx.Point for vx in wire.Vertexes]
                try:
                    area = __import__("Part").Face(wire).Area
                except Exception:           # noqa: BLE001
                    continue
                perimeter = wire.Length
            thickness = 2 * area / perimeter if perimeter else 0.0
            wb = box2d(tb, u, v)
            length = max(wb[1] - wb[0], wb[3] - wb[2])
            if is_circle_wire(wire):
                kind = "boss" if 2 * wire.Edges[0].Curve.Radius <= boss_max else None
                # a boss with a hole through it (a ring around a fastener hole) is a functional feature: it stays
                if kind and any(len(t.faces[f].Wires) > 1 for f in tops):
                    kind = None
            elif thickness <= rib_max and length >= RIB_MIN_LENGTH_FACTOR * thickness:
                kind = "rib"
            else:
                kind = None
            if kind:
                out.append({"kind": kind, "host": h, "faces": sorted(bundle), "height": height,
                            "thickness": thickness, "length": length})
        # ribs that reach the edge of the host: components of the faces standing on the host plane,
        # started from the OUTER wire (the faces below the plane are the plate itself and never qualify).
        # The host may be a gently bent sheet: faces are also measured against the neighbouring flat
        # faces reached through bends of at most BEND_ANGLE degrees, so a rib running over a bend is one rib.
        taken = {i for b in out for i in b["faces"]}
        near = _bent_hosts(t, h)
        frames = {q: plane_frame(t.faces[q], t.plane(q)) for q in near}

        def support(y, parent):
            """The flat face that y stands on (parent's support, or a touching bent host), else None."""
            for q in [parent] + [q for q in near if q != parent and q in t.nb[y]]:
                o_q, n_q = frames[q][0], frames[q][1]
                hs_q = [(p - o_q).dot(n_q) for p in points(y)]
                # beyond the first host only low features count: a tall wall is not part of a rib
                if _above(hs_q) and (q == h or max(hs_q) <= BENT_MAX_HEIGHT):
                    return q
            return None

        seeds = set()
        for e in host.OuterWire.Edges:
            seeds |= owners_of(e)
        seeds -= set(near) | taken
        seen = set()
        for seed in sorted(seeds):
            if seed in seen:
                continue
            sup0 = support(seed, h)
            if sup0 is None:
                continue
            comp, sup, stack = {seed}, {seed: sup0}, [seed]
            while stack:
                x = stack.pop()
                for y in t.nb[x]:
                    if y in near or y in comp or y in taken or bore_wall(y):
                        continue
                    s_y = support(y, sup[x])
                    if s_y is not None:
                        comp.add(y)
                        sup[y] = s_y
                        stack.append(y)
            seen |= comp
            height = max(max((p - frames[sup[f]][0]).dot(frames[sup[f]][1]) for p in points(f)) for f in comp)
            if (height <= logo_cap + 1e-6 or height > EDGE_RIB_MAX_HEIGHT
                    or len(comp) < MIN_EDGE_RIB_FACES):
                continue
            box = box2d([p for f in comp for p in points(f)], u, v)
            side_a, side_b = box[1] - box[0], box[3] - box[2]
            width, length = min(side_a, side_b), max(side_a, side_b)
            if 0 < width <= rib_max and length >= EDGE_RIB_LENGTH_FACTOR * width:
                out.append({"kind": "rib", "host": h, "faces": sorted(comp), "height": height,
                            "thickness": width, "length": length})
    return t, out


def _above(hs):
    return bool(hs) and min(hs) >= -BELOW_TOL and max(hs) > BELOW_TOL


def _bent_hosts(t, h):
    """h and the flat faces of a minimum host size reachable from it through shared edges at bends of
    at most BEND_ANGLE degrees."""
    norm = {}

    def normal(i):
        if i not in norm:
            norm[i] = plane_frame(t.faces[i], t.plane(i))[1]
        return norm[i]

    found, stack = {h}, [h]
    while stack:
        x = stack.pop()
        for y in t.nb[x]:
            if (y not in found and t.plane(y) is not None and t.area[y] >= MIN_HOST_AREA
                    and angle_deg(normal(x), normal(y)) <= BEND_ANGLE):
                found.add(y)
                stack.append(y)
    return found


@core.removal_fallback
def cut_protrusion(shape, group):
    """When defeaturing() cannot remove a rib / boss (free-form faces, an edge-attached rib), cut away the
    prism standing on its host plane: the footprint box of the faces, from the plane up past their top."""
    from FreeCAD import Matrix, Placement
    wanted = {core.sig(f) for f in group}
    t, bundles = protrusion_bundles(shape)
    for b in bundles:
        if wanted <= {core.sig(t.faces[i]) for i in b["faces"]}:
            origin, n, u, v = plane_frame(t.faces[b["host"]], t.plane(b["host"]))
            pts = [p for i in b["faces"] for p in face_points(t.faces[i])]
            box = box2d(pts, u, v)
            margin = 0.3
            a0, b0 = box[0] - margin, box[2] - margin
            prism = __import__("Part").makeBox(box[1] - box[0] + 2 * margin, box[3] - box[2] + 2 * margin,
                                               b["height"] + 1.0)
            corner = u * a0 + v * b0 + n * origin.dot(n)
            prism.Placement = Placement(Matrix(u.x, v.x, n.x, corner.x, u.y, v.y, n.y, corner.y,
                                               u.z, v.z, n.z, corner.z, 0, 0, 0, 1))
            return prism
    return None


@core.set_rule("ref_protrusions", batch="only", category="protrusions")
def _protrusions(shape):
    t, fams = protrusion_families(shape)
    return [t.faces[i] for fam in fams for p in fam for i in p["indices"]]


@core.set_rule("rib", category="protrusions")
def _rib(shape):
    t, bundles = protrusion_bundles(shape)
    return [t.faces[i] for i in sorted({i for b in bundles if b["kind"] == "rib" for i in b["faces"]})]


@core.set_rule("boss", category="protrusions")
def _boss(shape):
    t, bundles = protrusion_bundles(shape)
    return [t.faces[i] for i in sorted({i for b in bundles if b["kind"] == "boss" for i in b["faces"]})]
