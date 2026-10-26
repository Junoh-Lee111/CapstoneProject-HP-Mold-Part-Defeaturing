"""HOLES: complete round holes below a diameter limit (profile "hole_diameter").

Rule: ref_holes (a port of the HP mentor's example). A hole is a full 360-degree bore (not a groove);
the floor of a blind hole goes with it."""
import math
import os
import sys

import Part

_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # .../src
for _p in (_SRC, os.path.join(_SRC, "engine")):                       # layers: engine/, rules/, ...
    if _p not in sys.path:
        sys.path.insert(0, _p)
import cleancad_core as core  # noqa: E402
from geom_utils import Topo, stype, flatten, sweep, inward_cylinder, same_cyl, connected, SIZE_TOL, TWO_PI  # noqa: E402,F401


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


@core.set_rule("ref_holes", category="holes")
def _holes(shape):
    return flatten(hole_groups(shape, core.PROFILE["hole_diameter"]))
