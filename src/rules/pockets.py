"""POCKETS: shallow recesses in a flat face are filled flat ("replace face / flatten", mentor Emboss / Deboss and
Replace Face: Remove). Holes in the floor of a recess stay.

Rule: flatten - works from the INNER WIRES of a flat host face (the rim of a recess):
 1. from the faces next to the rim follow the edge adjacency for at most 3 steps (the recess walls, its floor, pads
    and countersinks inside it);
 2. the floor depth is the depth of the deepest up-facing face of those; faces that go deeper (the walls of a hole
    through the floor) and faces that rise above the host plane (a boss standing in the recess) are NOT part of it;
 3. accepted when the recess is shallow (at most half of the part's thickness at that place), not a blind round hole
    or counterbore (cylinder walls and a flat floor, deeper than 0.35 x its width: the hole rule decides those), and the loops where the recess
    meets the faces left out are flat (so a hole can be kept).
The removal does not use the CAD kernel's defeaturing (slow and unreliable on free-form recesses) but two simple
solids: the rim face pushed down to the floor depth is fused to the part, after the holes' cross-sections have been
cut out of it. Limits are parameters of this description, not validated general criteria."""
import os
import sys

import Part
from FreeCAD import Vector

_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # .../src
for _p in (_SRC, os.path.join(_SRC, "engine")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import cleancad_core as core  # noqa: E402
from geom_utils import Topo, stype, plane_frame, face_points  # noqa: E402

MIN_HOST_AREA = 20.0         # mm2: smaller flat faces are not recess hosts
MAX_HOPS = 3                 # steps from the rim through the recess
ABOVE_TOL = 1e-4             # mm: nothing of a recess may stand above the host plane
MAX_DEPTH_FRACTION = 0.5     # the recess is at most this part of the part's thickness deep
MIN_DEPTH = 0.05             # mm
MAX_MEMBERS = 80             # a recess with more faces than this is not a recess (the search leaked)
HOLE_DEPTH_RATIO = 0.35      # cylinder walls and a flat floor, deeper than this x the width: a blind hole, not a recess
LEVEL_TOL = 0.02             # mm: a loop counts as flat and parallel to the host within this
EPS = 0.02                   # mm: overlap of the hole tools below the filler


def _loops(edges):
    """Group edges into closed wires."""
    return [Part.Wire(w) for w in Part.sortEdges(edges)]


def pocket_bundles(shape):
    """-> (topo, [bundle]) with bundle = {"host", "faces": [indices], "depth", "n", "origin", "rim": wire, "loops": [wire]}."""
    t = Topo(shape)
    if not shape.Solids:
        return t, []            # surface models (pressed sheets): their engravings belong to the logo rule
    edge_owners = {}
    for e, owners in t.edges:
        edge_owners.setdefault(e.hashCode(), []).append((e, owners))

    def owners_of(edge):
        for e, owners in edge_owners.get(edge.hashCode(), []):
            if e.isSame(edge):
                return owners
        return set()

    bundles = []
    all_points = [v.Point for v in shape.Vertexes]
    for h, host in enumerate(t.faces):
        if t.plane(h) is None or t.area[h] < MIN_HOST_AREA or len(host.Wires) < 2:
            continue
        origin, n, _, _ = plane_frame(host, t.plane(h))
        levels = [(p - origin).dot(n) for p in all_points]
        thickness = max(levels) - min(levels)
        heights = {}

        def hs(i):
            if i not in heights:
                heights[i] = [(p - origin).dot(n) for p in face_points(t.faces[i])]
            return heights[i]

        for wire in host.Wires:
            if wire.isSame(host.OuterWire):
                continue
            seeds = set()
            for e in wire.Edges:
                seeds |= owners_of(e)
            seeds.discard(h)
            reached, frontier = set(seeds), set(seeds)
            for _ in range(MAX_HOPS - 1):
                nxt = set()
                for i in frontier:
                    nxt |= {o for o in t.nb[i] if o != h and o not in reached}
                reached |= nxt
                frontier = nxt
            below = {i for i in reached if max(hs(i)) <= ABOVE_TOL}        # nothing standing above the host plane
            # the floor depth: the deepest face that looks up out of the recess
            up_depths = []
            for i in below:
                f = t.faces[i]
                try:
                    u0, u1, v0, v1 = f.ParameterRange
                    normal = f.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
                except Exception:                           # noqa: BLE001
                    continue
                if normal.dot(n) > 0.3:
                    up_depths.append(-min(hs(i)))
            if not up_depths:
                continue
            depth = max(up_depths)
            if depth < MIN_DEPTH or depth > MAX_DEPTH_FRACTION * thickness:
                continue
            members = {i for i in below if -min(hs(i)) <= depth + 0.05}
            if not members or seeds - members:
                continue            # a face at the rim goes deeper than the floor: a hole or a step, not a recess
            # pads and dimples inside the recess may lie more than 3 steps from the rim: take every face connected to
            # the recess that is no deeper than the floor and does not rise above the host plane
            stack = list(members)
            while stack and len(members) <= MAX_MEMBERS:
                for o in t.nb[stack.pop()]:
                    if o != h and o not in members and max(hs(o)) <= ABOVE_TOL and -min(hs(o)) <= depth + 0.05:
                        members.add(o)
                        stack.append(o)
            if len(members) > MAX_MEMBERS:
                continue            # it leaks into the rest of the part: not a recess
            kinds = {stype(t.faces[i]) for i in members}
            bb = wire.BoundBox
            size = max(bb.XLength, bb.YLength, bb.ZLength)
            if (kinds <= {"Cylinder", "Plane"} and any(stype(t.faces[i]) == "Cylinder" for i in members)
                    and depth > HOLE_DEPTH_RATIO * size):
                continue            # a blind hole / counterbore (deep for its width): the hole rule decides
            # where the recess meets what was left out: flat loops (holes through the floor, bosses in the recess)
            cut_edges = [e for e, owners in t.edges
                         if owners & members and (owners - members - {h})]
            loops, flat = [], True
            for loop in _loops(cut_edges):
                lv = [(v.Point - origin).dot(n) for v in loop.Vertexes]
                if max(lv) - min(lv) > LEVEL_TOL:
                    flat = False
                    break
                loops.append(loop)
            if not flat:
                continue
            bundles.append({"host": h, "faces": sorted(members), "depth": depth, "n": n, "origin": origin,
                            "rim": wire, "loops": loops})
    return t, bundles


def fill(shape, b):
    """The part with this recess filled flat; None if it did not work."""
    n, depth = b["n"], b["depth"]
    try:
        prism = Part.Face(b["rim"]).extrude(n * -depth)
        tools = []
        for loop in b["loops"]:
            level = (loop.Vertexes[0].Point - b["origin"]).dot(n)           # < 0: below the host plane
            face = Part.Face(loop)
            face.translate(n * -level)                                       # up to the host plane
            tools.append(face.extrude(n * -(depth + EPS)))
        filler = prism
        for tool in tools:
            filler = filler.cut(tool)
        if not filler.Solids:
            return None
        result = shape.fuse(filler).removeSplitter()
    except Exception:                                       # noqa: BLE001  (a loop that is not a closed flat wire ...)
        return None
    if not result.isValid() or len(result.Solids) != len(shape.Solids):
        return None
    return result


_LAST = {}


def _bundles_of(shape):
    """pocket_bundles() of the shape, found once per shape (the engine selects again and again)."""
    last = _LAST.get("shape")
    if last is not None and last.isSame(shape):
        return _LAST["result"]
    result = pocket_bundles(shape)
    _LAST["shape"], _LAST["result"] = shape, result
    return result


@core.set_rule("flatten", batch="try", category="pockets")
def _flatten(shape):
    t, bundles = _bundles_of(shape)
    return [t.faces[i] for i in sorted({i for b in bundles for i in b["faces"]})]


@core.pre_removal
def flatten_pockets(shape, group):
    """Fill the recesses the group consists of, one after the other (the shape changes, so they are found again)."""
    wanted = {core.sig(f) for f in group}
    t0, bundles0 = _bundles_of(shape)
    if not wanted <= {core.sig(t0.faces[i]) for b in bundles0 for i in b["faces"]}:
        return None             # the group is more than recesses (e.g. rounds with a dimple in them): not ours
    current, done = shape, 0
    for _ in range(len(wanted) + 1):
        t, bundles = _bundles_of(current)
        mine = next((b for b in bundles if {core.sig(t.faces[i]) for i in b["faces"]} <= wanted), None)
        if mine is None:
            break
        new = fill(current, mine)
        if new is None:
            break
        current, done = new, done + 1
        wanted -= {core.sig(t.faces[i]) for i in mine["faces"]}
        if not wanted:
            break
    return ("result", current) if done else None
