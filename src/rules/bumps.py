"""BUMPS: small raised dots and nubs on a flat face are cut away (mentor: "small bumps kept for a gap: delete").

Rule: bump - from the INNER WIRES of a flat host face (the foot of a bump): the faces behind the wire that lie on or above
the host plane and connect only to the host form the bump. Accepted when it is small: the foot is at most the profile's
"bump_max_size" wide (default 3 mm), at most 1.5 mm high and has at most 8 faces. Bigger columns are bosses, thin long
walls ribs: other rules.
The removal does not use the CAD kernel's defeaturing: each foot pushed up by the bump's height is a solid that is cut
away. Limits are parameters of this description, not validated general criteria."""
import os
import sys

import Part

_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # .../src
for _p in (_SRC, os.path.join(_SRC, "engine")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import cleancad_core as core  # noqa: E402
from geom_utils import Topo, plane_frame, face_points  # noqa: E402

MIN_HOST_AREA = 20.0         # mm2
MAX_BUMP_HEIGHT = 1.5        # mm
MAX_BUMP_FACES = 8
BELOW_TOL = 1e-4             # mm: nothing of a bump may reach below the host plane
MIN_HEIGHT = 0.02            # mm


def bump_bundles(shape):
    """-> (topo, [{"host", "faces": [indices], "height", "n", "origin", "rim": wire}])"""
    t = Topo(shape)
    if not shape.Solids:
        return t, []
    limit = core.PROFILE.get("bump_max_size", 3.0)
    edge_owners = {}
    for e, owners in t.edges:
        edge_owners.setdefault(e.hashCode(), []).append((e, owners))

    def owners_of(edge):
        for e, owners in edge_owners.get(edge.hashCode(), []):
            if e.isSame(edge):
                return owners
        return set()

    bundles, taken = [], set()
    for h, host in enumerate(t.faces):
        if t.plane(h) is None or t.area[h] < MIN_HOST_AREA or len(host.Wires) < 2:
            continue
        origin, n, _, _ = plane_frame(host, t.plane(h))
        for wire in host.Wires:
            if wire.isSame(host.OuterWire):
                continue
            wb = wire.BoundBox
            if max(wb.XLength, wb.YLength, wb.ZLength) > limit:
                continue
            seeds = set()
            for e in wire.Edges:
                seeds |= owners_of(e)
            seeds.discard(h)
            if not seeds or seeds & taken:
                continue
            bump, stack, ok = set(), list(seeds), True
            while stack and ok:
                i = stack.pop()
                if i in bump or i == h:
                    continue
                if min((p - origin).dot(n) for p in face_points(t.faces[i])) < -BELOW_TOL:
                    ok = False                      # reaches below the host plane: a hole or a recess, not a bump
                    break
                bump.add(i)
                if len(bump) > MAX_BUMP_FACES:
                    ok = False
                    break
                stack += [o for o in t.nb[i] if o != h and o not in bump]
            if not ok or not bump:
                continue
            height = max((p - origin).dot(n) for i in bump for p in face_points(t.faces[i]))
            if height < MIN_HEIGHT or height > MAX_BUMP_HEIGHT:
                continue
            taken |= bump
            bundles.append({"host": h, "faces": sorted(bump), "height": height, "n": n, "origin": origin, "rim": wire})
    return t, bundles


_LAST = {}


def _bundles_of(shape):
    last = _LAST.get("shape")
    if last is not None and last.isSame(shape) and _LAST.get("limit") == core.PROFILE.get("bump_max_size"):
        return _LAST["result"]
    result = bump_bundles(shape)
    _LAST.update(shape=shape, result=result, limit=core.PROFILE.get("bump_max_size"))
    return result


@core.set_rule("bump", batch="try", category="bumps")
def _bump(shape):
    t, bundles = _bundles_of(shape)
    return [t.faces[i] for i in sorted({i for b in bundles for i in b["faces"]})]


@core.pre_removal
def cut_bumps(shape, group):
    """Cut the bumps the group consists of away (one tool per bump, fused to one cut)."""
    wanted = {core.sig(f) for f in group}
    t, bundles = _bundles_of(shape)
    mine = [b for b in bundles if {core.sig(t.faces[i]) for i in b["faces"]} <= wanted]
    if not mine or not wanted <= {core.sig(t.faces[i]) for b in mine for i in b["faces"]}:
        return None                 # the group is more than bumps
    try:
        tools = [Part.Face(b["rim"]).extrude(b["n"] * b["height"]) for b in mine]
        tool = tools[0].multiFuse(tools[1:]) if len(tools) > 1 else tools[0]
        result = shape.cut(tool).removeSplitter()
    except Exception:                                       # noqa: BLE001
        return None
    if not result.isValid() or len(result.Solids) != len(shape.Solids):
        return None
    return "result", result
