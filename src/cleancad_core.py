"""CleanCAD core mechanics (runs inside FreeCAD, headless or GUI).

MECHANISM (stable): groups() / remove_group() / process()
CRITERIA (to be filled in by the team): the RULES registry below - "which faces to remove?"

The rules registered here are TEST SCAFFOLDING ONLY: simple stand-ins so the removal
mechanism can be exercised end to end. The real decision logic (Stage 1 rule-based,
Stage 2 ML-based per the confirmed architecture) plugs in the same way - register a
function with @rule("name") that takes (face, ctx) and returns True if that face
should be removed.
"""
import Part

MAX_SMALL_RADIUS = 5.0
RULES = {}


def rule(name):
    def deco(fn):
        RULES[name] = fn
        return fn
    return deco


def sig(face):
    c = face.CenterOfMass
    return (type(face.Surface).__name__, round(face.Area, 3), round(c.x, 2), round(c.y, 2), round(c.z, 2))


def normal(face):
    try:
        return face.normalAt(*face.Surface.parameter(face.CenterOfMass))
    except Exception:
        return None


class Ctx:
    """Shared per-shape context available to rule functions (e.g. the base plate's top Z)."""

    def __init__(self, shape):
        ups = [f for f in shape.Faces if type(f.Surface).__name__ == "Plane"
               and (normal(f) is not None and normal(f).z > 0.99)]
        self.base_z = max(ups, key=lambda f: f.Area).CenterOfMass.z if ups else 0.0


# ---------------- test-scaffolding rules (NOT the project's real decision criteria) ----------------
@rule("cyl")        # small cylinders: holes, small fillets
def _cyl(f, c):
    return type(f.Surface).__name__ == "Cylinder" and f.Surface.Radius <= MAX_SMALL_RADIUS


@rule("prot")       # faces protruding above the base plate: ribs, bosses, raised emboss
def _prot(f, c):
    bb = f.BoundBox
    return bb.ZMin >= c.base_z - 1e-6 and bb.ZMax > c.base_z + 1e-6


@rule("recess")     # faces sunk below the top surface (not the bottom/sides): pockets, engraved emboss
def _recess(f, c):
    bb = f.BoundBox
    return bb.ZMin > 1e-6 and bb.ZMin < c.base_z - 1e-6 and bb.ZMax <= c.base_z + 1e-6


@rule("chamfer")    # small inclined planes and cones
def _chamfer(f, c):
    t = type(f.Surface).__name__
    if t == "Cone":
        return f.Area < 200
    if t != "Plane":
        return False
    n = normal(f)
    return n is not None and max(abs(n.x), abs(n.y), abs(n.z)) < 0.99 and f.Area < 200


@rule("fail_demo")  # deliberately selects an un-removable face, to exercise failure handling
def _fail(f, c):
    return type(f.Surface).__name__ == "Plane" and f.BoundBox.ZMax < 1e-6
# ------------------------------------------------------------------------------------------------


def select(shape, rule_names, failed=()):
    ctx = Ctx(shape)
    fns = [RULES[r] for r in rule_names]
    return [f for f in shape.Faces if any(fn(f, ctx) for fn in fns) and sig(f) not in failed]


def groups(shape, faces):
    """Connected components of the selected faces: one physical feature each
    (e.g. a rib's 5 faces are removed together, not one at a time)."""
    all_faces = shape.Faces

    def idx(f):
        return next(i for i, g in enumerate(all_faces) if g.isSame(f))

    selected = {idx(f) for f in faces}
    if not selected:
        return []
    parent = {i: i for i in selected}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for e in shape.Edges:
        adjacent = [a for a in (idx(f) for f in shape.ancestorsOfType(e, Part.Face)) if a in selected]
        for a in adjacent[1:]:
            parent[find(a)] = find(adjacent[0])
    out = {}
    for i in selected:
        out.setdefault(find(i), []).append(all_faces[i])
    return list(out.values())


def remove_group(shape, group):
    """Remove one feature (a group of connected faces).

    FreeCAD's defeaturing fails SILENTLY when a face can't be removed - it just
    returns the shape unchanged. Success must therefore be judged by comparing
    the result to the input, not by catching an exception.
    """
    try:
        new_shape = shape.defeaturing(group)
    except Exception as e:
        return False, shape, f"exception: {e!r}"
    changed = len(new_shape.Faces) < len(shape.Faces) or abs(new_shape.Volume - shape.Volume) > 1e-6
    if not changed:
        return False, shape, "no-op (shape unchanged)"
    if not new_shape.isValid():
        return False, shape, "result invalid"
    return True, new_shape, "ok"


def process(shape, rule_names):
    """Headless end-to-end: repeatedly remove feature groups until none remain.

    Returns (final_shape, removed, failures). Each failure keeps the geometry's
    face signatures so it can be stored for manual correction and fed back into
    Stage 2 retraining (per FR-DEF-04 / NFR-REL-02).
    """
    failed_sigs, removed, failures = set(), [], []
    current = shape
    while True:
        candidate_groups = groups(current, select(current, rule_names, failed_sigs))
        if not candidate_groups:
            break
        group = candidate_groups[0]
        ok, new_shape, why = remove_group(current, group)
        info = {
            "faces": len(group),
            "types": sorted({type(f.Surface).__name__ for f in group}),
            "sigs": [sig(f) for f in group],
        }
        if ok:
            removed.append(info)
            current = new_shape
        else:
            info["reason"] = why
            failures.append(info)
            failed_sigs.update(sig(f) for f in group)
    return current, removed, failures
