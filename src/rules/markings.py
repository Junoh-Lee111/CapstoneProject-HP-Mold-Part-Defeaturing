"""MARKINGS: logos, text and other marks engraved into or raised from a flat face.

Rule: logo - geometric / topological heuristic from the HP mentor's rule description (no image, no OCR):
 1. Hosts are flat faces; the starting points are the INNER WIRES of a host. A wire that is a single circle is
    an ordinary hole and is skipped - unless the host has several inner wires and more than one of them is
    non-circular (a multi-glyph structure: the circles are letters like O, 0).
 2. From the faces next to a wire, follow the edge adjacency for at most 3 steps through SHALLOW faces:
    smaller than 20 % of the host and not deeper (along the host normal) than 0.35 x the wire size.
 3. (our addition) the depth may also not exceed the profile value "logo_max_depth", if set.
 4. A bundle whose total area exceeds 25 % of the host is not a logo.
 5. A wire that has a matching inner boundary on a facing, antiparallel flat face is a through slot / cut.
Fallback: on surface models (shells, no solid) a logo is removed by re-making the host face without the
holes the logo cut. The limits are parameters of that description, not validated general criteria."""
import math
import os
import sys

import Part

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cleancad_core as core  # noqa: E402
from geom_utils import Topo, stype, plane_frame, box2d, is_circle_wire  # noqa: E402,F401

MIN_HOST_AREA = 20.0        # mm2: smaller flat faces are not logo hosts
MAX_FACE_FRACTION = 0.20    # a bundle face must be smaller than this part of the host area
MAX_BUNDLE_FRACTION = 0.25  # the whole bundle must be smaller than this part of the host area
DEPTH_FACTOR = 0.35         # depth <= factor * size of the wire
MAX_HOPS = 3
OVERLAP = 0.5               # facing inner wire counts as "the same" when its box overlaps this much


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
             if t.plane(i) is not None and len(f.Wires) > 1 and t.area[i] >= MIN_HOST_AREA]
    frames = {i: plane_frame(t.faces[i], t.plane(i)) for i in range(len(t.faces)) if t.plane(i) is not None}
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
                    if (f in frames and abs(frames[f][1].dot(n)) > 1 - 1e-9
                            and abs((frames[f][0] - origin).dot(n)) < 1e-6):
                        continue        # coplanar with the host: part of the host, not of the engraving
                    bundle.add(f)
                    nxt |= t.nb[f]
                frontier = nxt - bundle
            if bundle and sum(t.area[f] for f in bundle) <= MAX_BUNDLE_FRACTION * t.area[h]:
                bundles.append({"host": h, "faces": sorted(bundle)})
    return t, bundles


@core.set_rule("logo", batch="try", category="markings")
def _logo(shape):
    t, bundles = logo_bundles(shape)
    chosen = sorted({i for b in bundles for i in b["faces"]})
    return [t.faces[i] for i in chosen]


@core.removal_fallback
def rebuild_surface_model(shape, group):
    """Surface models (shells of faces, no solid) cannot be defeatured. A logo is removed there by
    dropping its faces and re-making the host face without the holes the logo had cut into it."""
    import Part
    if shape.Solids:
        return None
    t, bundles = logo_bundles(shape)
    wanted = {core.sig(f) for f in group}
    mine = [b for b in bundles if {core.sig(t.faces[i]) for i in b["faces"]} <= wanted]
    if not mine:
        return None
    gone = {i for b in mine for i in b["faces"]}
    new_faces, hosts_done = [], set()
    for b in mine:
        h = b["host"]
        if h in hosts_done:
            continue
        hosts_done.add(h)
        host = t.faces[h]
        claimed = set()
        for w in host.Wires:
            if w.isSame(host.OuterWire):
                continue
            if any(o in gone for e in w.Edges for o in _owners(t, e)):
                claimed.add(id(w))
        keep = [w for w in host.Wires if not w.isSame(host.OuterWire) and id(w) not in claimed]
        face = Part.Face(host.OuterWire)
        for w in keep:
            face = face.cut(Part.Face(w))
        new_faces.append(face)
    # the islands inside letters like A or O lie in the host plane and touch the logo: they go with it
    for b in mine:
        h = b["host"]
        o_h, n_h = plane_frame(t.faces[h], t.plane(h))[:2]
        for i, f in enumerate(t.faces):
            if i in gone or i == h or t.plane(i) is None or t.area[i] >= MAX_FACE_FRACTION * t.area[h]:
                continue
            o_i, n_i = plane_frame(f, t.plane(i))[:2]
            if n_i.dot(n_h) > 1 - 1e-9 and abs((o_i - o_h).dot(n_h)) < 1e-4 and t.nb[i] & gone:
                gone.add(i)
    skip = gone | hosts_done
    new_faces += [f for i, f in enumerate(t.faces) if i not in skip]
    return "result", Part.Compound(new_faces)


def _owners(topo, edge):
    for e, owners in topo.edges:
        if e.isSame(edge):
            return owners
    return set()
