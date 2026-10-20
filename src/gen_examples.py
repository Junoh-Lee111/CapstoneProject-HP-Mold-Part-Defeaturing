"""Builds the self-authored example CAD shapes used to exercise the CleanCAD prototype
(per FR-DATA-02/03: ~2-3mm thick, ~100-200mm, covering curved cut-out / ribbed / near-edge types,
plus a few extra shapes exercising other feature categories and a deliberate failure case).

Run headless: FreeCADCmd src/gen_examples.py
Writes STEP files + manifest.json (expected results) under $CLEANCAD_WORKDIR/samples/examples
(default ~/Documents/CleanCAD_Workspace) - NOT into the repo.
"""
import os
import json
import math
import Part
from FreeCAD import Vector

WORKDIR = os.environ.get("CLEANCAD_WORKDIR", os.path.expanduser("~/Documents/CleanCAD_Workspace"))
OUT = os.path.join(WORKDIR, "samples", "examples")
os.makedirs(OUT, exist_ok=True)

import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cleancad_core import sig  # noqa: E402

MANIFEST = []
TOL = 1e-6


# ---- face-level ground truth -------------------------------------------------------------------
# A face of the generated shape is ground truth "to be removed" when it does not belong to the
# clean base shape (the shape expected after defeaturing): it must NOT lie on a base surface
# within that base face's extent. Each truth face also gets a feature type from `kinds`.
def _stype(f):
    return type(f.Surface).__name__


def cyl(f):
    return _stype(f) == "Cylinder"


def cone(f):
    return _stype(f) == "Cone"


def full(f):
    u0, u1, _, _ = f.ParameterRange
    return cyl(f) and u1 - u0 >= 2 * math.pi - 1e-6


def radius(f):
    return f.Surface.Radius if cyl(f) else None


def _coincident(a, b):
    ta, tb = _stype(a), _stype(b)
    if ta != tb:
        return False
    sa, sb = a.Surface, b.Surface
    if ta == "Plane":
        return (abs(sa.Axis.dot(sb.Axis)) > 1 - 1e-9
                and abs((sb.Position - sa.Position).dot(sa.Axis)) < TOL)
    if ta == "Cylinder":
        return (abs(sa.Radius - sb.Radius) < TOL and sa.Axis.cross(sb.Axis).Length < 1e-9
                and (sb.Center - sa.Center).cross(sa.Axis).Length < TOL)
    return False


def _within(a, b):
    p, q = a.BoundBox, b.BoundBox
    return (p.XMin >= q.XMin - TOL and p.XMax <= q.XMax + TOL and p.YMin >= q.YMin - TOL
            and p.YMax <= q.YMax + TOL and p.ZMin >= q.ZMin - TOL and p.ZMax <= q.ZMax + TOL)


def on_base(face, base_faces):
    return any(_coincident(face, b) and _within(face, b) for b in base_faces)


def save(name, shape, rules, expected_faces, expected_volume, note, expect_failure=False,
         base=None, kinds=()):
    """base: the clean shape expected after defeaturing (ground truth = faces not on it);
    kinds: ordered [(feature_type, predicate(face))]; first match names a truth face's type."""
    path = os.path.join(OUT, f"{name}.step")
    shape.exportStep(path)
    entry = dict(
        name=name, file=path, rules=rules,
        expected_faces=expected_faces, expected_volume=round(expected_volume, 3),
        expect_failure=expect_failure, note=note,
    )
    if base is not None:
        # re-read so the signatures match what the evaluation sees (STEP round trip)
        loaded = Part.read(path)
        base_faces = list(base.Faces)
        truth = []
        for f in loaded.Faces:
            if base is shape or on_base(f, base_faces):     # base is shape: nothing is to be removed
                continue
            ftype = next((t for t, pred in kinds if pred(f)), "other")
            truth.append({"sig": list(sig(f)), "type": ftype})
        truth_path = os.path.join(OUT, f"{name}.truth.json")
        json.dump({"case": name, "faces_total": len(loaded.Faces), "base_faces": len(base_faces),
                   "remove": truth}, open(truth_path, "w"), indent=1)
        entry["truth"] = truth_path
        print(f"GEN {name}: truth {len(truth)} of {len(loaded.Faces)} faces "
              f"(base has {len(base_faces)})")
    MANIFEST.append(entry)
    print(f"GEN {name}: faces={len(shape.Faces)} valid={shape.isValid()} volume={shape.Volume:.3f}")


def flat_plate():
    return Part.makeBox(100, 60, 3)


PLATE_VOL = 100 * 60 * 3


def gen_plate_hole_fillets():
    plate = flat_plate()
    hole = Part.makeCylinder(4, 10, Vector(50, 30, -2))
    plate = plate.cut(hole)
    top_edges = [e for e in plate.Edges if abs(e.Vertexes[0].Z - 3) < 1e-6 and abs(e.Vertexes[-1].Z - 3) < 1e-6
                 and e.Curve.__class__.__name__ != "Circle"]
    plate = plate.makeFillet(1.0, top_edges)
    save("plate_hole_fillets", plate, ["cyl"], 6, PLATE_VOL,
         "through hole + edge fillets -> plain plate",
         base=flat_plate(), kinds=[("hole", full), ("fillet", cyl)])


def curved_press(detailed):
    R_in, t, H, arc = 300.0, 2.5, 150.0, 120.0
    ang = math.degrees(arc / R_in)
    th = math.radians(ang / 2)
    outer = Part.makeCylinder(R_in + t, H, Vector(0, 0, 0), Vector(0, 0, 1), ang)
    inner = Part.makeCylinder(R_in, H, Vector(0, 0, 0), Vector(0, 0, 1), 360)
    sheet = outer.cut(inner)

    def radial(shape, z):
        from FreeCAD import Placement, Rotation
        shape.Placement = Placement(Vector(0, 0, z), Rotation(Vector(0, 0, 1), math.degrees(th)))
        return shape

    window = Part.makeBox(30, 30, 20, Vector(R_in - 10, -15, 0))
    if detailed:
        x_edges = [e for e in window.Edges if abs(e.Vertexes[0].Point.y - e.Vertexes[1].Point.y) < 1e-6
                   and abs(e.Vertexes[0].Point.z - e.Vertexes[1].Point.z) < 1e-6]
        window = window.makeFillet(3.0, x_edges)
    sheet = sheet.cut(radial(window, 60))
    if detailed:
        for y, z in ((-25, 25), (25, 125)):
            hole = Part.makeCylinder(2, 30, Vector(R_in - 10, y, 0), Vector(1, 0, 0))
            sheet = sheet.cut(radial(hole, z))
    return sheet.removeSplitter()


def gen_curved_press():
    sheet = curved_press(True)
    # Expected volume is AFTER defeaturing (2 corner fillets + 4 hole faces removed and healed),
    # not sheet.Volume above (which is the shape as generated, before removal).
    save("curved_press", sheet, ["cyl"], 10, 43686.879,
         "curved sheet R300 t2.5, cut-out with R3 corners + 2 holes -> healed curved sheet",
         base=curved_press(False), kinds=[("hole", full), ("fillet", cyl)])


def gen_ribbed():
    t = 2.5
    plate = Part.makeBox(150, 100, t)
    rib_a = Part.makeBox(110, 1.5, 8, Vector(20, 24.25, t))
    rib_b = Part.makeBox(110, 1.5, 8, Vector(20, 74.25, t))
    rib_c = Part.makeBox(1.5, 20, 8, Vector(74.25, 40, t))
    shape = plate.fuse(rib_a).fuse(rib_b).fuse(rib_c).removeSplitter()
    root = [e for e in shape.Edges if abs(e.BoundBox.ZMin - t) < 1e-6 and abs(e.BoundBox.ZMax - t) < 1e-6
            and abs(e.BoundBox.XLength - 110) < 1e-6 and 24 < e.BoundBox.YMin < 26.5]
    shape = shape.makeFillet(0.5, root)
    save("ribbed", shape, ["prot"], 6, 150 * 100 * t,
         "3 separate ribs (one with root fillets) -> plain plate",
         base=plate, kinds=[("fillet", cyl), ("rib", lambda f: True)])


def gen_chamfer():
    plate = flat_plate()
    top_edges = [e for e in plate.Edges if abs(e.BoundBox.ZMin - 3) < 1e-6 and abs(e.BoundBox.ZMax - 3) < 1e-6]
    plate = plate.makeChamfer(1.0, top_edges)
    plate = plate.cut(Part.makeCylinder(3, 10, Vector(50, 30, -2)))
    plate = plate.cut(Part.makeCone(3, 4.2, 1.2, Vector(50, 30, 1.8))).removeSplitter()
    base = flat_plate().cut(Part.makeCylinder(3, 10, Vector(50, 30, -2)))
    save("chamfer", plate, ["chamfer"], 7, PLATE_VOL - math.pi * 9 * 3,
         "perimeter chamfer + countersink -> plate with a plain hole",
         base=base, kinds=[("countersink", cone), ("chamfer", lambda f: True)])


def gen_boss():
    plate = flat_plate().fuse(Part.makeCylinder(7, 6, Vector(50, 30, 3))).removeSplitter()
    plate = plate.cut(Part.makeCylinder(2.5, 20, Vector(50, 30, -5)))
    base = flat_plate().cut(Part.makeCylinder(2.5, 20, Vector(50, 30, -5)))
    save("boss", plate, ["prot"], 7, PLATE_VOL - math.pi * 6.25 * 3,
         "boss removed, screw hole through the plate stays",
         base=base, kinds=[("boss", lambda f: True)])


def gen_emboss():
    plate = flat_plate()
    pads = [Part.makeBox(25, 12, 0.5, Vector(15, 15, 3))]
    pads += [Part.makeBox(2, 8, 0.5, Vector(50 + i * 5, 20, 3)) for i in range(3)]
    for p in pads:
        plate = plate.fuse(p)
    plate = plate.cut(Part.makeBox(20, 3, 0.4, Vector(60, 42, 2.6))).removeSplitter()
    save("emboss", plate, ["prot", "recess"], 6, PLATE_VOL,
         "raised + engraved emboss -> plain plate",
         base=flat_plate(), kinds=[("emboss", lambda f: True)])


def gen_rib_network():
    shape = Part.makeBox(120, 80, 2.5)
    ribs = [
        Part.makeBox(100, 1.5, 8, Vector(10, 24.25, 2.5)),
        Part.makeBox(100, 1.5, 8, Vector(10, 54.25, 2.5)),
        Part.makeBox(1.5, 60, 8, Vector(39.25, 10, 2.5)),
        Part.makeBox(1.5, 60, 8, Vector(79.25, 10, 2.5)),
    ]
    for r in ribs:
        shape = shape.fuse(r)
    shape = shape.removeSplitter()
    save("rib_network", shape, ["prot"], 6, 120 * 80 * 2.5,
         "crossing ribs form one connected feature -> plain plate",
         base=Part.makeBox(120, 80, 2.5), kinds=[("rib", lambda f: True)])


def gen_near_edge():
    plate = flat_plate()
    corner_edges = [e for e in plate.Edges if abs(e.BoundBox.XMin - 100) < 1e-6
                    and abs(e.BoundBox.YMin - 60) < 1e-6 and e.BoundBox.ZLength > 2]
    plate = plate.makeFillet(3.0, corner_edges)
    plate = plate.cut(Part.makeCylinder(2, 10, Vector(3, 30, -2)))
    plate = plate.cut(Part.makeCylinder(4, 10, Vector(100, 15, -2)))
    plate = plate.fuse(Part.makeBox(1.5, 26, 6, Vector(95.5, 24, 3))).removeSplitter()
    save("near_edge", plate, ["cyl", "prot"], 6, PLATE_VOL,
         "hole 1mm from an edge, an edge-opening notch, a corner fillet, and a rib near an edge -> plain plate",
         base=flat_plate(),
         kinds=[("hole", full), ("notch", lambda f: cyl(f) and abs(radius(f) - 4) < 1e-6),
                ("fillet", cyl), ("rib", lambda f: True)])


def gen_fail_demo():
    plate = flat_plate().cut(Part.makeCylinder(4, 10, Vector(50, 30, -2)))
    save("fail_demo", plate, ["fail_demo"], 7, PLATE_VOL - math.pi * 16 * 3,
         "targets an un-removable face on purpose: must be detected, stored, and left unchanged",
         expect_failure=True, base=plate)


FONT_DIR, FONT_FILE = "/System/Library/Fonts/Supplemental", "Arial Bold.ttf"


def text_prism(text, height, z0, z1, x0=20.0, y0=22.0):
    """Solid letters (with their counters) between z0 and z1, or None when the font is not available."""
    if not os.path.exists(os.path.join(FONT_DIR, FONT_FILE)):
        return None
    glyphs = Part.makeWireString(text, FONT_DIR + "/", FONT_FILE, height, 0)
    solids = []
    for wires in glyphs:
        if not wires:                      # a space has no outline
            continue
        face = Part.makeFace(wires, "Part::FaceMakerBullseye")
        solids.append(face.extrude(Vector(0, 0, z1 - z0)))
    shape = solids[0]
    for s in solids[1:]:
        shape = shape.fuse(s)
    shape.translate(Vector(x0, y0, z0))
    return shape


def gen_logo_engrave():
    text = text_prism("X01 ABS", 8, 2.7, 3.2)
    if text is None:
        print("GEN logo_engrave skipped: no font")
        return
    plate = flat_plate().cut(text).removeSplitter()
    save("logo_engrave", plate, ["logo"], 6, PLATE_VOL, "text engraved 0.3 mm deep -> plain plate",
         base=flat_plate(), kinds=[("logo", lambda f: True)])


def gen_logo_emboss():
    text = text_prism("X01 ABS", 8, 3.0, 3.3)
    if text is None:
        print("GEN logo_emboss skipped: no font")
        return
    plate = flat_plate().fuse(text).removeSplitter()
    save("logo_emboss", plate, ["logo"], 6, PLATE_VOL, "text raised 0.3 mm -> plain plate",
         base=flat_plate(), kinds=[("logo", lambda f: True)])


def gen_logo_through_text():
    text = text_prism("X01 ABS", 8, -1.0, 4.0)
    if text is None:
        print("GEN logo_through_text skipped: no font")
        return
    plate = flat_plate().cut(text).removeSplitter()
    # stencil-like letters cut through the plate are a cut-out, not a logo: must stay as they are
    save("logo_through_text", plate, ["logo"], len(plate.Faces), plate.Volume,
         "text cut through the plate (not a logo) -> unchanged", base=plate)


def gen_pocket():
    plate = flat_plate().cut(Part.makeBox(20, 12, 1.5, Vector(40, 24, 1.5)))
    # a blind functional pocket, not a marking: must stay as it is
    save("pocket", plate, ["logo"], len(plate.Faces), plate.Volume,
         "blind rectangular pocket 20x12x1.5 (not a logo) -> unchanged", base=plate)


def main():
    for gen in (gen_plate_hole_fillets, gen_curved_press, gen_ribbed, gen_chamfer,
                gen_boss, gen_emboss, gen_rib_network, gen_near_edge, gen_fail_demo,
                gen_logo_engrave, gen_logo_emboss, gen_logo_through_text, gen_pocket):
        gen()
    manifest_path = os.path.join(OUT, "manifest.json")
    json.dump(MANIFEST, open(manifest_path, "w"), indent=1)
    print(f"GEN manifest: {len(MANIFEST)} examples -> {manifest_path}")


# Note: FreeCADCmd runs this file with __name__ set to the module name, not "__main__",
# so call main() unconditionally rather than gating on the usual `if __name__ == "__main__"`.
main()
