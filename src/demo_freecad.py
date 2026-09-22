"""Live FreeCAD GUI demo of the CleanCAD prototype: highlights faces selected for removal in
red, then removes them feature-by-feature with the 3D view updating in real time.

Run inside FreeCAD's GUI (see fcdemo.sh), not with FreeCADCmd.

Jobs come from $CLEANCAD_WORKDIR/samples/examples/manifest.json (all examples, or a subset
via CLEANCAD_ONLY=name1,name2), or a single external file via CLEANCAD_INPUT + CLEANCAD_RULE.
All results (STEP, snapshots, logs) are written under $CLEANCAD_WORKDIR - nothing in the repo.
"""
import os
import sys
import json
import time

import FreeCAD as App
import FreeCADGui as Gui
import Part
import ImportGui
from PySide import QtCore

WORKDIR = os.environ.get("CLEANCAD_WORKDIR", os.path.expanduser("~/Documents/CleanCAD_Workspace"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cleancad_core as core

DELAY_MS = int(os.environ.get("CLEANCAD_DELAY_MS", "1200"))
AUTOQUIT = os.environ.get("CLEANCAD_AUTOQUIT") == "1"
GRAY, RED = (0.75, 0.78, 0.82), (0.85, 0.12, 0.12)

# Instant camera moves so screenshots aren't caught mid-animation.
view_prefs = App.ParamGet("User parameter:BaseApp/Preferences/View")
view_prefs.SetBool("UseNavigationAnimations", False)
view_prefs.SetBool("UseAutoRotation", False)

os.makedirs(os.path.join(WORKDIR, "samples", "examples", "highlight"), exist_ok=True)
os.makedirs(os.path.join(WORKDIR, "samples", "examples", "out"), exist_ok=True)
os.makedirs(os.path.join(WORKDIR, "snapshots"), exist_ok=True)
os.makedirs(os.path.join(WORKDIR, "logs"), exist_ok=True)

if os.environ.get("CLEANCAD_INPUT"):
    single = os.environ["CLEANCAD_INPUT"]
    jobs = [dict(name=os.path.splitext(os.path.basename(single))[0], file=single,
                 rules=os.environ.get("CLEANCAD_RULE", "cyl").split(","))]
else:
    manifest_path = os.path.join(WORKDIR, "samples", "examples", "manifest.json")
    jobs = json.load(open(manifest_path))
    if os.environ.get("CLEANCAD_ONLY"):
        wanted = set(os.environ["CLEANCAD_ONLY"].split(","))
        jobs = [j for j in jobs if j["name"] in wanted]

state = {}


def log(message):
    with open(os.path.join(WORKDIR, "logs", f"{state['job']['name']}.log"), "a") as f:
        f.write(time.strftime("%H:%M:%S ") + message + "\n")


def paint():
    ctx = core.Ctx(state["obj"].Shape)
    fns = [core.RULES[r] for r in state["job"]["rules"]]
    state["vo"].DiffuseColor = [
        RED if (any(fn(f, ctx) for fn in fns) and core.sig(f) not in state["failed"]) else GRAY
        for f in state["obj"].Shape.Faces
    ]


def snapshot(tag):
    Gui.updateGui()
    path = os.path.join(WORKDIR, "snapshots", f"{state['job']['name']}_{state['n']:02d}_{tag}.png")
    Gui.activeDocument().activeView().saveImage(path, 1100, 700, "White")
    state["n"] += 1


def start(index):
    if index >= len(jobs):
        if AUTOQUIT:
            QtCore.QTimer.singleShot(800, lambda: Gui.getMainWindow().close())
        return
    job = jobs[index]
    state.clear()
    state.update(index=index, job=job, n=0, failed=set(), phase="view")
    open(os.path.join(WORKDIR, "logs", f"{job['name']}.log"), "w").close()

    doc = App.newDocument(job["name"])
    obj = doc.addObject("Part::Feature", "Model")
    obj.Shape = Part.read(job["file"])
    doc.recompute()
    state["doc"], state["obj"], state["vo"] = doc, obj, obj.ViewObject
    state["vo"].DisplayMode = "Flat Lines"
    log(f"START {job['name']} rules={job['rules']} faces={len(obj.Shape.Faces)}")
    QtCore.QTimer.singleShot(900, step)


def finish():
    job, shape = state["job"], state["obj"].Shape
    out_path = os.path.join(WORKDIR, "samples", "examples", "out", f"{job['name']}_gui_defeatured.step")
    shape.exportStep(out_path)
    matches_expected = None
    if "expected_faces" in job:
        matches_expected = (len(shape.Faces) == job["expected_faces"]
                             and abs(shape.Volume - job["expected_volume"]) <= 0.05)
    log(f"DONE faces={len(shape.Faces)} valid={shape.isValid()} volume={shape.Volume:.3f} "
        f"expected_match={matches_expected}")
    index, doc_name = state["index"], state["doc"].Name

    def next_job():
        App.closeDocument(doc_name)
        start(index + 1)

    QtCore.QTimer.singleShot(DELAY_MS, next_job)


def step():
    current = state["obj"].Shape
    view = Gui.activeDocument().activeView()

    if state["phase"] in ("view", "fit2"):
        view.viewIsometric()
        view.fitAll()
        Gui.updateGui()
        state["phase"] = "fit2" if state["phase"] == "view" else "show"
        return QtCore.QTimer.singleShot(900, step)

    if state["phase"] == "show":
        paint()
        snapshot("highlight")
        feature_groups = core.groups(current, core.select(current, state["job"]["rules"]))
        log(f"HIGHLIGHT {sum(len(g) for g in feature_groups)} faces red "
            f"in {len(feature_groups)} feature group(s)")
        try:
            highlight_path = os.path.join(WORKDIR, "samples", "examples", "highlight",
                                           f"{state['job']['name']}_highlight.step")
            ImportGui.export([state["obj"]], highlight_path)
            text = open(highlight_path, errors="ignore").read()
            log(f"colored STEP export (GUI mode): COLOUR_RGB={text.count('COLOUR_RGB')}")
        except Exception as e:
            log(f"colored export FAILED: {e!r}")
        state["phase"] = "remove"
        return QtCore.QTimer.singleShot(DELAY_MS, step)

    feature_groups = core.groups(current, core.select(current, state["job"]["rules"], state["failed"]))
    if not feature_groups:
        paint()
        snapshot("final")
        return finish()

    group = feature_groups[0]
    kinds = ",".join(sorted({type(f.Surface).__name__ for f in group}))
    ok, new_shape, why = core.remove_group(current, group)
    if ok:
        state["obj"].Shape = new_shape
        state["doc"].recompute()
        log(f"REMOVED feature ({len(group)} faces: {kinds}): "
            f"faces {len(current.Faces)}->{len(new_shape.Faces)} volume={new_shape.Volume:.2f}")
        paint()
        snapshot("removed")
    else:
        state["failed"].update(core.sig(f) for f in group)
        log(f"FAILED feature ({len(group)} faces: {kinds}): {why} -> kept, geometry+face IDs stored")
        paint()
        snapshot("failed")
    QtCore.QTimer.singleShot(DELAY_MS, step)


start(0)
