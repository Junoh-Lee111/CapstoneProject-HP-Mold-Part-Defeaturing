"""Logo / marking (engraving and emboss) recognition, registered in the CleanCAD pipeline as "logo".

Geometric and topological heuristic from the HP mentor's rule description (no image, no OCR):
 1. Hosts are planar faces; the starting points are the INNER WIRES of a host. An inner wire that is a
    single circle is an ordinary hole and is skipped - unless the host has several inner wires and
    more than one of them is non-circular (a multi-glyph structure: the circles are letters like O, 0).
 2. From the faces next to a wire, follow the edge adjacency for at most 3 steps through SHALLOW faces:
    smaller than 20 % of the host and not deeper (along the host normal) than 0.35 x the wire size.
 3. (our addition) the depth may also not exceed the profile value "logo_max_depth", if set.
 4. A bundle whose total area exceeds 25 % of the host is not a logo.
 5. A wire that has a matching inner boundary on a facing, antiparallel planar face is a through
    slot / cut, not a logo, and is skipped.
All faces of an accepted bundle (walls, floors, tops of every glyph part) are selected for removal.
The limits are parameters of that description, not validated general criteria.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cleancad_core as core  # noqa: E402
from ref_rules import Topo, stype  # noqa: E402

MIN_HOST_AREA = 20.0        # mm2: smaller planar faces are not logo hosts
MAX_FACE_FRACTION = 0.20    # a bundle face must be smaller than this part of the host area
MAX_BUNDLE_FRACTION = 0.25  # the whole bundle must be smaller than this part of the host area
DEPTH_FACTOR = 0.35         # depth <= factor * size of the wire
MAX_HOPS = 3
# Our own addition to the mentor's description (confirm with HP): marks are shallow in absolute terms
# (HP's samples: 0.15 mm), a blind pocket of 1.5 mm is not. Set profile "logo_max_depth" to None to switch off.
OVERLAP = 0.5               # facing inner wire counts as "the same" when its box overlaps this much


def is_circle_wire(wire):
    edges = wire.Edges
    if not edges or any(type(e.Curve).__name__ != "Circle" for e in edges):
        return False
    c0 = edges[0].Curve
    return all(abs(e.Curve.Radius - c0.Radius) < 1e-6 and (e.Curve.Center - c0.Center).Length < 1e-6
               for e in edges)


def plane_frame(face):
    """Origin, unit normal and two in-plane unit axes of a planar face."""
    s = face.Surface
    n = s.Axis * (-1 if face.Orientation == "Reversed" else 1)
    u = s.XDir if hasattr(s, "XDir") else None
    if u is None or abs(u.dot(n)) > 1e-6:
        u = n.cross(core.FreeCAD.Vector(1, 0, 0))
        if u.Length < 1e-6:
            u = n.cross(core.FreeCAD.Vector(0, 1, 0))
    u.normalize()
    v = n.cross(u)
    v.normalize()
    return s.Position, n, u, v


def box2d(points, u, v):
    us = [p.dot(u) for p in points]
    vs = [p.dot(v) for p in points]
    return min(us), max(us), min(vs), max(vs)


def overlap_ratio(a, b):
    w = min(a[1], b[1]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[2], b[2])
    if w <= 0 or h <= 0:
        return 0.0
    area = lambda r: (r[1] - r[0]) * (r[3] - r[2])  # noqa: E731
    return w * h / max(min(area(a), area(b)), 1e-12)


def face_depth(face, origin, n):
    """Largest distance of the face from the host plane, along the host normal."""
    bb = face.BoundBox
    return max(abs((core.FreeCAD.Vector(x, y, z) - origin).dot(n))
               for x in (bb.XMin, bb.XMax) for y in (bb.YMin, bb.YMax) for z in (bb.ZMin, bb.ZMax))


def logo_bundles(shape):
    """-> list of dicts {"host": index, "faces": [indices]} for every accepted engraving / emboss."""
    t = Topo(shape)
    max_depth = core.PROFILE.get("logo_max_depth")
    edge_owners = {}
    for e, owners in t.edges:
        edge_owners.setdefault(e.hashCode(), []).append((e, owners))

    def owners_of(edge):
        for e, owners in edge_owners.get(edge.hashCode(), []):
            if e.isSame(edge):
                return owners
        return set()

    hosts = [i for i, f in enumerate(t.faces)
             if stype(f) == "Plane" and len(f.Wires) > 1 and t.area[i] >= MIN_HOST_AREA]
    frames = {i: plane_frame(t.faces[i]) for i, f in enumerate(t.faces) if stype(f) == "Plane"}
    bundles = []
    for h in hosts:
        host = t.faces[h]
        origin, n, u, v = frames[h]
        inner = [w for w in host.Wires if not w.isSame(host.OuterWire)]
        non_circle = [w for w in inner if not is_circle_wire(w)]
        multi_glyph = len(inner) > 1 and len(non_circle) > 1
        candidates = inner if multi_glyph else non_circle
        # inner boundaries of facing planes (antiparallel normal), projected in this host's frame
        facing = []
        for o, (oo, on, _, _) in frames.items():
            if o != h and on.dot(n) < -0.999:
                for w in t.faces[o].Wires:
                    if not w.isSame(t.faces[o].OuterWire):
                        facing.append(box2d([vx.Point for vx in w.Vertexes], u, v))
        for wire in candidates:
            pts = [vx.Point for vx in wire.Vertexes]
            if not pts:
                continue
            wb = box2d(pts, u, v)
            size = max(wb[1] - wb[0], wb[3] - wb[2])
            if any(overlap_ratio(wb, fb) >= OVERLAP for fb in facing):
                continue        # through slot / cut
            seeds = set()
            for e in wire.Edges:
                seeds |= owners_of(e)
            seeds.discard(h)
            bundle, frontier = set(), set(seeds)
            for _ in range(MAX_HOPS + 1):
                nxt = set()
                for f in frontier:
                    if f in bundle or f == h:
                        continue
                    if t.area[f] >= MAX_FACE_FRACTION * t.area[h]:
                        continue
                    depth = face_depth(t.faces[f], origin, n)
                    if depth > DEPTH_FACTOR * size + 1e-6:
                        continue
                    if max_depth is not None and depth > max_depth + 1e-6:
                        continue
                    if (stype(t.faces[f]) == "Plane" and abs(frames[f][1].dot(n)) > 1 - 1e-9
                            and abs((frames[f][0] - origin).dot(n)) < 1e-6):
                        continue        # coplanar with the host: part of the host, not of the engraving
                    bundle.add(f)
                    nxt |= t.nb[f]
                frontier = nxt - bundle
            if bundle and sum(t.area[f] for f in bundle) <= MAX_BUNDLE_FRACTION * t.area[h]:
                bundles.append({"host": h, "faces": sorted(bundle)})
    return t, bundles


@core.set_rule("logo", batch="try")
def _logo(shape):
    t, bundles = logo_bundles(shape)
    chosen = sorted({i for b in bundles for i in b["faces"]})
    return [t.faces[i] for i in chosen]
