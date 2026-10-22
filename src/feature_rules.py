"""Rules for straight ribs, bosses and chamfers, registered in the CleanCAD pipeline.

Generic geometry, not tied to the shape of the test parts (no fixed base height):

PROTRUSIONS (rules "rib" and "boss")
  Start at the inner wires of a planar host face (the footprint of whatever stands on it). Collect the
  faces that stand on the outer side of the host plane, reached from the wire by edge adjacency; faces that
  reach below the host plane (the plate itself, a hole that also runs through the plate) never belong.
  The footprint decides what it is:
    boss  - the footprint is a circle (a column) up to profile "boss_max_diameter";
    rib   - a thin footprint (mean thickness 2*area/perimeter <= profile "rib_max_thickness") that is
            at least 3 thicknesses long;
  Anything lower than the logo depth cap (profile "logo_max_depth") is a marking and left to the logo rule;
  other shapes are not selected.
  Ribs that touch the EDGE of the host (so that the host has no inner wire for them, as on cut-out
  samples) are found from the host's outer wire: every connected group of faces standing on the outer
  side of the host plane is a candidate and is taken for a rib when its footprint box is thin
  (<= "rib_max_thickness") and at least twice as long as wide.
CHAMFERS (rule "chamfer_edge")
  A narrow face between two faces that it meets at 25-65 degrees, where those two faces are about a right
  angle apart (a chamfer or countersink replaces a 90 degree edge); width <= profile "chamfer_size".
The limits are starting values, not validated criteria.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cleancad_core as core  # noqa: E402
from geom_utils import Topo, stype, face_points  # noqa: E402
from logo_rules import is_circle_wire, plane_frame, box2d  # noqa: E402

MIN_HOST_AREA = 50.0
BELOW_TOL = 0.1            # mm: a face may dip this far below the host plane (root blends) and still stand on it
RIB_MIN_LENGTH_FACTOR = 3.0
EDGE_RIB_LENGTH_FACTOR = 2.0
MIN_EDGE_RIB_FACES = 3       # a rib is more than one sliver face
CHAMFER_ANGLE = (25.0, 65.0)
CHAMFER_RIGHT_ANGLE = (65.0, 115.0)
MIN_CHAMFER_WIDTH = 0.1


def _owners_index(topo):
    index = {}
    for e, owners in topo.edges:
        index.setdefault(e.hashCode(), []).append((e, owners))

    def owners_of(edge):
        for e, owners in index.get(edge.hashCode(), []):
            if e.isSame(edge):
                return owners
        return set()
    return owners_of


def protrusion_bundles(shape):
    """-> (topo, [{"kind": "rib"|"boss", "host": i, "faces": [...], "height": h, "thickness": t}])"""
    t = Topo(shape)
    owners_of = _owners_index(t)
    prof = core.PROFILE
    logo_cap = prof.get("logo_max_depth") or 0.0
    boss_max = prof.get("boss_max_diameter", 20.0)
    rib_max = prof.get("rib_max_thickness", 4.0)
    pts_cache = {}

    def points(i):
        if i not in pts_cache:
            pts_cache[i] = face_points(t.faces[i])
        return pts_cache[i]

    out = []
    for h, host in enumerate(t.faces):
        if stype(host) != "Plane" or t.area[h] < MIN_HOST_AREA:
            continue
        origin, n, u, v = plane_frame(host)

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
                    if f in bundle or f == h:
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
            tops = [f for f in bundle if stype(t.faces[f]) == "Plane"
                    and abs(plane_frame(t.faces[f])[1].dot(n)) > 1 - 1e-6
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
            elif thickness <= rib_max and length >= RIB_MIN_LENGTH_FACTOR * thickness:
                kind = "rib"
            else:
                kind = None
            if kind:
                out.append({"kind": kind, "host": h, "faces": sorted(bundle), "height": height,
                            "thickness": thickness, "length": length})
        # ribs that reach the edge of the host: components of the faces standing on the host plane,
        # started from the OUTER wire (the faces below the plane are the plate itself and never qualify)
        taken = {i for b in out if b["host"] == h for i in b["faces"]}
        seeds = set()
        for e in host.OuterWire.Edges:
            seeds |= owners_of(e)
        seeds -= {h} | taken
        seen = set()
        for seed in sorted(seeds):
            if seed in seen or not _above(heights(seed)):
                continue
            comp, stack = {seed}, [seed]
            while stack:
                x = stack.pop()
                for y in t.nb[x]:
                    if y != h and y not in comp and y not in taken and _above(heights(y)):
                        comp.add(y)
                        stack.append(y)
            seen |= comp
            height = max(max(heights(f)) for f in comp)
            if height <= logo_cap + 1e-6 or len(comp) < MIN_EDGE_RIB_FACES:
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


@core.removal_fallback
def cut_protrusion(shape, group):
    """When defeaturing() cannot remove a rib / boss (free-form faces, an edge-attached rib), cut away the
    prism standing on its host plane: the footprint box of the faces, from the plane up past their top."""
    from FreeCAD import Matrix, Placement
    wanted = {core.sig(f) for f in group}
    t, bundles = protrusion_bundles(shape)
    for b in bundles:
        if wanted <= {core.sig(t.faces[i]) for i in b["faces"]}:
            origin, n, u, v = plane_frame(t.faces[b["host"]])
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


def _angle(a, b):
    d = max(-1.0, min(1.0, a.dot(b)))
    return math.degrees(math.acos(d))


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
        a1, a2 = _angle(*n1), _angle(*n2)
        # the two faces on either side, compared where they meet the chamfer
        between = _angle(n1[1], n2[1])
        if (CHAMFER_ANGLE[0] <= a1 <= CHAMFER_ANGLE[1] and CHAMFER_ANGLE[0] <= a2 <= CHAMFER_ANGLE[1]
                and CHAMFER_RIGHT_ANGLE[0] <= between <= CHAMFER_RIGHT_ANGLE[1]
                and abs(a1 + a2 - between) <= 15.0):
            picked.append(i)
    return t, picked


@core.set_rule("rib")
def _rib(shape):
    t, bundles = protrusion_bundles(shape)
    return [t.faces[i] for i in sorted({i for b in bundles if b["kind"] == "rib" for i in b["faces"]})]


@core.set_rule("boss")
def _boss(shape):
    t, bundles = protrusion_bundles(shape)
    return [t.faces[i] for i in sorted({i for b in bundles if b["kind"] == "boss" for i in b["faces"]})]


@core.set_rule("chamfer_edge")
def _chamfer_edge(shape):
    t, picked = chamfer_faces(shape)
    return [t.faces[i] for i in picked]
