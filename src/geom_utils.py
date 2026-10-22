"""Small geometry helpers shared by the rule modules (no dependency on cleancad_core, so they can be
imported in any order)."""
import math

import Part

GEOM_TOL = 1e-6


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
