"""Small geometry helpers shared by the rule modules (no dependency on cleancad_core, so they can be
imported in any order)."""
import math

import Part

GEOM_TOL = 1e-6


def stype(f):
    return type(f.Surface).__name__


def plane_of(face):
    """The plane a face lies in: its own surface if it is a Plane, or - for free-form (B-spline) faces
    that are in fact flat, as in surface models of pressed parts - the plane found by FreeCAD; else None."""
    if stype(face) == "Plane":
        return face.Surface
    try:
        return face.findPlane(1e-4)
    except Exception:           # noqa: BLE001
        return None


def plane_frame(face, plane=None):
    """Origin, outward unit normal and two in-plane unit axes of a flat face."""
    from FreeCAD import Vector
    plane = plane or plane_of(face)
    u0, u1, v0, v1 = face.ParameterRange
    try:
        n = Vector(face.normalAt((u0 + u1) / 2, (v0 + v1) / 2))
    except Exception:           # noqa: BLE001
        n = Vector(plane.Axis)
    n = Vector(plane.Axis) * (1 if Vector(plane.Axis).dot(n) >= 0 else -1)
    n.normalize()
    u = Vector(plane.XDir) if hasattr(plane, "XDir") else None
    if u is None or abs(u.dot(n)) > 1e-6:
        u = n.cross(Vector(1, 0, 0))
        if u.Length < 1e-6:
            u = n.cross(Vector(0, 1, 0))
    u.normalize()
    v = n.cross(u)
    v.normalize()
    return plane.Position, n, u, v


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
        self._plane = {}

    def plane(self, i):
        """Plane of face i if it is flat (also free-form faces that are flat), else None."""
        if i not in self._plane:
            self._plane[i] = plane_of(self.faces[i])
        return self._plane[i]


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
